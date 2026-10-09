"""The service accepts current specs, excluding legacy policy/pooling configuration."""
from __future__ import annotations

import math
from kami.config import RunSpec, SpecError


def finite_json(value, path=""):
    if isinstance(value, float) and not math.isfinite(value):
        raise SpecError([(path, "số phải hữu hạn")])
    if isinstance(value, dict):
        for key, item in value.items():
            finite_json(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            finite_json(item, f"{path}[{i}]")


def public_spec(doc):
    finite_json(doc)
    if not isinstance(doc, dict):
        raise SpecError([("", "cần object RunSpec")])
    errors = []
    if "policy_group" in doc:
        errors.append(("policy_group", "policy nằm ngoài phạm vi API hiện tại"))
    config = doc.get("sim_config", {})
    if isinstance(config, dict) and "pooling" in config:
        errors.append(("sim_config.pooling", "pooling nằm ngoài phạm vi API hiện tại"))
    behavior = doc.get("behavior", {})
    if isinstance(behavior, dict):
        for group in ("models", "slots"):
            if isinstance(behavior.get(group), dict) and "pool_accept" in behavior[group]:
                errors.append((f"behavior.{group}.pool_accept", "pooling nằm ngoài phạm vi API hiện tại"))
    if errors:
        raise SpecError(errors)
    return RunSpec.from_dict(doc)
