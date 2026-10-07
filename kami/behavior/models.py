"""Default, interpretable behaviour models (design doc §6.3: simple first).

All parameters live in a ``params`` dataclass so a model can be saved to and
loaded from the model registry as JSON. Default values are **assumptions**
chosen to give plausible baselines on synthetic data; replace them with
fitted checkpoints (see ``kami.training``) before trusting magnitudes.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Dict, Hashable, List, Optional, Tuple

from kami.behavior.protocols import Context, TripOffer


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class Model:
    """Base: a model is ``params`` + pure functions of (agent, situation, context)."""

    params: object

    def to_dict(self) -> Dict:
        return asdict(self.params) if self.params is not None else {}


# --------------------------------------------------------------------------- rider
@dataclass
class LogitBookingParams:
    asc: float = 3.0
    b_surge: float = 2.0         # per unit of (surge - 1), scaled by rider price sensitivity
    b_eta: float = 0.15          # per minute of quoted ETA
    b_surcharge: float = 0.3     # per 10k VND of extra charge


class LogitBooking(Model):
    """Book or not after seeing fare/ETA (Cohen et al. style price elasticity)."""

    def __init__(self, params: Optional[LogitBookingParams] = None, **kw):
        self.params = params or LogitBookingParams(**kw)

    def p_book(self, rider, quote, ctx: Context) -> float:
        p = self.params
        sens = rider.attrs.get("price_sens", 1.0)
        u = (p.asc - p.b_surge * sens * (quote.surge - 1.0) - p.b_eta * quote.eta / 60.0
             - p.b_surcharge * sens * quote.surcharge / 10_000)
        return sigmoid(u)


@dataclass
class WeibullCancelParams:
    shape: float = 1.2               # k > 1 increasing hazard; k < 1 "sunk waiting time" effect
    b_eta: float = 0.05              # hazard multiplier exp(b_eta * (eta_shown - eta_ref))
    eta_ref: float = 5.0             # minutes
    weather_multiplier: Dict[str, float] = field(default_factory=lambda: {"rain": 1.15, "heavy_rain": 1.3})


class WeibullCancel(Model):
    """Waiting-phase cancellation hazard; scale = rider's own patience (minutes)."""

    def __init__(self, params: Optional[WeibullCancelParams] = None, **kw):
        self.params = params or WeibullCancelParams(**kw)

    def hazard(self, rider, waited_min: float, eta_shown: float, ctx: Context) -> float:
        p = self.params
        lam = max(rider.attrs.get("patience_min", 10.0), 0.1)
        k = p.shape
        base = (k / lam) * (max(waited_min, 1e-6) / lam) ** (k - 1)
        mult = math.exp(p.b_eta * (eta_shown - p.eta_ref))
        mult *= p.weather_multiplier.get(ctx.weather, 1.0) * ctx.incident_cancel_multiplier
        return base * mult


@dataclass
class OverrunCancelParams:
    base: float = 0.008              # per minute while the driver is on time
    b_overrun: float = 0.25          # growth per minute the driver is late vs. the promise
    weather_multiplier: Dict[str, float] = field(default_factory=lambda: {"rain": 1.1, "heavy_rain": 1.2})


class OverrunCancel(Model):
    """Matched-phase cancellation: low baseline, grows when the promised ETA is exceeded."""

    def __init__(self, params: Optional[OverrunCancelParams] = None, **kw):
        self.params = params or OverrunCancelParams(**kw)

    def hazard(self, rider, waited_min: float, eta_shown: float, ctx: Context) -> float:
        p = self.params
        overdue = max(0.0, -eta_shown)
        h = p.base * math.exp(p.b_overrun * overdue)
        return h * p.weather_multiplier.get(ctx.weather, 1.0) * ctx.incident_cancel_multiplier


@dataclass
class LogitPoolAcceptParams:
    asc: float = -1.0
    b_wait: float = 0.15             # per minute already waited (impatience makes pooling attractive)
    b_price: float = 0.5             # per 10k VND surcharge, scaled by price sensitivity
    b_detour: float = 0.1            # per minute of expected detour


class LogitPoolAccept(Model):
    """Accept a pooling offer. **No empirical data for surcharges** (design doc §14.1)."""

    def __init__(self, params: Optional[LogitPoolAcceptParams] = None, **kw):
        self.params = params or LogitPoolAcceptParams(**kw)

    def p_accept(self, rider, offer, ctx: Context) -> float:
        p = self.params
        sens = rider.attrs.get("price_sens", 1.0)
        u = (p.asc + p.b_wait * offer.waited / 60.0 - p.b_price * sens * offer.surcharge / 10_000
             - p.b_detour * offer.detour / 60.0 + rider.attrs.get("pool_willingness", 0.0))
        return sigmoid(u)


# --------------------------------------------------------------------------- driver
@dataclass
class LogitDriverAcceptParams:
    asc: float = 3.0
    b_pickup: float = 0.25           # per minute of pickup ETA
    b_fare: float = 1.0              # per 100k VND payout


