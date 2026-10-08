"""kami 0.1 CLI arguments → equivalent ``RunSpec`` (``python -m kami spec``, AC01-2)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from kami.config.specs import (BehaviorSpec, FileZoneSpec, GridNetworkSpec, PolicyGroupMember, PolicyGroupSpec,
                               PolicySpec, PresetSourceSpec, RoadNetworkSpec, RunSpec, ScenarioSpec, SquareZoneSpec)


def spec_from_cli(preset: str = "weekday_am_peak", policy: str = "baseline",
                  policy_args: Optional[Dict[str, Any]] = None, seed: int = 0, demand: float = 200.0,
                  drivers: int = 150, network: str = "grid", zones: Optional[str] = None, zone_m: float = 1000.0,
                  grid_km: float = 8.0, registry: Optional[str] = None, employed_drivers: bool = False,
                  overrides: Optional[Dict[str, Any]] = None) -> RunSpec:
    """The RunSpec that ``python -m kami run`` with these flags runs (same scenario, policy, behaviour, seed).

    ``overrides`` (synthetic parameters, e.g. ``t_end``) has no 0.1 flag; it exists to shrink scenarios in tests.
    """
    if network.startswith(("road", "fleetpy")):
        net = RoadNetworkSpec(name=network.partition(":")[2] or "example_network")
        zsp = FileZoneSpec(name=zones) if zones else SquareZoneSpec(cell_m=float(zone_m))
    else:
        net = GridNetworkSpec(width_m=grid_km * 1000, height_m=grid_km * 1000)
        zsp = SquareZoneSpec(cell_m=float(zone_m))
    scenario = ScenarioSpec(name=preset, network=net, zones=zsp, n_drivers=drivers, seed=seed,
                            source=PresetSourceSpec(preset=preset, demand_per_hour=demand,
                                                    overrides=dict(overrides or {})))
    group = PolicyGroupSpec(name=policy, members=[PolicyGroupMember(PolicySpec(policy, dict(policy_args or {})))])
    # 0.1: --registry replaces the whole suite (and so ignores --employed-drivers)
    behavior = BehaviorSpec(registry=registry) if registry else \
        BehaviorSpec(preset="employed_drivers" if employed_drivers else "default")
    spec = RunSpec(name=f"{preset}-{policy}-s{seed}", scenario=scenario, policy_group=group, behavior=behavior)
    return RunSpec.from_dict(spec.to_dict())   # validate
