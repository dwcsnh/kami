"""Fixed interfaces of every decision point (design doc §6).

Models return *probabilities* (or hazards / distributions) and never draw
random numbers themselves. The engine turns them into decisions with the
agent's own CRN number (``u < p``), which keeps baseline and treatment
paired no matter which model is plugged in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Optional, Protocol, Sequence, Tuple, runtime_checkable


@dataclass
class Context:
    """Exogenous situation at the decision moment."""

    t: float
    hour: int
    weather: str = "clear"
    zone: Hashable = None
    incident_cancel_multiplier: float = 1.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TripOffer:
    """What a driver sees when a trip is offered (input of DriverAcceptModel)."""

    pickup_eta: float      # seconds
    fare: float            # driver-side payout estimate
    trip_dist: float       # metres
    dest_zone: Hashable = None
    pooled: bool = False


@runtime_checkable
class BookingModel(Protocol):
    def p_book(self, rider, quote, ctx: Context) -> float: ...


@runtime_checkable
class RiderCancelModel(Protocol):
    def hazard(self, rider, waited_min: float, eta_shown: float, ctx: Context) -> float:
        """Cancellation hazard per minute. ``eta_shown`` is minutes until promised pickup
        (can be negative when the driver is late)."""


@runtime_checkable
class PoolAcceptModel(Protocol):
    def p_accept(self, rider, offer, ctx: Context) -> float: ...


@runtime_checkable
class DriverAcceptModel(Protocol):
    def p_accept(self, driver, offer: TripOffer, ctx: Context) -> float: ...


@runtime_checkable
class IdleMoveModel(Protocol):
    def distribution(self, driver, ctx: Context, zones) -> List[Tuple[Optional[Hashable], float]]:
        """``[(zone or None for 'stay', weight), …]`` for an idle driver."""


@runtime_checkable
class DriverShiftModel(Protocol):
    def p_stop(self, driver, ctx: Context) -> float:
        """Probability of ending the shift now (evaluated whenever the driver becomes idle)."""
