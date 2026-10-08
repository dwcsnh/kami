"""Reference look-ups on a replay (sprint 03): the state and position of a vehicle at time ``t``.

The web app implements the same rules in TypeScript (``web/src/data/replay.ts``); its tests compare with samples
written by this module (``tests/data/replay/make_web_samples.py``).

* segment at ``t``: the segment of the vehicle with ``t0 ≤ t < t1`` (the last one also at ``t = t1``);
* position: linear interpolation between the two points around ``t``, clamped to the first / last point.
"""
from __future__ import annotations

from bisect import bisect_right
from typing import Any, Dict, List, Optional, Tuple


class ReplayIndex:
    def __init__(self, trips: Dict[str, list]):
        self.trips = trips
        self._by_vehicle: Dict[Any, List[int]] = {}
        for i, v in enumerate(trips["vehicle"]):
            self._by_vehicle.setdefault(v, []).append(i)
        self._t0 = {v: [trips["t0"][i] for i in idx] for v, idx in self._by_vehicle.items()}

    def vehicles(self) -> List[Any]:
        return list(self._by_vehicle)

    def segment_at(self, vehicle, t: float) -> Optional[int]:
        idx = self._by_vehicle.get(vehicle)
        if not idx:
            return None
        k = bisect_right(self._t0[vehicle], t) - 1
        if k < 0:
            return None
        i = idx[k]
        t1 = self.trips["t1"][i]
        if t < t1 or (k == len(idx) - 1 and t == t1):
            return i
        return None

    def state_at(self, vehicle, t: float) -> Optional[str]:
        i = self.segment_at(vehicle, t)
        return None if i is None else self.trips["state"][i]

    def position_at(self, vehicle, t: float) -> Optional[Tuple[float, float]]:
        i = self.segment_at(vehicle, t)
        if i is None:
            return None
        return position_in(self.trips["path"][i], self.trips["ts"][i], t)


def position_in(path: List[float], ts: List[float], t: float) -> Tuple[float, float]:
    n = len(ts)
    if n == 1 or t <= ts[0]:
        return path[0], path[1]
    if t >= ts[-1]:
        return path[2 * n - 2], path[2 * n - 1]
    k = bisect_right(ts, t) - 1            # ts[k] ≤ t < ts[k + 1]
    t0, t1 = ts[k], ts[k + 1]
    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    x0, y0, x1, y1 = path[2 * k], path[2 * k + 1], path[2 * k + 2], path[2 * k + 3]
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
