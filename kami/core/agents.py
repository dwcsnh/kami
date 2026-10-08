"""Agents (design doc §5): Rider, Driver and the small value objects they share.

Agents only hold state. Every state transition is performed by the engine
(``kami.core.engine.Simulation``) so that policies cannot mutate agents
directly (design doc §7.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RiderState(str, Enum):
    REQUESTED = "REQUESTED"   # app opened, quote not yet answered
    DECLINED = "DECLINED"     # saw the quote and did not book (lost demand)
    WAITING = "WAITING"       # booked, no driver yet
    MATCHED = "MATCHED"       # driver assigned and on the way
    ONBOARD = "ONBOARD"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


TERMINAL_RIDER_STATES = {RiderState.DECLINED, RiderState.DONE, RiderState.CANCELLED}


class DriverState(str, Enum):
    OFFLINE = "OFFLINE"
    IDLE = "IDLE"             # available; may be cruising/repositioning (see Driver.leg)
    EN_ROUTE = "EN_ROUTE"     # driving to a pickup, nobody on board
    ON_TRIP = "ON_TRIP"       # at least one rider on board
    CHARGING = "CHARGING"     # reserved for EV support


@dataclass
class Quote:
    """What the rider sees before booking (and the platform's promise)."""

    fare: float
    eta: float                 # promised seconds until pickup
    surge: float = 1.0
    surcharge: float = 0.0


@dataclass
class PoolOffer:
    """A pooling proposal shown to a rider (input of PoolAcceptModel)."""

    surcharge: float           # extra money the rider pays (negative = discount)
    waited: float              # seconds already waited when the offer is shown
    detour: float = 0.0        # expected extra in-vehicle seconds
    partner_id: Optional[int] = None


@dataclass
class Stop:
    kind: str                  # "pickup" | "dropoff"
    rider_id: int
    loc: int


@dataclass
class Leg:
    """One continuous drive between two network locations."""

    origin: int
    dest: int
    t_depart: float
    t_arrive: float
    dist: float
    occupied: bool
    purpose: str               # "stop" | "idle" | "reposition"
    promised_arrive: Optional[float] = None  # platform's estimate (plan vs. reality)
    path: Optional[list] = field(default=None, repr=False)  # lazily computed [(node, cum_tt)]
    group: str = "car"         # vehicle group whose router drives the leg (sprint 02)
    rider_id: Optional[int] = None   # rider of the next stop (purpose "stop")


@dataclass
class Job:
    """Unit of dispatch: one rider, or several riders merged by a pooling policy."""

    id: int
    rider_ids: List[int]
    created_t: float
    tabu: Set[int] = field(default_factory=set)   # drivers that rejected this job
    driver_id: Optional[int] = None
    pooled: bool = False
    stops: List[Stop] = field(default_factory=list)  # planned stop order for pooled jobs


@dataclass
class Rider:
    id: int
    t_request: float
    origin: int
    dest: int
    attrs: Dict[str, Any] = field(default_factory=dict)
    state: RiderState = RiderState.REQUESTED
    version: int = 0                  # bumped on every state change (lazy invalidation)

    zone: Any = None
    dest_zone: Any = None
    direct_tt: float = 0.0
    direct_dist: float = 0.0

    quote: Optional[Quote] = None
    fare: float = 0.0                 # base fare after pricing policy
    surcharge: float = 0.0            # pooling surcharge (negative = discount)
    job_id: Optional[int] = None
    driver_id: Optional[int] = None
    pooled: bool = False
    pool_offers: int = 0
    pool_accepts: int = 0

    t_booked: Optional[float] = None
    t_matched: Optional[float] = None
    eta_promised: Optional[float] = None   # absolute time the platform promised for pickup
    t_pickup: Optional[float] = None
    t_dropoff: Optional[float] = None
    t_cancel: Optional[float] = None
    cancel_phase: Optional[str] = None     # "waiting" | "matched"

    # survival-model bookkeeping (see Simulation._schedule_cancel)
    hazard_budget: float = 0.0
    hazard_acc: float = 0.0
    hazard_t: float = 0.0
    hazard_phase: Optional[str] = None
    cancel_token: int = 0             # identifies the currently armed RIDER_CANCEL event

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_RIDER_STATES

    @property
    def fare_paid(self) -> float:
        return self.fare + self.surcharge if self.state == RiderState.DONE else 0.0


@dataclass
class Driver:
    id: int
    loc: int
    shift_start: float
    shift_end: float
    attrs: Dict[str, Any] = field(default_factory=dict)
    capacity: int = 4
    state: DriverState = DriverState.OFFLINE
    plan_version: int = 0
    plan: List[Stop] = field(default_factory=list)
    leg: Optional[Leg] = None
    onboard: Set[int] = field(default_factory=set)
    job_ids: List[int] = field(default_factory=list)
    going_offline: bool = False
    home_zone: Any = None
    group: str = "car"                # effective vehicle group on the network (sprint 02, attrs["vehicle_group"])
    legs: int = 0                     # legs driven so far (trajectory sequence number)

    # accounting
    t_online: Optional[float] = None
    online_time: float = 0.0
    busy_time: float = 0.0            # EN_ROUTE + ON_TRIP
    occupied_time: float = 0.0        # ON_TRIP
    dist_total: float = 0.0
    dist_empty: float = 0.0
    earnings: float = 0.0
    trips: int = 0
    offers: int = 0
    rejections: int = 0
    idle_since: Optional[float] = None
    idle_gaps: List[float] = field(default_factory=list)
    _state_since: float = 0.0
    idle_moves: int = 0

    @property
    def available(self) -> bool:
        return self.state == DriverState.IDLE and not self.going_offline
