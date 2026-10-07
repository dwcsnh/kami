from kami.network.base import Network, SpatialIndex
from kami.network.grid import GridNetwork
from kami.network.zones import ZoneSystem, SquareZoneSystem, H3ZoneSystem, FleetPyZoneSystem


def FleetPyNetwork(*args, **kwargs):  # lazy import: FleetPy deps are only needed when used
    from kami.network.fleetpy_network import FleetPyNetwork as _F
    return _F(*args, **kwargs)


__all__ = ["Network", "SpatialIndex", "GridNetwork", "FleetPyNetwork", "ZoneSystem",
           "SquareZoneSystem", "H3ZoneSystem", "FleetPyZoneSystem"]
