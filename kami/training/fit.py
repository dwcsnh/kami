"""Offline fitting of behaviour models → registry checkpoints (design doc §2 principle 7, §13 phase 2).

Intentionally dependency-free and simple; real pipelines can replace any of
these as long as they write a checkpoint the registry can load.

* ``fit_weibull_cancel``        – survival MLE on (waited minutes, cancelled?) with right-censoring
* ``fit_logit``                 – logistic regression by Newton/IRLS (pool accept, driver accept, booking)
* ``fit_transition_matrix``     – zone→zone idle movement probabilities per hour from GPS segments
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Hashable, Iterable, List, Sequence, Tuple


def fit_weibull_cancel(records: Iterable[Tuple[float, bool]], shapes: Sequence[float] = None) -> Dict[str, float]:
    """MLE of a Weibull hazard with right-censoring.

    :param records: (duration_min, event) — event=True if the rider cancelled at that time,
                    False if observation ended without cancel (matched / still waiting).
    :return: {"shape": k, "scale_min": λ, "loglik": ℓ}. Use ``scale_min`` as the mean of
             riders' ``patience_min`` attribute (``ScenarioBuilder.rider_attrs``).
    """
    data = [(max(t, 1e-3), bool(e)) for t, e in records]
    d = sum(e for _, e in data)
    if d == 0:
        raise ValueError("no cancellation events")
    best = None
    for k in shapes or [0.5 + 0.05 * i for i in range(51)]:
        lam_k = sum(t ** k for t, _ in data) / d          # closed-form λ^k given k
        lam = lam_k ** (1 / k)
        ll = sum((math.log(k) - k * math.log(lam) + (k - 1) * math.log(t)) for t, e in data if e) \
            - sum((t / lam) ** k for t, _ in data)
        if best is None or ll > best["loglik"]:
            best = {"shape": k, "scale_min": lam, "loglik": ll}
    return best


def fit_logit(X: Sequence[Sequence[float]], y: Sequence[int], names: Sequence[str], l2: float = 1e-4,
              iters: int = 50) -> Dict[str, float]:
    """Logistic regression with intercept ``asc`` (Newton–Raphson, small ridge for stability).

    Returns ``{"asc": b0, names[0]: b1, …}``. Map signs onto model params, e.g. for
    ``LogitPoolAccept`` fit on features [waited_min, surcharge/10k, detour_min] and set
    ``b_wait=b1, b_price=-b2, b_detour=-b3``.
    """
    n, p = len(X), len(names) + 1
    rows = [[1.0] + list(map(float, x)) for x in X]
    beta = [0.0] * p
    for _ in range(iters):
        g = [0.0] * p
        H = [[0.0] * p for _ in range(p)]
        for xi, yi in zip(rows, y):
            z = sum(b * v for b, v in zip(beta, xi))
            mu = 1 / (1 + math.exp(-max(min(z, 30), -30)))
            w = mu * (1 - mu)
            for a in range(p):
                g[a] += (yi - mu) * xi[a]
                for b in range(p):
                    H[a][b] += w * xi[a] * xi[b]
        for a in range(p):
            g[a] -= l2 * beta[a]
            H[a][a] += l2
        step = _solve(H, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return dict(zip(["asc", *names], beta))


def _solve(A: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def fit_transition_matrix(moves: Iterable[Tuple[int, Hashable, Hashable]], min_count: int = 5,
                          smoothing: float = 0.5) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Idle-driver movement matrix by hour (Uber-style, design doc §6.2).

    :param moves: (hour, from_zone, to_zone) for each idle GPS segment; to_zone == from_zone means "stayed".
    :return: ``{str(hour): {str(zone): {"stay" | str(next_zone): prob}}}`` for ``TransitionMatrixIdleMove``.
    """
    counts: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for h, a, b in moves:
        counts[str(h)][str(a)]["stay" if a == b else str(b)] += 1
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for h, rows in counts.items():
        for z, row in rows.items():
            total = sum(row.values())
            if total < min_count:
                continue
            denom = total + smoothing * len(row)
            out.setdefault(h, {})[z] = {k: (v + smoothing) / denom for k, v in row.items()}
    return out
