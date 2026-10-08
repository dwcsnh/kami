"""Traffic layer (design doc §8).

Travel time = base network time (incident-aware routing)
              × time-of-day factor × weather factor.

Level 1 (default): time-dependent multipliers (hour profile × weather).
Level 2: incidents as exogenous events — ``INCIDENT_START`` adds a slowdown
         factor on every node of the affected zones; routing avoids them and
         drivers already on the road are re-timed by the engine.
Level 3 (SUMO co-simulation) is out of scope for the engine itself.

"Plan vs. reality" (FleetPy idea, design doc §4.2): the platform's ETA can
be computed with ``aware=False`` (it does not yet know about incidents) while
the actual drive uses full information, producing measurable ETA errors.

Sprint 02 (both off by default, kami 0.1 behaviour unchanged):

* ``congestion`` — zone × hour congestion (``kami.congestion.CongestionModel``) replaces the city-wide hour
  profile. It is a *state* set per period by ``apply_period`` (the engine calls it at every ``CONGESTION_UPDATE``),
  like FleetPy's time-dependent travel-time folders: on a ``RoadNetwork`` the edge travel times of every vehicle
  group are re-set, on a grid the factors enter routing as node factors. The platform's estimate sees congestion
  (historical knowledge) but, as before, not incidents.
* ``vehicle_groups`` — per-group speed factor, congestion scale and forbidden edges (``"car"``, ``"bike"``).
  Queries take ``group=``; groups that are not declared behave as ``"car"``. Without ``vehicle_groups`` every
  vehicle is a car.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Set, Tuple

from kami.congestion import DEFAULT_VEHICLE_GROUPS, CongestionModel, VehicleGroup, build_congestion
from kami.network.base import Network
from kami.network.zones import ZoneSystem

DEFAULT_GROUP = "car"

# Congestion multiplier per hour of day (1.0 = free flow). Peaks at 7-9h and 17-19h.
DEFAULT_HOUR_PROFILE = [0.85, 0.85, 0.85, 0.85, 0.9, 1.0, 1.15, 1.45, 1.5, 1.3, 1.15, 1.15,
                        1.2, 1.15, 1.15, 1.2, 1.35, 1.55, 1.6, 1.4, 1.2, 1.05, 0.95, 0.9]
DEFAULT_WEATHER_FACTOR = {"clear": 1.0, "rain": 1.25, "heavy_rain": 1.5}


@dataclass
class Incident:
    id: str
    zones: Set[Hashable]
    factor: float                 # travel-time multiplier inside the zones
    cancel_multiplier: float = 1.5  # hazard multiplier for riders waiting in the zones


class TrafficLayer:
    def __init__(self, network: Network, zones: ZoneSystem,
                 hour_profile: Optional[Sequence[float]] = None,
                 weather_factor: Optional[Dict[str, float]] = None,
                 platform_sees_incidents: bool = False,
                 congestion=None,
                 vehicle_groups: Optional[Dict[str, object]] = None):
        self.network = network
        self.zones = zones
        self.hour_profile = list(hour_profile or DEFAULT_HOUR_PROFILE)
        self.weather_factor = dict(DEFAULT_WEATHER_FACTOR, **(weather_factor or {}))
        self.platform_sees_incidents = platform_sees_incidents
        self.weather = "clear"
        self.incidents: Dict[str, Incident] = {}
        self._zone_factor: Dict[Hashable, float] = {}
        self._version = 0
        self._cache: Dict[Tuple[int, int, int], Tuple[float, float]] = {}
        # stateful fast path (RoadNetwork C++ backend): incidents live inside a second router
        self._live = bool(getattr(network, "supports_live_factors", False))
        # sprint 02: vehicle groups and zone × hour congestion
        self.vehicle_groups: Dict[str, VehicleGroup] = {}
        for g, p in (vehicle_groups or {}).items():
            if isinstance(p, VehicleGroup):
                self.vehicle_groups[g] = p
            else:
                base = DEFAULT_VEHICLE_GROUPS.get(g, VehicleGroup())
                self.vehicle_groups[g] = VehicleGroup(**dict(vars(base), **(p or {})))
        self.congestion: Optional[CongestionModel] = None
        if congestion is not None:
            self.congestion = build_congestion(congestion).bind(network, zones)
        self._edge_groups = bool(getattr(network, "supports_groups", False))
        self._groups_on = bool(self.vehicle_groups) or self.congestion is not None
        self.hour: Optional[int] = None            # congestion hour in force (None = no congestion state yet)
        self._node_cong: Dict[str, Dict[int, float]] = {}   # grid: congestion node factors per group
        self.activate()

    def activate(self) -> None:
        """Put the network in this layer's state (free flow / group speeds, no incidents).

        The network object may be shared by several simulations (``build_world`` cache), so ``Simulation.run`` calls
        this before the first event.
        """
        if self._edge_groups:
            self.network.reset_groups()
        self.hour = None
        if self._groups_on:
            self.apply_period(None)
        if self.incidents:
            self._rebuild()

    # --- vehicle groups ------------------------------------------------------
    def group(self, group: Optional[str]) -> str:
        """Effective group: declared groups keep their name, anything else is ``"car"``."""
        return group if group in self.vehicle_groups else DEFAULT_GROUP

    def _vg(self, group: str) -> VehicleGroup:
        return self.vehicle_groups.get(group) or DEFAULT_VEHICLE_GROUPS[DEFAULT_GROUP]

    def _net_kw(self, group: str) -> Dict[str, str]:
        return {"group": group} if self._edge_groups and group != DEFAULT_GROUP else {}

    def _speed(self, group: str) -> float:
        """Travel-time multiplier applied outside the network (grids: no per-group routers)."""
        if self._edge_groups:
            return 1.0
        return 1.0 / self._vg(group).speed_factor

    # --- state changes (called by the engine) -----------------------------
    def set_weather(self, weather: str):
        self.weather = weather

    def start_incident(self, inc: Incident):
        self.incidents[inc.id] = inc
        self._rebuild()

    def end_incident(self, inc_id: str):
        self.incidents.pop(inc_id, None)
        self._rebuild()

    def _rebuild(self):
        zf: Dict[Hashable, float] = {}
        for inc in self.incidents.values():
            for z in inc.zones:
                zf[z] = max(zf.get(z, 1.0), inc.factor)
        self._zone_factor = zf
        self._version += 1
        self._cache.clear()
        if self._live:
            nf = {n: f for z, f in zf.items() for n in self.zones.nodes_in(z)}
            for g in self._groups_in_use():
                self.network.apply_live_factors(nf, **self._net_kw(g))

    def _groups_in_use(self) -> List[str]:
        return [DEFAULT_GROUP] + [g for g in self.vehicle_groups if g != DEFAULT_GROUP]

    def apply_period(self, t: Optional[float]) -> bool:
        """Set the congestion state of the period containing ``t`` (None: free flow / groups only).

        Returns True when travel times changed.
        """
        hour = None if (t is None or self.congestion is None) else self.congestion.hour(t)
        if hour == self.hour and t is not None:
            return False
        self.hour = hour
        cong = self.congestion if hour is not None else None
        for g in self._groups_in_use():
            vg = self._vg(g)
            if self._edge_groups:
                factors = cong.edge_factors(hour, vg.congestion_scale) if cong else None
                if vg.speed_factor != 1.0:
                    k = 1.0 / vg.speed_factor
                    factors = [f * k for f in factors] if factors else [k] * len(self.network.edge_list())
                self.network.set_edge_factors(g, factors)
            elif cong is not None:
                scale = vg.congestion_scale
                self._node_cong[g] = {n: cong.node_factor(n, hour, scale) for n in self.network.nodes()}
            else:
                self._node_cong.pop(g, None)
        self._version += 1
        self._cache.clear()
        return True

    # --- queries -----------------------------------------------------------
    def multiplier(self, t: float) -> float:
        w = self.weather_factor.get(self.weather, 1.0)
        if self.congestion is not None:            # decision D11: zone × hour replaces the hour profile
            return w
        return self.hour_profile[int(t // 3600) % 24] * w

    def node_factor(self, aware: bool = True, group: str = DEFAULT_GROUP):
        """Routing node factor: incidents (if ``aware``) × congestion on networks without per-group routers."""
        cong = self._node_cong.get(group) if self._node_cong else None
        inc = self._zone_factor if (self._zone_factor and aware) else None
        if cong is None:
            if inc is None:
                return None
            zf, zone_of = inc, self.zones.zone_of
            return lambda n: zf.get(zone_of(n), 1.0)
        if inc is None:
            return cong.__getitem__
        zone_of = self.zones.zone_of
        return lambda n: cong[n] * inc.get(zone_of(n), 1.0)

    def _base(self, o: int, d: int, aware: bool) -> Tuple[float, float]:
        """kami 0.1 path (no vehicle groups, no congestion)."""
        nf = self.node_factor(aware)
        if nf is None:
            return self.network.base_travel(o, d)
        if self._live:
            return self.network.live_travel(o, d)
        key = (o, d, self._version)
        hit = self._cache.get(key)
        if hit is None:
            hit = self.network.base_travel(o, d, nf)
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[key] = hit
        return hit

    def _base_g(self, o: int, d: int, aware: bool, group: str) -> Tuple[float, float]:
        kw = self._net_kw(group)
        nf = self.node_factor(aware, group)
        if nf is None:
            return self.network.base_travel(o, d, **kw)
        if self._live:     # live routers exist on RoadNetwork only, where congestion is in the edge times
            return self.network.live_travel(o, d, **kw)
        key = (o, d, self._version, group)
        hit = self._cache.get(key)
        if hit is None:
            hit = self.network.base_travel(o, d, nf, **kw)
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[key] = hit
        return hit

    def travel(self, o: int, d: int, t: float, aware: bool = True, group: str = DEFAULT_GROUP) -> Tuple[float, float]:
        """(seconds, metres) driving from o to d departing at t (``group``: vehicle group of the driver)."""
        if not self._groups_on:
            tt, dist = self._base(o, d, aware)
            return tt * self.multiplier(t), dist
        group = self.group(group)
        tt, dist = self._base_g(o, d, aware, group)
        return tt * self.multiplier(t) * self._speed(group), dist

    def estimate(self, o: int, d: int, t: float, group: str = DEFAULT_GROUP) -> Tuple[float, float]:
        """Platform-side ETA (may ignore incidents, see ``platform_sees_incidents``)."""
        return self.travel(o, d, t, self.platform_sees_incidents, group)

    def many_to_one(self, origins: Sequence[int], d: int, t: float, max_tt: Optional[float] = None,
                    aware: bool = True, group: str = DEFAULT_GROUP) -> Dict[int, Tuple[float, float]]:
        if not self._groups_on:
            m = self.multiplier(t)
            cap = None if max_tt is None else max_tt / m
            nf = self.node_factor(aware)
            if nf is not None and self._live:
                raw = self.network.live_many_to_one(origins, d, cap)
            else:
                raw = self.network.many_to_one(origins, d, nf, cap)
            return {o: (tt * m, dist) for o, (tt, dist) in raw.items()}
        group = self.group(group)
        m = self.multiplier(t) * self._speed(group)
        cap = None if max_tt is None else max_tt / m
        kw = self._net_kw(group)
        nf = self.node_factor(aware, group)
        if nf is not None and self._live:
            raw = self.network.live_many_to_one(origins, d, cap, **kw)
        else:
            raw = self.network.many_to_one(origins, d, nf, cap, **kw)
        return {o: (tt * m, dist) for o, (tt, dist) in raw.items()}

    def path(self, o: int, d: int, group: str = DEFAULT_GROUP) -> List[Tuple[int, float]]:
        """Actual (incident-aware) route as [(node, cumulative base seconds)]."""
        if not self._groups_on:
            nf = self.node_factor(True)
            if nf is not None and self._live:
                return self.network.live_path(o, d)
            return self.network.path(o, d, nf)
        group = self.group(group)
        kw = self._net_kw(group)
        nf = self.node_factor(True, group)
        if nf is not None and self._live:
            return self.network.live_path(o, d, **kw)
        return self.network.path(o, d, nf, **kw)

    # --- context for behaviour models ---------------------------------------
    def incident_at(self, node: int) -> Optional[Incident]:
        if not self.incidents:
            return None
        z = self.zones.zone_of(node)
        for inc in self.incidents.values():
            if z in inc.zones:
                return inc
        return None