class LogitDriverAccept(Model):
    """Accept/reject a trip offer (Ashkrof et al.)."""

    def __init__(self, params: Optional[LogitDriverAcceptParams] = None, **kw):
        self.params = params or LogitDriverAcceptParams(**kw)

    def p_accept(self, driver, offer: TripOffer, ctx: Context) -> float:
        p = self.params
        u = (p.asc - p.b_pickup * offer.pickup_eta / 60.0 + p.b_fare * offer.fare / 100_000
             + driver.attrs.get("accept_bias", 0.0))
        return sigmoid(u)


class AlwaysAccept(Model):
    """Employed drivers (no right to refuse) — see design doc §6.2 open question."""

    params = None

    def p_accept(self, driver, offer, ctx) -> float:
        return 1.0


@dataclass
class HomeBiasIdleParams:
    p_stay: float = 0.6
    w_home: float = 0.25             # weight of heading back to the home zone
    min_idle_s: float = 120          # informational: engine waits this long before deciding


class HomeBiasIdleMove(Model):
    """Stay, drift to a neighbour zone, or return to the home zone."""

    def __init__(self, params: Optional[HomeBiasIdleParams] = None, **kw):
        self.params = params or HomeBiasIdleParams(**kw)

    def distribution(self, driver, ctx: Context, zones) -> List[Tuple[Optional[Hashable], float]]:
        p = self.params
        here = ctx.zone
        out: List[Tuple[Optional[Hashable], float]] = [(None, p.p_stay)]
        rest = 1.0 - p.p_stay
        home = driver.home_zone
        if home is not None and home != here:
            out.append((home, rest * p.w_home))
            rest *= 1.0 - p.w_home
        nbrs = zones.neighbors(here)
        for z in nbrs:
            out.append((z, rest / len(nbrs)))
        if not nbrs:
            out[0] = (None, 1.0)
        return out


class TransitionMatrixIdleMove(Model):
    """Uber-style zone→zone transition matrix by hour, learned from GPS (see training.fit).

    ``matrix[str(hour)][str(zone)] = {str(next_zone) | "stay": prob}``; unknown cells fall back.
    """

    def __init__(self, matrix: Dict, fallback: Optional[Model] = None):
        self.params = None
        self.matrix = matrix
        self.fallback = fallback or HomeBiasIdleMove()

    def to_dict(self) -> Dict:
        return {"matrix": self.matrix}

    def distribution(self, driver, ctx: Context, zones):
        row = self.matrix.get(str(ctx.hour), {}).get(str(ctx.zone))
        if not row:
            return self.fallback.distribution(driver, ctx, zones)
        by_str = {str(z): z for z in zones.zones()}
        out = []
        for z, prob in row.items():
            if z == "stay" or z == str(ctx.zone):
                out.append((None, prob))
            elif z in by_str:
                out.append((by_str[z], prob))
        return out


class ScheduledShift(Model):
    """Drivers follow the scenario's shift times exactly."""

    params = None

    def p_stop(self, driver, ctx) -> float:
        return 0.0


@dataclass
class IncomeTargetParams:
    target: float = 800_000          # VND per shift
    p_stop_after_target: float = 0.3


class IncomeTargetShift(Model):
    """Simple labour-supply model: may log off early after reaching a daily income target."""

    def __init__(self, params: Optional[IncomeTargetParams] = None, **kw):
        self.params = params or IncomeTargetParams(**kw)

    def p_stop(self, driver, ctx) -> float:
        tgt = driver.attrs.get("income_target", self.params.target)
        return self.params.p_stop_after_target if driver.earnings >= tgt else 0.0


# --------------------------------------------------------------------------- wrappers
class ProbabilityScaler(Model):
    """Multiply a probability model's output (sensitivity analysis, design doc §11).

    ``ProbabilityScaler(LogitPoolAccept(), 1.5)`` = "riders accept pooling 50% more often".
    """

    def __init__(self, inner: Model, factor: float):
        self.params = None
        self.inner, self.factor = inner, factor

    def to_dict(self):
        return {"factor": self.factor, "inner": type(self.inner).__name__}

    def _scale(self, p: float) -> float:
        return min(1.0, max(0.0, p * self.factor))

    def p_accept(self, *a, **k) -> float:
        return self._scale(self.inner.p_accept(*a, **k))

    def p_book(self, *a, **k) -> float:
        return self._scale(self.inner.p_book(*a, **k))

    def p_stop(self, *a, **k) -> float:
        return self._scale(self.inner.p_stop(*a, **k))


class HazardScaler(Model):
    """Multiply a hazard model (e.g. riders 30% more impatient)."""

    def __init__(self, inner: Model, factor: float):
        self.params = None
        self.inner, self.factor = inner, factor

    def hazard(self, *a, **k) -> float:
        return self.inner.hazard(*a, **k) * self.factor
