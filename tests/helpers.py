"""Shared fixtures: a small, fast synthetic world."""
from kami.network import GridNetwork, SquareZoneSystem
from kami.scenario import ScenarioBuilder

_NET = GridNetwork(5000, 5000, 250)
_ZONES = SquareZoneSystem(_NET, 1000)
BUILDER = ScenarioBuilder(_NET, _ZONES)


def small_scenario(seed=1, preset="weekday_am_peak", demand=120, drivers=40, **kw):
    return BUILDER.preset(preset, seed=seed, demand_per_hour=demand, n_drivers=drivers, t_end=8.5 * 3600, **kw)


def assert_metrics_equal(tc, a, b):
    """Every metric identical (NaN == NaN)."""
    import math

    tc.assertEqual(sorted(a), sorted(b))
    for k in a:
        if isinstance(a[k], float) and math.isnan(a[k]):
            tc.assertTrue(math.isnan(b[k]), k)
        else:
            tc.assertEqual(a[k], b[k], k)


def small_run_spec(preset="weekday_am_peak", policy="baseline", args=None, seed=1, **kw):
    """RunSpec equivalent of ``small_scenario`` (5 km grid, 1 h window) + ``POLICIES[policy](**args)``."""
    from kami.config import spec_from_cli
    from kami.scenario import PRESETS

    t_end = PRESETS[preset]["t_start"] + 3600
    kw = dict(dict(demand=120, drivers=40, grid_km=5), **kw)
    return spec_from_cli(preset, policy, args or {}, seed=seed, overrides={"t_end": t_end}, **kw)
