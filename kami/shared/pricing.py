"""Discount sau minimum/làm tròn FareModel; không áp minimum lần hai."""
from kami.core.agents import Quote
from kami.shared.config import FARE_FACTOR


def shared_quote(reference: Quote, preference: str) -> Quote:
    fare = reference.fare
    if preference == "shared_only":
        # FareModel rounds to 100 VND. Integer arithmetic keeps VND exact.
        fare = int(reference.fare) * 7 / 10
    return Quote(fare, reference.eta, reference.surge, 0.0,
                 exclusive_reference_fare=reference.fare, service_preference=preference,
                 fare_factor=FARE_FACTOR if preference == "shared_only" else 1.0)
