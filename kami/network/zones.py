"""Zone systems: the spatial unit for metrics, behaviour matrices, surge and incidents.

The design doc uses an H3 grid. ``h3`` is optional, so kami ships:

* ``SquareZoneSystem`` – square cells over planar coordinates (works everywhere)
* ``H3ZoneSystem``     – real H3 cells, needs ``pip install h3`` and a geo-referenced network
* ``FileZoneSystem``   – zone file ``<data_root>/zones/<name>/<network>/node_zone_info.csv`` (FleetPy layout;
  ``FleetPyZoneSystem`` is the kami 0.1 name)

All expose the same small API so the rest of the engine does not care.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, Hashable, List, Tuple

from kami.network.base import Network


class ZoneSystem:
    """Base class. Subclasses fill ``node_zone`` (node -> zone id)."""

    def __init__(self, network: Network):
        self.network = network
        self.node_zone: Dict[int, Hashable] = {}
        self._members: Dict[Hashable, List[int]] = {}
        self._centroid: Dict[Hashable, int] = {}
        self._neighbors: Dict[Hashable, List[Hashable]] = {}

    def _finalise(self, neighbor_radius_m: float):
        self._members = {}
        for n, z in self.node_zone.items():
            self._members.setdefault(z, []).append(n)
        locs = set(self.network.location_nodes())
        self._loc_members = {z: [n for n in ns if n in locs] for z, ns in self._members.items()}
        coords = self.network.coords
        centers = {}
        for z, ns in self._members.items():
            pts = [coords(n) for n in ns]
            cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            centers[z] = (cx, cy)
            cand = self._loc_members[z] or ns
            self._centroid[z] = min(cand, key=lambda n: (coords(n)[0] - cx) ** 2 + (coords(n)[1] - cy) ** 2)
        zs = list(centers)
        for z in zs:
            cx, cy = centers[z]
            self._neighbors[z] = [w for w in zs if w != z and
                                  math.hypot(centers[w][0] - cx, centers[w][1] - cy) <= neighbor_radius_m]
        self.centers = centers

    def zone_of(self, node: int) -> Hashable:
        return self.node_zone[node]

    def zones(self) -> List[Hashable]:
        return list(self._members)

    def nodes_in(self, zone: Hashable) -> List[int]:
        return self._members.get(zone, [])

    def location_nodes_in(self, zone: Hashable) -> List[int]:
        """Nodes of ``zone`` that are valid driving targets (see ``Network.location_nodes``)."""
        return self._loc_members.get(zone, [])

    def centroid_node(self, zone: Hashable) -> int:
        return self._centroid[zone]

    def neighbors(self, zone: Hashable) -> List[Hashable]:
        return self._neighbors.get(zone, [])

    def zones_within(self, node: int, radius_m: float) -> List[Hashable]:
        x, y = self.network.coords(node)
        return [z for z, (cx, cy) in self.centers.items() if math.hypot(cx - x, cy - y) <= radius_m]


class SquareZoneSystem(ZoneSystem):
    """Square cells of ``cell_m`` metres. Zone id = ``"i_j"``."""

    def __init__(self, network: Network, cell_m: float = 1000.0):
        super().__init__(network)
        self.cell = cell_m
        x0, y0, _, _ = network.bounds()
        for n in network.nodes():
            x, y = network.coords(n)
            self.node_zone[n] = f"{int((x - x0) // cell_m)}_{int((y - y0) // cell_m)}"
        self._finalise(neighbor_radius_m=cell_m * 1.5)


class H3ZoneSystem(ZoneSystem):
    """H3 cells at ``resolution`` (8 ≈ 0.7 km²). Requires ``h3`` and ``network.lonlat``."""

    def __init__(self, network: Network, resolution: int = 8):
        super().__init__(network)
        import h3  # optional dependency

        to_cell = getattr(h3, "latlng_to_cell", None) or getattr(h3, "geo_to_h3")
        for n in network.nodes():
            lonlat = network.lonlat(n)
            if lonlat is None:
                raise ValueError("H3ZoneSystem needs a geo-referenced network")
            self.node_zone[n] = to_cell(lonlat[1], lonlat[0], resolution)
        edge_m = {7: 1220, 8: 461, 9: 174}.get(resolution, 500)
        self._finalise(neighbor_radius_m=edge_m * 2.2)


class FileZoneSystem(ZoneSystem):
    """Zones read from ``node_zone_info.csv`` (columns ``node_index,zone_id``; negative ids are ignored).

    :param zone_system_name: folder under ``<data_root>/zones`` or path of a ``node_zone_info.csv`` file
    :param data_root: data folder (default: the road network's data root, else ``$KAMI_DATA_ROOT`` / ``<repo>/data``)
    :param fleetpy_root: kami 0.1 compatibility — folder containing ``data/``
    """

    def __init__(self, network: Network, zone_system_name: str = "example_zones", data_root=None,
                 neighbor_radius_m: float = 1500.0, fleetpy_root=None):
        super().__init__(network)
        from kami.network.road.network import resolve_data_root

        path = Path(zone_system_name)
        if not path.is_file():
            if data_root is None and fleetpy_root is None:
                data_root = getattr(network, "data_root", None)
            root = resolve_data_root(data_root, fleetpy_root)
            net_name = getattr(network, "name", "example_network")
            path = root / "zones" / str(zone_system_name) / net_name / "node_zone_info.csv"
        allowed = set(network.nodes())  # all nodes, including stop-only nodes
        with open(path) as f:
            for row in csv.DictReader(f):
                n = int(row["node_index"])
                if n in allowed and int(row["zone_id"]) >= 0:
                    self.node_zone[n] = int(row["zone_id"])
        # nodes missing from the zone file fall back to their nearest zoned node
        missing = allowed - set(self.node_zone)
        if missing:
            from kami.network.base import SpatialIndex

            idx = SpatialIndex({n: network.coords(n) for n in self.node_zone}, cell=250.0)
            for n in missing:
                self.node_zone[n] = self.node_zone[idx.nearest(*network.coords(n))]
        self._finalise(neighbor_radius_m=neighbor_radius_m)


FleetPyZoneSystem = FileZoneSystem   # kami 0.1 name
