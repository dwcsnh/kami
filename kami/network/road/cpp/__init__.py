"""C++ Dijkstra router (optional extension, ported from FleetPy's ``cpp_router``).

Build once with ``python -m kami.network.road.cpp.build`` (needs Cython and a C++17 compiler).
``PyNetwork`` is ``None`` when the extension is not built; ``RoadNetwork`` then uses the pure-Python router.
"""
try:
    from kami.network.road.cpp._router import PyNetwork
except ImportError:  # extension not built
    PyNetwork = None

__all__ = ["PyNetwork"]
