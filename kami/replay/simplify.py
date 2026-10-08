"""Space-time simplification of a timed polyline (sprint 03, S03-2, decision D6).

The browser interpolates a vehicle linearly in space *and* time between two kept points, so a point may only be
dropped when both the position and the timing it encodes are reproduced: point ``k`` between kept points ``i`` and
``j`` is redundant when its distance to the chord ``i→j`` is ≤ ``dist_m`` and the time at which the chord passes its
projection differs from ``t_k`` by ≤ ``dt_s``. Douglas–Peucker style: split at the worst point until every dropped
point satisfies both bounds. The first and last points are always kept; repeated points (same place and time) go.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

M_PER_DEG = 111_320.0


def simplify(xs: Sequence[float], ys: Sequence[float], ts: Sequence[float], dist_m: float = 1.0,
             dt_s: float = 0.5, lonlat: bool = True) -> List[int]:
    """Indices of the points to keep (sorted, first and last included)."""
    n = len(xs)
    if n <= 2:
        return list(range(n))
    if lonlat:
        lat0 = math.radians(sum(ys) / n)
        kx, ky = M_PER_DEG * math.cos(lat0), M_PER_DEG
    else:
        kx = ky = 1.0
    px = [x * kx for x in xs]
    py = [y * ky for y in ys]
    # drop exact repeats first (zero-length steps carry no information unless the time differs)
    idx = [0]
    for k in range(1, n):
        p = idx[-1]
        if px[k] == px[p] and py[k] == py[p] and ts[k] == ts[p]:
            continue
        idx.append(k)
    if idx[-1] != n - 1:
        if len(idx) == 1:
            idx.append(n - 1)
        else:
            idx[-1] = n - 1
    if len(idx) <= 2:
        return idx
    keep = [False] * len(idx)
    keep[0] = keep[-1] = True
    stack: List[Tuple[int, int]] = [(0, len(idx) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ia, ib = idx[a], idx[b]
        ax, ay, at = px[ia], py[ia], ts[ia]
        dx, dy, dt = px[ib] - ax, py[ib] - ay, ts[ib] - at
        l2 = dx * dx + dy * dy
        worst, worst_k = 1.0, -1
        for m in range(a + 1, b):
            k = idx[m]
            qx, qy = px[k] - ax, py[k] - ay
            if l2 > 0:
                u = (qx * dx + qy * dy) / l2
                uc = 0.0 if u < 0 else 1.0 if u > 1 else u
                d = math.hypot(qx - uc * dx, qy - uc * dy)
                t_hat = at + uc * dt
            else:
                # chord of zero length: the vehicle stands still from a to b; time follows linearly
                d = math.hypot(qx, qy)
                t_hat = ts[k]
            score = max(d / dist_m if dist_m > 0 else (math.inf if d > 0 else 0.0),
                        abs(ts[k] - t_hat) / dt_s if dt_s > 0 else (math.inf if ts[k] != t_hat else 0.0))
            if score > worst:
                worst, worst_k = score, m
        if worst_k >= 0:
            keep[worst_k] = True
            stack.append((a, worst_k))
            stack.append((worst_k, b))
    return [idx[m] for m in range(len(idx)) if keep[m]]


def max_deviation(xs, ys, ts, kept: Sequence[int], lonlat: bool = True) -> Tuple[float, float]:
    """Largest distance (m) and time error (s) of the dropped points w.r.t. the kept polyline (for tests)."""
    if lonlat and xs:
        lat0 = math.radians(sum(ys) / len(ys))
        kx, ky = M_PER_DEG * math.cos(lat0), M_PER_DEG
    else:
        kx = ky = 1.0
    worst_d = worst_t = 0.0
    for a, b in zip(kept[:-1], kept[1:]):
        ax, ay, at = xs[a] * kx, ys[a] * ky, ts[a]
        dx, dy, dt = xs[b] * kx - ax, ys[b] * ky - ay, ts[b] - at
        l2 = dx * dx + dy * dy
        for k in range(a + 1, b):
            qx, qy = xs[k] * kx - ax, ys[k] * ky - ay
            if l2 > 0:
                u = max(0.0, min(1.0, (qx * dx + qy * dy) / l2))
                worst_d = max(worst_d, math.hypot(qx - u * dx, qy - u * dy))
                worst_t = max(worst_t, abs(ts[k] - (at + u * dt)))
            else:
                worst_d = max(worst_d, math.hypot(qx, qy))
    return worst_d, worst_t
