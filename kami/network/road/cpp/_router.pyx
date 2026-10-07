# distutils: language = c++
# cython: language_level=3
"""Cython wrapper of the C++ Dijkstra router.

Port of FleetPy's ``cpp_router/PyNetwork.pyx`` (MIT licence, TUM-VT, see LICENSE-FleetPy). Differences: buffers are
``std::vector`` instead of numpy arrays (no numpy needed to build or run) and paths are ``str`` or ``bytes``.
"""
from libcpp.string cimport string
from libcpp.vector cimport vector



cdef string _b(path):
    return path if isinstance(path, bytes) else str(path).encode()


cdef class PyNetwork:
    cdef Network* c_net

    def __cinit__(self, node_path, edge_path):
        """Load ``nodes.csv`` / ``edges.csv`` of a network ``base`` folder."""
        self.c_net = new Network(_b(node_path), _b(edge_path))

    def __dealloc__(self):
        del self.c_net

    def updateEdgeTravelTimes(self, file_path):
        """Apply a CSV with columns ``from_node,to_node,edge_tt``."""
        self.c_net.updateEdgeTravelTimes(_b(file_path))

    cdef list _many(self, int start, targets, max_time_range, max_targets, bint forward):
        cdef vector[int] tg = list(targets)
        cdef int n = tg.size()
        if n == 0:
            return []
        cdef vector[int] reached = vector[int](n)
        cdef vector[double] tts = vector[double](n)
        cdef vector[double] dis = vector[double](n)
        cdef double mr = -1.0 if max_time_range is None else max_time_range
        cdef int mt = -1 if max_targets is None else max_targets
        cdef int k
        if forward:
            k = self.c_net.computeTravelCosts1ToXpy(start, n, tg.data(), reached.data(), tts.data(), dis.data(), mr, mt)
        else:
            k = self.c_net.computeTravelCostsXTo1py(start, n, tg.data(), reached.data(), tts.data(), dis.data(), mr, mt)
        return [(reached[i], tts[i], dis[i]) for i in range(k)]

    def computeTravelCostsXto1(self, start_node_index, list_target_node_indices, max_time_range=None, max_targets=None):
        """Backward search from ``start_node_index``: list of ``(origin, tt, dis)`` for reached origins."""
        return self._many(start_node_index, list_target_node_indices, max_time_range, max_targets, False)

    def computeTravelCosts1toX(self, start_node_index, list_target_node_indices, max_time_range=None, max_targets=None):
        """Forward search from ``start_node_index``: list of ``(target, tt, dis)`` for reached targets."""
        return self._many(start_node_index, list_target_node_indices, max_time_range, max_targets, True)

    def computeTravelCosts1To1(self, start_node_index, end_node_index):
        """``(tt, dis)``; ``(-1.0, -1.0)`` if no route exists."""
        cdef double dis = 0.0
        cdef double tt = 0.0
        self.c_net.computeTravelCosts1To1py(start_node_index, end_node_index, &tt, &dis)
        return (tt, dis)

    def computeRoute1To1(self, start_node_index, end_node_index):
        """Node list of the fastest route (empty if none)."""
        cdef int n = self.c_net.computeRouteSize1to1(start_node_index, end_node_index)
        cdef vector[int] route
        if n < 0:
            return []
        route = vector[int](max(n, 1))
        if n > 0:
            self.c_net.writeRoute(route.data())
        return [route[i] for i in range(n)]
