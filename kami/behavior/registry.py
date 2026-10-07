"""Model registry and the behaviour suite plugged into a simulation.

Design doc §2 principle 7: behaviour models are trained in a separate
pipeline; the simulator only loads checkpoints. A checkpoint is a small JSON
file ``<root>/<slot>/<version>.json``::

    {"slot": "pool_accept", "version": "v2", "class": "kami.behavior.models.LogitPoolAccept",
     "params": {"asc": -0.8, ...}, "meta": {"trained_on": "2026-09 SP survey"}}
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Dict, Optional

from kami.behavior import models as M

SLOTS = ("booking", "cancel_wait", "cancel_matched", "pool_accept", "driver_accept", "idle_move", "driver_shift")


@dataclass
class BehaviorSuite:
    """One model per decision point. Swap any slot without touching the engine."""

    booking: Any = field(default_factory=M.LogitBooking)
    cancel_wait: Any = field(default_factory=M.WeibullCancel)
    cancel_matched: Any = field(default_factory=M.OverrunCancel)
    pool_accept: Any = field(default_factory=M.LogitPoolAccept)
    driver_accept: Any = field(default_factory=M.LogitDriverAccept)
    idle_move: Any = field(default_factory=M.HomeBiasIdleMove)
    driver_shift: Any = field(default_factory=M.ScheduledShift)

    def replace(self, **slots) -> "BehaviorSuite":
        return replace(self, **slots)

    def describe(self) -> Dict[str, Dict]:
        return {f.name: {"class": type(getattr(self, f.name)).__name__,
                         "params": getattr(self, f.name).to_dict()} for f in fields(self)}

    @classmethod
    def employed_drivers(cls) -> "BehaviorSuite":
        """Drivers are employees: no rejection, platform controls idle moves."""
        return cls(driver_accept=M.AlwaysAccept())


def _import(path: str):
    mod, _, name = path.rpartition(".")
    return getattr(importlib.import_module(mod), name)


class ModelRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save(self, slot: str, model, version: str, meta: Optional[Dict] = None) -> Path:
        if slot not in SLOTS:
            raise ValueError(f"unknown slot {slot}; expected one of {SLOTS}")
        path = self.root / slot / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        cls = type(model)
        doc = {"slot": slot, "version": version, "class": f"{cls.__module__}.{cls.__name__}",
               "params": model.to_dict(), "meta": meta or {}}
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
        return path

    def versions(self, slot: str):
        d = self.root / slot
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def load(self, slot: str, version: str = "latest"):
        if version == "latest":
            vs = self.versions(slot)
            if not vs:
                raise FileNotFoundError(f"no checkpoint for slot {slot} under {self.root}")
            version = vs[-1]
        doc = json.loads((self.root / slot / f"{version}.json").read_text())
        cls = _import(doc["class"])
        params = doc.get("params") or {}
        if cls is M.TransitionMatrixIdleMove:
            return cls(params["matrix"])
        if not params:
            return cls()
        return cls(**params)

    def suite(self, versions: Optional[Dict[str, str]] = None, base: Optional[BehaviorSuite] = None) -> BehaviorSuite:
        """Build a suite: listed slots from the registry, others from ``base`` (defaults)."""
        base = base or BehaviorSuite()
        chosen = {slot: self.load(slot, ver) for slot, ver in (versions or {}).items()}
        return base.replace(**chosen)
