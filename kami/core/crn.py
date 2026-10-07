"""Common Random Numbers (design doc §2 principle 6, §6, §10.1).

Every stochastic decision in kami draws its uniform number from a
*counter-based* generator keyed by ``(seed, stream, *keys)`` instead of a
shared sequential RNG. A key names "this agent, this decision, this
occasion", e.g. ``("pool_accept", rider_id, offer_no)``.

Why counter-based instead of pre-generating arrays: the number a rider uses
for "do I cancel?" must not depend on how many random numbers *other*
agents consumed before it. With a shared ``random.Random`` a policy that
changes the order of decisions would silently re-shuffle every later draw
and destroy the pairing between baseline and treatment. Hashing the key
gives exactly the "pre-generated per-agent per-decision number" semantics
of the design without having to know the number of draws in advance.
"""
from __future__ import annotations

import hashlib
import math
from typing import Hashable

_INV_2_53 = 1.0 / (1 << 53)


class CRN:
    """Deterministic uniform/exponential draws keyed by name.

    ``CRN(seed).u("cancel_wait", rider_id)`` always returns the same value in
    (0, 1) for the same seed, regardless of call order or process.
    """

    __slots__ = ("seed", "_prefix")

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._prefix = f"kami|{self.seed}|".encode()

    def u(self, stream: str, *keys: Hashable) -> float:
        """Uniform in the open interval (0, 1)."""
        msg = self._prefix + stream.encode() + b"|" + "|".join(map(str, keys)).encode()
        x = int.from_bytes(hashlib.blake2b(msg, digest_size=8).digest(), "little")
        return ((x >> 11) + 0.5) * _INV_2_53

    def exp(self, stream: str, *keys: Hashable) -> float:
        """Standard exponential draw (mean 1); used as a cumulative-hazard budget."""
        return -math.log(self.u(stream, *keys))

    def normal(self, stream: str, *keys: Hashable) -> float:
        """Standard normal draw via Box-Muller on two keyed uniforms."""
        u1 = self.u(stream, *keys, "n1")
        u2 = self.u(stream, *keys, "n2")
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def choice_index(self, weights, stream: str, *keys: Hashable) -> int:
        """Inverse-CDF categorical draw; ``weights`` need not be normalised."""
        total = float(sum(weights))
        if total <= 0:
            return 0
        target = self.u(stream, *keys) * total
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if target < acc:
                return i
        return len(weights) - 1

    def child(self, offset: int) -> "CRN":
        """Independent generator (used to *disable* CRN in variance experiments)."""
        return CRN(self.seed * 1_000_003 + offset)
