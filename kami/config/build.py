"""Build engine objects from specs (sprint 01, S01-2).

Builders only call kami 0.1 APIs (``GridNetwork``, ``ScenarioBuilder``, ``POLICIES``,
``Composite``, ``BehaviorSuite``, ``ModelRegistry``, ``SimConfig``), so a ``RunSpec``
gives exactly the metrics of the equivalent Python code (AC01-1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from kami.behavior import BehaviorSuite, ModelRegistry
from kami.behavior.registry import SLOTS
from kami.config.specs import (DEFAULT_TIMESERIES_INTERVAL_S, WRAPPERS, BehaviorSpec, CsvSourceSpec,
                               FileZoneSpec, FleetPyDemandSourceSpec, FleetSpec, GridNetworkSpec, H3ZoneSpec,
                               ModelSpec, PolicyGroupSpec, PolicySpec, PresetSourceSpec, Ref, RoadNetworkSpec,
                               RunSpec, ScenarioSpec, SimConfigSpec, SquareZoneSpec, SyntheticSourceSpec,
                               VehicleTypeSpec, ZonalSourceSpec, _model_classes, model_params_class)
from kami.config.validate import SpecError
from kami.core.engine import SimConfig, Simulation
from kami.matching import MatchingParams
from kami.network import FileZoneSystem, GridNetwork, H3ZoneSystem, RoadNetwork, SquareZoneSystem
from kami.policy import POLICIES, Baseline, Composite, Policy
from kami.pooling import PoolingParams
from kami.pricing import FareModel
from kami.scenario import Scenario, ScenarioBuilder, read_zone_weights

_WORLD_CACHE: Dict[str, Tuple[Any, Any]] = {}


def build_network(spec):
    if isinstance(spec, GridNetworkSpec):
        return GridNetwork(spec.width_m, spec.height_m, spec.spacing_m, spec.speed_kmh)
    if isinstance(spec, RoadNetworkSpec):
        return RoadNetwork(spec.name, data_root=spec.data_root, network_dynamics_file=spec.dynamics_file,
                           scenario_time=spec.scenario_time, backend=spec.backend)
    raise TypeError(f"unknown network spec {spec!r}")


def build_zones(spec, network):
    if isinstance(spec, SquareZoneSpec):
        return SquareZoneSystem(network, spec.cell_m)
    if isinstance(spec, H3ZoneSpec):
        return H3ZoneSystem(network, spec.resolution)
    if isinstance(spec, FileZoneSpec):
        return FileZoneSystem(network, spec.name, neighbor_radius_m=spec.neighbor_radius_m)
    raise TypeError(f"unknown zone spec {spec!r}")


def build_world(spec: ScenarioSpec, cache: bool = True):
    """``(network, zones)`` of a scenario; cached per (network, zones) spec in this process (road networks load slowly)."""
    key = json.dumps([spec.network.to_dict(), spec.zones.to_dict()], sort_keys=True)
    if cache and key in _WORLD_CACHE:
        return _WORLD_CACHE[key]
    net = build_network(spec.network)
    world = (net, build_zones(spec.zones, net))
    if cache:
        _WORLD_CACHE[key] = world
    return world


def clear_world_cache() -> None:
    _WORLD_CACHE.clear()


def _data_file(path: str, network) -> str:
    """A replay file: as given if it exists, else relative to the network's data root."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return str(p)
    root = getattr(network, "data_root", None)
    if root is not None and (Path(root) / p).exists():
        return str(Path(root) / p)
    raise FileNotFoundError(f"replay file not found: {path} (also looked under the network data root {root})")


def _fleet_slots(fleets: Sequence[FleetSpec], vehicle_types: Sequence[VehicleTypeSpec]):
    """Expanded ``[(fleet, vehicle_type), ...]``, one entry per vehicle, in declaration order."""
    types = {v.name: v for v in vehicle_types}
    return [(fl, types[c.vehicle_type]) for fl in fleets for c in fl.composition for _ in range(c.count)]


