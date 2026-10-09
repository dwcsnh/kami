"""Demo toàn bộ vòng đời Shared V1 trên đường Hà Nội; mọi mốc do engine tạo.

Dữ liệu minh họa: hai khách chắc chắn đặt, không hủy, một tài xế nhận chuyến.
Đây là giả định để quan sát quy trình, không phải hành vi GreenSM đã hiệu chỉnh.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kami import BehaviorSuite, SharedRideConfig, SimConfig, Simulation, SquareZoneSystem
from kami.network import RoadNetwork
from kami.scenario import DriverSpec, RequestSpec, Scenario
from kami.replay import export


class DemoBooking:
    def p_book(self, *args):
        return 1.0


class DemoNoCancel:
    def hazard(self, *args):
        return 0.0


def build_demo():
    net = RoadNetwork("hanoi", backend="python")
    scenario = Scenario("shared-v1-walkthrough", 7, 25200, 26100, net, SquareZoneSystem(net, 500),
        [RequestSpec(1, 25210, 313, 12616, {"service_preference": "shared_only"}),
         RequestSpec(2, 25230, 389, 85, {"service_preference": "shared_only"})],
        [DriverSpec(1, 49, 25200, 26100, 4, {"group": "car"})],
        traffic={"hour_profile": [1.0] * 24})
    behavior = BehaviorSuite.employed_drivers().replace(booking=DemoBooking(),
        cancel_wait=DemoNoCancel(), cancel_matched=DemoNoCancel())
    return Simulation(scenario, behavior=behavior, config=SimConfig(batch_window=60,
        shared_ride=SharedRideConfig(enabled=True), idle_decision_s=10000, drain_s=0,
        record_trajectories=True, timeseries_interval_s=10))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="web/public/fixtures/shared_v1_walkthrough")
    args = parser.parse_args()
    sim = build_demo().run()
    export(sim, args.out, run={"name": "Shared V1 — từ đặt xe đến trả khách (minh họa)", "seed": 7})
    for r in sim.riders.values():
        print(r.id, r.state.value, "booked", r.t_booked, "pickup", r.t_pickup, "dropoff", r.t_dropoff)
    print("Replay:", args.out)
