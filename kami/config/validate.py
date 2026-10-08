"""Validation helpers for declarative specs.

Every error is recorded with the dotted path of the offending field
(``policy_group.members[0].policy.params.wait_treshold``) and all errors of a
document are reported at once in a single ``SpecError``.
"""
from __future__ import annotations

import dataclasses
import difflib
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MISSING = object()

TYPE_NAMES = {int: "số nguyên", float: "số", bool: "true/false", str: "chuỗi", dict: "object", list: "mảng"}


class SpecError(ValueError):
    """Invalid configuration. ``errors`` is a list of ``(field path, message)``."""

    def __init__(self, errors: Iterable[Tuple[str, str]]):
        self.errors: List[Tuple[str, str]] = [(p or "<gốc>", m) for p, m in errors]
        lines = "\n".join(f"  - {p}: {m}" for p, m in self.errors)
        super().__init__(f"cấu hình không hợp lệ ({len(self.errors)} lỗi):\n{lines}")

    def paths(self) -> List[str]:
        return [p for p, _ in self.errors]


class Errors(list):
    def add(self, path: str, msg: str) -> None:
        self.append((path, msg))

    def check(self) -> None:
        if self:
            raise SpecError(self)


def join(path: str, key) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else str(key)


def suggest(name: str, options: Iterable[str]) -> str:
    """`` (ý bạn là 'x'?)`` for a near miss, else the list of valid names."""
    options = sorted(str(o) for o in options)
    close = difflib.get_close_matches(str(name), options, n=1, cutoff=0.6)
    if close:
        return f"; ý bạn là '{close[0]}'? (có: {', '.join(options)})"
    return f" (có: {', '.join(options)})" if options else ""


def type_ok(v: Any, typ) -> bool:
    if typ is None or typ == "any":
        return True
    if isinstance(typ, tuple):
        return any(type_ok(v, t) for t in typ)
    if typ is int:
        return isinstance(v, int) and not isinstance(v, bool)
    if typ is float:
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, typ)


def type_name(typ) -> str:
    if isinstance(typ, tuple):
        return " hoặc ".join(type_name(t) for t in typ)
    return TYPE_NAMES.get(typ, getattr(typ, "__name__", str(typ)))


def check_value(v: Any, path: str, errs: Errors, typ=None, *, nullable: bool = False, ge=None, gt=None, le=None,
                choices: Optional[Sequence] = None) -> bool:
    """Type / range / enum check of one value. Returns True if valid."""
    if v is None:
        if nullable:
            return True
        errs.add(path, "không được để null")
        return False
    if not type_ok(v, typ):
        errs.add(path, f"sai kiểu: cần {type_name(typ)}, nhận {type(v).__name__} {v!r}")
        return False
    if choices is not None and v not in choices:
        errs.add(path, f"giá trị {v!r} không hợp lệ" + suggest(v, choices))
        return False
    if type_ok(v, float):
        if ge is not None and v < ge:
            errs.add(path, f"phải ≥ {ge}, nhận {v}")
            return False
        if gt is not None and v <= gt:
            errs.add(path, f"phải > {gt}, nhận {v}")
            return False
        if le is not None and v > le:
            errs.add(path, f"phải ≤ {le}, nhận {v}")
            return False
    return True


def unknown_keys(d: Dict, allowed: Iterable[str], path: str, errs: Errors) -> None:
    allowed = list(allowed)
    for k in d:
        if k not in allowed:
            errs.add(join(path, k), "trường không tồn tại" + suggest(k, allowed))


def default_kind(value: Any):
    """Accepted JSON type for a parameter, inferred from its Python default."""
    if isinstance(value, bool):
        return bool
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    if isinstance(value, str):
        return str
    if isinstance(value, dict):
        return dict
    if isinstance(value, (list, tuple)):
        return list
    return "any"


def dataclass_overrides(d: Any, cls, path: str, errs: Errors, constraints: Optional[Dict[str, Dict]] = None,
                        nested: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a sparse ``{field: value}`` dict against the fields of an engine dataclass.

    Accepted types are inferred from the dataclass defaults (``None`` default = number or null).
    ``nested`` maps a field to the dataclass of a nested sparse dict (e.g. ``fare`` → ``FareModel``).
    """
    if not isinstance(d, dict):
        errs.add(path, f"sai kiểu: cần object, nhận {type(d).__name__}")
        return {}
    constraints = constraints or {}
    nested = nested or {}
    defaults = {}
    for f in dataclasses.fields(cls):
        if f.default is not dataclasses.MISSING:
            defaults[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            defaults[f.name] = f.default_factory()  # type: ignore[misc]
    unknown_keys(d, list(defaults) + [k for k in nested if k not in defaults], path, errs)
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if k not in defaults and k not in nested:
            continue
        p = join(path, k)
        if k in nested:
            sub = nested[k]
            out[k] = sub(v, p, errs) if callable(sub) and not dataclasses.is_dataclass(sub) else \
                dataclass_overrides(v, sub, p, errs)
            continue
        dv = defaults[k]
        kind = default_kind(dv)
        c = dict(constraints.get(k, {}))
        if dv is None:
            kind, c["nullable"] = (float, True) if "type" not in c else (c.pop("type"), True)
        elif "type" in c:
            kind = c.pop("type")
        if check_value(v, p, errs, kind, **c):
            out[k] = v
    return out
