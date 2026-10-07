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
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Set, Tuple

from kami.network.base import Network
from kami.network.zones import ZoneSystem

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
                 platform_sees_incidents: bool = False):
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
            self.network.apply_live_factors(nf)

    # --- queries -----------------------------------------------------------
    def multiplier(self, t: float) -> float:
        return self.hour_profile[int(t // 3600) % 24] * self.weather_factor.get(self.weather, 1.0)

    def node_factor(self, aware: bool = True):
        if not self._zone_factor or not aware:
            return None
        zf, zone_of = self._zone_factor, self.zones.zone_of
        return lambda n: zf.get(zone_of(n), 1.0)

    def _base(self, o: int, d: int, aware: bool) -> Tuple[float, float]:
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

    def travel(self, o: int, d: int, t: float, aware: bool = True) -> Tuple[float, float]:
        """(seconds, metres) driving from o to d departing at t."""
        tt, dist = self._base(o, d, aware)
        return tt * self.multiplier(t), dist

    def estimate(self, o: int, d: int, t: float) -> Tuple[float, float]:
        """Platform-side ETA (may ignore incidents, see ``platform_sees_incidents``)."""
        return self.travel(o, d, t, aware=self.platform_sees_incidents)

    def many_to_one(self, origins: Sequence[int], d: int, t: float, max_tt: Optional[float] = None,
                    aware: bool = True) -> Dict[int, Tuple[float, float]]:
        m = self.multiplier(t)
        cap = None if max_tt is None else max_tt / m
        nf = self.node_factor(aware)
        if nf is not None and self._live:
            raw = self.network.live_many_to_one(origins, d, cap)
        else:
            raw = self.network.many_to_one(origins, d, nf, cap)
        return {o: (tt * m, dist) for o, (tt, dist) in raw.items()}

    def path(self, o: int, d: int) -> List[Tuple[int, float]]:
        """Actual (incident-aware) route as [(node, cumulative base seconds)]."""
        nf = self.node_factor(True)
        if nf is not None and self._live:
            return self.network.live_path(o, d)
        return self.network.path(o, d, nf)

    # --- context for behaviour models ---------------------------------------
    def incident_at(self, node: int) -> Optional[Incident]:
        if not self.incidents:
            return None
        z = self.zones.zone_of(node)
        for inc in self.incidents.values():
            if z in inc.zones:
                return inc
        return None
