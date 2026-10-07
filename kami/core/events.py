"""Event catalogue (design doc §4.3) and the heap entry used by the engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class EventType(str, Enum):
    # Rider
    REQUEST_CREATED = "REQUEST_CREATED"
    OFFER_SHOWN = "OFFER_SHOWN"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    OFFER_REJECTED = "OFFER_REJECTED"
    RIDER_CANCEL = "RIDER_CANCEL"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    # Driver
    DRIVER_ONLINE = "DRIVER_ONLINE"
    DRIVER_OFFLINE = "DRIVER_OFFLINE"
    TRIP_OFFERED = "TRIP_OFFERED"
    TRIP_ACCEPTED = "TRIP_ACCEPTED"
    TRIP_REJECTED = "TRIP_REJECTED"
    ARRIVE_STOP = "ARRIVE_STOP"          # driver reached the next stop of its plan (pickup or dropoff)
    IDLE_MOVE = "IDLE_MOVE"              # driver decides where to go while idle
    IDLE_ARRIVE = "IDLE_ARRIVE"          # idle/reposition move finished
    CHARGE_START = "CHARGE_START"        # reserved: EV charging (not implemented yet)
    CHARGE_END = "CHARGE_END"            # reserved: EV charging (not implemented yet)
    # Platform
    DISPATCH_TICK = "DISPATCH_TICK"
    REPOSITION_TICK = "REPOSITION_TICK"
    PRICE_UPDATE = "PRICE_UPDATE"
    # Policy
    POLICY_TIMER = "POLICY_TIMER"
    # Environment
    INCIDENT_START = "INCIDENT_START"
    INCIDENT_END = "INCIDENT_END"
    WEATHER_CHANGE = "WEATHER_CHANGE"
    TRAFFIC_UPDATE = "TRAFFIC_UPDATE"


# Same-timestamp ordering. Lower runs first. Rationale:
#   environment changes first (so every decision at t sees the world at t),
#   then agent movements that free capacity (drop-offs, arrivals),
#   then new demand, then platform batch decisions, then policy timers.
# Combined with the monotonically increasing sequence number this makes
# every run with the same scenario + seed fully reproducible.
EVENT_PRIORITY: Dict[EventType, int] = {
    EventType.WEATHER_CHANGE: 0,
    EventType.INCIDENT_START: 0,
    EventType.INCIDENT_END: 0,
    EventType.TRAFFIC_UPDATE: 0,
    EventType.DRIVER_OFFLINE: 1,
    EventType.DRIVER_ONLINE: 1,
    EventType.ARRIVE_STOP: 2,
    EventType.IDLE_ARRIVE: 2,
    EventType.RIDER_CANCEL: 3,
    EventType.REQUEST_CREATED: 4,
    EventType.IDLE_MOVE: 5,
    EventType.PRICE_UPDATE: 6,
    EventType.DISPATCH_TICK: 7,
    EventType.REPOSITION_TICK: 8,
    EventType.POLICY_TIMER: 9,
}
DEFAULT_PRIORITY = 5


@dataclass(order=True)
class Event:
    """Heap entry ``(time, priority, seq)``; ``kind`` and ``payload`` are not compared."""

    time: float
    priority: int
    seq: int
    kind: EventType = field(compare=False)
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)
