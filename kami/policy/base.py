"""Policy plug-in interface (design doc §7.1).

A policy reacts to engine hooks and acts **only** through the engine API
(``sim.schedule``, ``sim.offer_trip``, ``sim.assign``, ``sim.merge_jobs``,
``sim.reposition``, ``sim.set_surge`` …). It never edits agent state directly,
so the same engine runs baseline and treatment unchanged.

Every hook has a sensible default, therefore ``Policy()`` *is* the baseline:
batch matching every ``batch_window`` seconds, metered fares, no pooling,
no platform repositioning.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Hashable, Iterable, List, Optional, Tuple

from kami.matching import MatchingParams

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.agents import Driver, Job, Quote, Rider
    from kami.core.engine import Simulation


class Policy:
    name: str = "baseline"
    #: periodic platform ticks, e.g. {"REPOSITION_TICK": 300, "PRICE_UPDATE": 120}
    tick_intervals: Dict[str, float] = {}

    def __init__(self, matching: Optional[MatchingParams] = None, batch_window: Optional[float] = None):
        self.matching = matching or MatchingParams()
        self.batch_window = batch_window      # None -> SimConfig.batch_window

    # ---- lifecycle ---------------------------------------------------------
    def on_start(self, sim: "Simulation") -> None:
        """Called once before the first event."""

    def on_end(self, sim: "Simulation") -> None:
        """Called once after the last event."""

    # ---- rider side ----------------------------------------------------------
    def price(self, sim: "Simulation", rider: "Rider", quote: "Quote") -> "Quote":
        """Return the quote shown to the rider (override for surge / upfront pricing)."""
        return quote

    def on_request(self, sim: "Simulation", rider: "Rider") -> None:
        """A rider has just booked (state WAITING)."""

    def on_timer(self, sim: "Simulation", rider: Optional["Rider"], **payload) -> None:
        """A ``POLICY_TIMER`` scheduled by this policy fired."""

    def on_rider_cancel(self, sim: "Simulation", rider: "Rider") -> None:
        """A rider cancelled (waiting or matched)."""

    def on_dropoff(self, sim: "Simulation", rider: "Rider", driver: "Driver") -> None:
        """Trip completed."""

    # ---- dispatch ------------------------------------------------------------
    def on_dispatch(self, sim: "Simulation", open_jobs: List["Job"],
                    idle_drivers: List["Driver"]) -> Optional[Iterable[Tuple["Job", "Driver"]]]:
        """Return (job, driver) pairs to offer; the engine runs the driver-acceptance step.

        Return ``None`` if the policy already called ``sim.offer_trip`` / ``sim.assign`` itself.
        """
        return sim.default_dispatch(open_jobs, idle_drivers, self.matching)

    # ---- supply side -----------------------------------------------------------
    def on_driver_idle(self, sim: "Simulation", driver: "Driver") -> Optional[int]:
        """Return a node to *direct* an idle driver there, or None to let the driver decide."""
        return None

    def on_tick(self, sim: "Simulation", kind: str) -> None:
        """Periodic ``REPOSITION_TICK`` / ``PRICE_UPDATE`` declared in ``tick_intervals``."""

    def describe(self) -> Dict:
        return {"name": self.name, "class": type(self).__name__, "matching": vars(self.matching)}
