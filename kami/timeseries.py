"""Time-series metrics (sprint 01, S01-6): periodic snapshots of the main metrics during a run.

Enabled by ``SimConfig(timeseries_interval_s=300)``; the result is ``sim.timeseries.rows``,
one dict per mark ``t_start + k·Δ`` plus a final row at the end of the run. The snapshot
at mark ``m`` is the state after every event with time ``< m``. The sampler adds no
event to the queue and draws no random number, so results are identical with it on or off.

Columns (times in minutes, money in VND):

* window ``[m − Δ, m)``: ``rider.requests``, ``rider.booked``, ``rider.completed``,
  ``rider.cancelled``, ``rider.wait_mean``, ``rider.wait_p90``, ``rider.pickup_mean`` (pickups in the window;
  ``pickup_mean`` = trip accepted → pickup, sprint 03),
  ``platform.gmv``, ``platform.surge_mean`` (quotes shown in the window);
* cumulative since the start: ``rider.*_cum``, ``platform.gmv_cum``;
* state at ``m``: ``rider.waiting_now``, ``driver.online``, ``driver.idle`` (parked),
  ``driver.repositioning`` (idle and driving: own idle move or platform repositioning),
  ``driver.en_route``, ``driver.on_trip``, ``driver.utilization_now`` (on_trip / online).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from kami.core.agents import DriverState, RiderState
from kami.metrics import mean, percentile

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.engine import Simulation

NaN = float("nan")
COUNTERS = ("requests", "booked", "completed", "cancelled")
COLUMNS = (["t"] + [f"rider.{c}" for c in COUNTERS] + [f"rider.{c}_cum" for c in COUNTERS] +
           ["rider.waiting_now", "rider.wait_mean", "rider.wait_p90", "rider.pickup_mean",
            "driver.online", "driver.idle", "driver.repositioning", "driver.en_route", "driver.on_trip",
            "driver.utilization_now", "platform.gmv", "platform.gmv_cum", "platform.surge_mean"])


class MetricSampler:
    def __init__(self, sim: "Simulation", interval_s: float):
        if interval_s <= 0:
            raise ValueError("timeseries interval must be > 0")
        self.sim = sim
        self.interval = float(interval_s)
        self.t0 = sim.scenario.t_start
        self._k = 0
        self.next_mark = self.t0
        self.rows: List[Dict[str, float]] = []
        self._win = dict.fromkeys(COUNTERS, 0)
        self._cum = dict.fromkeys(COUNTERS, 0)
        self._waits: List[float] = []
        self._pickups: List[float] = []
        self._matched: Dict[int, float] = {}
        self._gmv = 0.0
        self._gmv_cum = 0.0
        self._surge_sum = 0.0
        self._quotes = 0
        self._waiting: Set[int] = set()
        sim.log.subscribe(self._on_event)

    # ------------------------------------------------------------------ input
    def _on_event(self, t: float, ev: str, rider_id: Optional[int], driver_id: Optional[int],
                  info: Dict[str, Any]) -> None:
        if ev == "REQUEST_CREATED":
            self._win["requests"] += 1
        elif ev == "OFFER_SHOWN":
            self._surge_sum += info.get("surge", 1.0)
            self._quotes += 1
        elif ev == "OFFER_ACCEPTED":
            self._win["booked"] += 1
            self._waiting.add(rider_id)
        elif ev == "TRIP_ACCEPTED":
            self._matched[rider_id] = t
        elif ev == "PICKUP":
            self._waits.append(info.get("wait", 0.0) / 60.0)
            t_matched = self._matched.pop(rider_id, None)
            if t_matched is not None:
                self._pickups.append((t - t_matched) / 60.0)
        elif ev == "DROPOFF":
            self._win["completed"] += 1
            fare = info.get("fare", 0.0) + info.get("surcharge", 0.0)
            self._gmv += fare
        elif ev == "RIDER_CANCEL":
            self._win["cancelled"] += 1
            self._matched.pop(rider_id, None)

    # ------------------------------------------------------------------ sampling
    def sample_until(self, t: float) -> float:
        """Snapshot every mark ``≤ t``; return the next mark."""
        while self.next_mark <= t:
            self._sample(self.next_mark)
            self._k += 1
            self.next_mark = self.t0 + self._k * self.interval
        return self.next_mark

    def finish(self, t: float) -> None:
        """Marks up to ``t`` and a final row at ``t`` (end of the run) unless ``t`` is itself a mark."""
        self.sample_until(t)
        if not self.rows or self.rows[-1]["t"] < t:
            self._sample(t)

    def _sample(self, mark: float) -> None:
        sim = self.sim
        riders = sim.riders
        self._waiting = {r for r in self._waiting if riders[r].state == RiderState.WAITING}
        online = idle = moving = en_route = on_trip = 0
        for d in sim.drivers.values():
            s = d.state
            if s == DriverState.OFFLINE:
                continue
            online += 1
            if s == DriverState.IDLE:
                if d.leg is None:
                    idle += 1
                else:
                    moving += 1
            elif s == DriverState.EN_ROUTE:
                en_route += 1
            elif s == DriverState.ON_TRIP:
                on_trip += 1
        for c in COUNTERS:
            self._cum[c] += self._win[c]
        self._gmv_cum += self._gmv
        row: Dict[str, float] = {"t": mark}
        row.update({f"rider.{c}": self._win[c] for c in COUNTERS})
        row.update({f"rider.{c}_cum": self._cum[c] for c in COUNTERS})
        row.update({
            "rider.waiting_now": len(self._waiting),
            "rider.wait_mean": mean(self._waits),
            "rider.wait_p90": percentile(self._waits, 90),
            "rider.pickup_mean": mean(self._pickups),
            "driver.online": online, "driver.idle": idle, "driver.repositioning": moving,
            "driver.en_route": en_route, "driver.on_trip": on_trip,
            "driver.utilization_now": on_trip / online if online else NaN,
            "platform.gmv": self._gmv, "platform.gmv_cum": self._gmv_cum,
            "platform.surge_mean": self._surge_sum / self._quotes if self._quotes else NaN,
        })
        self.rows.append(row)
        self._win = dict.fromkeys(COUNTERS, 0)
        self._waits = []
        self._pickups = []
        self._gmv = 0.0
        self._surge_sum, self._quotes = 0.0, 0

    # ------------------------------------------------------------------ output
    def series(self, name: str) -> List[float]:
        return [r[name] for r in self.rows]

    def to_json(self, path: str | Path) -> Path:
        """JSON list of rows; NaN is written as ``null``."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
                 for r in self.rows]
        path.write_text(json.dumps(clean, indent=1))
        return path

    def to_csv(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(self.rows)
        return path