def apply_fleets(scenario: Scenario, fleets: Sequence[FleetSpec], vehicle_types: Sequence[VehicleTypeSpec]) -> None:
    """Decision D6: driver ``i`` (generation order) takes slot ``floor(i * len(slots) / n)``.

    Only ``capacity`` and ``attrs`` change — the random draws of the scenario are untouched.
    """
    slots = _fleet_slots(fleets, vehicle_types)
    n = len(scenario.drivers)
    if not slots or not n:
        return
    for i, d in enumerate(scenario.drivers):
        fl, vt = slots[i * len(slots) // n]
        d.capacity = vt.seats
        d.attrs["fleet_id"] = fl.name
        d.attrs["vehicle_type"] = vt.name
        d.attrs["vehicle_group"] = vt.group      # used on the network when the scenario declares vehicle_groups
    scenario.tags["fleets"] = {fl.name: fl.size() for fl in fleets}


def _zone_weights(spec: ScenarioSpec, src: ZonalSourceSpec, net):
    """Zone weights of a ``zonal`` source: the given file, else ``zone_weights.csv`` next to the zone file."""
    if src.weights:
        return read_zone_weights(_data_file(src.weights, net))
    if isinstance(spec.zones, FileZoneSpec):
        p = Path(spec.zones.name)
        folder = p.parent if p.is_file() else (Path(getattr(net, "data_root", "")) / "zones" / spec.zones.name /
                                               getattr(net, "name", ""))
        if (folder / "zone_weights.csv").exists():
            return read_zone_weights(folder / "zone_weights.csv")
    return None


def build_scenario(spec: ScenarioSpec, seed: Optional[int] = None, fleets: Sequence[FleetSpec] = (),
                   vehicle_types: Sequence[VehicleTypeSpec] = (), world=None) -> Scenario:
    net, zones = world or build_world(spec)
    builder = ScenarioBuilder(net, zones, traffic=spec.traffic.kwargs(lambda p: _data_file(p, net)))
    seed = spec.seed if seed is None else seed
    n_drivers = sum(fl.size() for fl in fleets) if fleets else spec.n_drivers
    src = spec.source
    if isinstance(src, PresetSourceSpec):
        sc = builder.preset(src.preset, seed=seed, demand_per_hour=src.demand_per_hour, n_drivers=n_drivers,
                            **src.synthetic_kwargs())
    elif isinstance(src, SyntheticSourceSpec):
        sc = builder.synthetic(name=spec.name, seed=seed, n_drivers=n_drivers, **src.synthetic_kwargs())
    elif isinstance(src, FleetPyDemandSourceSpec):
        sc = builder.from_fleetpy_demand(_data_file(src.file, net), name=spec.name, seed=seed, n_drivers=n_drivers,
                                         t_start=src.t_start, t_end=src.t_end, time_offset=src.time_offset,
                                         capacity=src.capacity)
    elif isinstance(src, ZonalSourceSpec):
        sc = builder.zonal(name=spec.name, seed=seed, n_drivers=n_drivers, weights=_zone_weights(spec, src, net),
                           **src.zonal_kwargs())
    elif isinstance(src, CsvSourceSpec):
        sc = builder.from_csv(_data_file(src.file, net), name=spec.name, seed=seed, n_drivers=n_drivers,
                              time_col=src.time_col, origin=tuple(src.origin), dest=tuple(src.dest),
                              coords=src.coords, t_start=src.t_start, t_end=src.t_end)
    else:
        raise TypeError(f"unknown source spec {src!r}")
    if fleets:
        apply_fleets(sc, fleets, vehicle_types)
    return sc


def build_policy_from_spec(spec: PolicySpec, overrides: Optional[Dict[str, Any]] = None) -> Policy:
    kw = dict(spec.params, **(overrides or {}))
    if kw.get("matching") is not None:
        kw["matching"] = MatchingParams(**kw["matching"])
    return POLICIES[spec.plugin](**kw)


def build_policy(group: PolicyGroupSpec) -> Policy:
    """Decision D5: 0 enabled members → ``Baseline()``; 1 → the policy itself; ≥ 2 → ``Composite`` in order."""
    members = []
    for m in group.members:
        if not m.enabled:
            continue
        if isinstance(m.policy, Ref):
            raise SpecError([("policy_group.members", "tham chiếu DB chưa được giải (dùng Repository.resolve)")])
        members.append(build_policy_from_spec(m.policy, m.params))
    if not members:
        return Baseline()
    if len(members) == 1:
        return members[0]
    return Composite(*members)


def build_model(spec: ModelSpec):
    cls = _model_classes()[spec.cls]
    p = spec.params
    if spec.cls in WRAPPERS:
        return cls(build_model(ModelSpec.from_dict(p["inner"])), p["factor"])
    if spec.cls == "TransitionMatrixIdleMove":
        fb = p.get("fallback")
        return cls(p["matrix"], build_model(ModelSpec.from_dict(fb)) if fb else None)
    pc = model_params_class(cls)
    if pc is None:
        return cls()
    return cls(pc(**p))


def build_behavior(spec: BehaviorSpec) -> BehaviorSuite:
    suite = BehaviorSuite.employed_drivers() if spec.preset == "employed_drivers" else BehaviorSuite()
    if spec.registry:
        reg = ModelRegistry(spec.registry)
        slots = dict(spec.slots) or {p.name: "latest" for p in Path(spec.registry).iterdir()
                                     if p.is_dir() and p.name in SLOTS}
        suite = reg.suite(slots, base=suite)
    if spec.models:
        suite = suite.replace(**{slot: build_model(m) for slot, m in spec.models.items()})
    return suite


def build_sim_config(spec: SimConfigSpec) -> SimConfig:
    kw = dict(spec.values)
    if "fare" in kw:
        kw["fare"] = FareModel(**kw["fare"])
    if "pooling" in kw:
        kw["pooling"] = PoolingParams(**kw["pooling"])
    if "shared_ride" in kw:
        from kami.shared.config import SharedRideConfig
        shared = dict(kw["shared_ride"])
        shared.pop("fare_factor", None)
        kw["shared_ride"] = SharedRideConfig(**shared)
    kw.setdefault("timeseries_interval_s", DEFAULT_TIMESERIES_INTERVAL_S)
    return SimConfig(**kw)


@dataclass
class BuiltRun:
    scenario: Scenario
    policy: Policy
    behavior: BehaviorSuite
    config: SimConfig
    crn_seed: Optional[int]

    def simulation(self) -> Simulation:
        return Simulation(self.scenario, self.policy, self.behavior, self.config, crn_seed=self.crn_seed)


def _require_resolved(spec: RunSpec) -> None:
    if spec.has_refs():
        raise SpecError([("", "RunSpec còn tham chiếu DB ({\"ref\": ...}); giải bằng Repository.resolve trước khi "
                              "chạy")])


def build_run(spec: RunSpec) -> BuiltRun:
    _require_resolved(spec)
    sc = build_scenario(spec.scenario, seed=spec.seed, fleets=spec.fleets, vehicle_types=spec.vehicle_types)
    config = build_sim_config(spec.sim_config)
    if config.shared_ride.enabled:
        from kami.core.crn import CRN
        crn = CRN(sc.seed)
        sc = sc.with_(requests=[replace(r, attrs=dict(r.attrs, service_preference=
                      config.shared_ride.preference(r.attrs, r.id, crn))) for r in sc.requests])
    if spec.outputs.trajectories != "none" or spec.outputs.replay == "json":
        config.record_trajectories = True
    return BuiltRun(sc, build_policy(spec.policy_group), build_behavior(spec.behavior), config, spec.crn_seed)


def run_spec(spec: RunSpec) -> Simulation:
    """Build and run; returns the finished ``Simulation``."""
    return build_run(spec).simulation().run()
