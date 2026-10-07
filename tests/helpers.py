"""Shared fixtures: a small, fast synthetic world."""
from kami.network import GridNetwork, SquareZoneSystem
from kami.scenario import ScenarioBuilder

_NET = GridNetwork(5000, 5000, 250)
_ZONES = SquareZoneSystem(_NET, 1000)
BUILDER = ScenarioBuilder(_NET, _ZONES)


def small_scenario(seed=1, preset="weekday_am_peak", demand=120, drivers=40, **kw):
    return BUILDER.preset(preset, seed=seed, demand_per_hour=demand, n_drivers=drivers, t_end=8.5 * 3600, **kw)
