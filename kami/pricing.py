"""Fare model: rider price, driver payout and platform take (design doc §7.3 "Giá" group)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FareModel:
    """Distance/time tariff in VND. ``surge`` multiplies the metered part."""

    base: float = 12_000
    per_km: float = 9_000
    per_min: float = 400
    min_fare: float = 25_000
    take_rate: float = 0.25          # platform commission on the rider payment
    surcharge_to_driver: float = 0.0 # share of a pooling surcharge passed to the driver

    def fare(self, dist_m: float, tt_s: float, surge: float = 1.0) -> float:
        metered = self.base + self.per_km * dist_m / 1000.0 + self.per_min * tt_s / 60.0
        return round(max(self.min_fare, metered * surge), -2)

    def driver_payout(self, fare: float, surcharge: float = 0.0) -> float:
        return fare * (1.0 - self.take_rate) + max(surcharge, 0.0) * self.surcharge_to_driver

    def platform_revenue(self, fare: float, surcharge: float = 0.0) -> float:
        """Rider payment minus driver payout (a negative surcharge = discount paid by the platform)."""
        return fare + surcharge - self.driver_payout(fare, surcharge)
