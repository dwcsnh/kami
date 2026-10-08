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


# --------------------------------------------------------------------------- sprint 02: OSM fixture / Hà Nội network
OSM_FIXTURE_CONFIG = __import__("pathlib").Path(__file__).resolve().parent / "data" / "osm" / "hoan_kiem.json"
_FIXTURE_ROOT = []


def osm_build_deps() -> bool:
    """pyosmium + pyproj + h3 available (needed to *build* a network; reading one needs none of them)."""
    try:
        import h3  # noqa: F401
        import osmium  # noqa: F401
        import pyproj  # noqa: F401
    except ImportError:
        return False
    return True


def fixture_data_root():
    """Data root holding the Hồ Gươm fixture network ``hoan_kiem_fixture`` (built once per test process), or None."""
    if not _FIXTURE_ROOT:
        if not osm_build_deps():
            _FIXTURE_ROOT.append(None)
        else:
            import atexit
            import shutil
            import tempfile

            from kami.osm import build, load_config

            root = tempfile.mkdtemp(prefix="kami-osm-fixture-")
            atexit.register(shutil.rmtree, root, True)
            build(load_config(OSM_FIXTURE_CONFIG), root, log=lambda *a: None)
            _FIXTURE_ROOT.append(root)
    return _FIXTURE_ROOT[0]


def hanoi_built() -> bool:
    from kami.network.road import default_data_root

    return (default_data_root() / "networks" / "hanoi" / "base" / "nodes.csv").exists()


def cpp_router() -> bool:
    from kami.network.road.cpp import PyNetwork

    return PyNetwork is not None
