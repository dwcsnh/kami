"""kami — agent-based, discrete-event simulator for evaluating ride-hailing policies.

Quick start::

    from kami import GridNetwork, SquareZoneSystem, ScenarioBuilder, Simulation, PoolAfterWait
    net = GridNetwork(); zones = SquareZoneSystem(net, 1000)
    sc = ScenarioBuilder(net, zones).preset("weekday_am_peak", seed=1)
    sim = Simulation(sc, PoolAfterWait()).run()
    print(sim.metrics())
"""
from kami.behavior import BehaviorSuite, ModelRegistry
from kami.core import CRN, EventType, SimConfig, Simulation
from kami.metrics import compute as compute_metrics
from kami.network import (FileZoneSystem, FleetPyNetwork, FleetPyZoneSystem, GridNetwork, H3ZoneSystem, RoadNetwork,
                          SquareZoneSystem)
from kami.policy import Baseline, Composite, HeatmapReposition, Policy, PoolAfterWait, SurgePricing
from kami.pricing import FareModel
from kami.shared import SharedRideConfig
from kami.scenario import PRESETS, Scenario, ScenarioBuilder
from kami.evaluation import (Condition, DecisionRule, Experiment, pooling_rule_example)

__version__ = "0.1.0"

__all__ = ["BehaviorSuite", "ModelRegistry", "CRN", "EventType", "SimConfig", "Simulation", "compute_metrics",
           "RoadNetwork", "FileZoneSystem", "FleetPyNetwork", "FleetPyZoneSystem", "GridNetwork", "H3ZoneSystem", "SquareZoneSystem", "Baseline",
           "Composite", "HeatmapReposition", "Policy", "PoolAfterWait", "SurgePricing", "FareModel", "PRESETS",
           "Scenario", "ScenarioBuilder", "SharedRideConfig", "Condition", "DecisionRule", "Experiment", "pooling_rule_example"]
