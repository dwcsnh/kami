import unittest
from kami.core.agents import Driver, DriverState, Rider, Stop
from kami.shared.evaluate import Evaluator
from kami.shared.dispatch import candidate_pairs
from tests.shared_helpers import world
from tests.helpers import fixture_data_root, osm_build_deps


def prepared():
    sim=world();sim.traffic.activate()
    for spec in sim.scenario.requests:
        sim.riders[spec.id]=Rider(spec.id,0,spec.origin,spec.dest,pickup_deadline=600)
    d=Driver(1,0,0,3000,state=DriverState.IDLE)
    return sim,d,list(sim.riders.values())


class Evaluate(unittest.TestCase):
    def test_four_orders_and_individual_baseline_dwell(self):
        sim,d,rs=prepared();ev=Evaluator(sim);plans=ev.plans(d,rs)
        self.assertEqual(len(plans),4)
        for plan in plans:
            for r in rs:
                direct,_=sim.traffic.estimate(r.origin,r.dest,plan.pickup_t[r.id],group=d.group)
                self.assertEqual(plan.direct_baseline_s[r.id],30+direct)
                self.assertEqual(plan.extra_ride_s[r.id],max(0,plan.dropoff_t[r.id]-plan.pickup_t[r.id]-30-direct))
            self.assertGreater(plan.overlap_s,0)
        plan=plans[0]
        self.assertEqual(plan.pickup_t,{1:0,2:40})
        self.assertEqual(plan.dropoff_t,{1:160,2:190})
        self.assertEqual(plan.extra_ride_s,{1:30,2:20})

    def test_separate_extra_limits_exact_and_over(self):
        sim,d,rs=prepared();ev=Evaluator(sim)
        stops=[Stop('pickup',1,0),Stop('pickup',2,11),Stop('dropoff',1,110),Stop('dropoff',2,121)]
        sim.config.shared_ride.max_shared_extra_ride_s=30
        self.assertIsNotNone(ev.evaluate(d,rs,stops))
        sim.config.shared_ride.max_shared_extra_ride_s=29.999
        self.assertIsNone(ev.evaluate(d,rs,stops))
        stops[-2:]=list(reversed(stops[-2:]));sim.config.shared_ride.max_shared_extra_ride_s=70
        self.assertIsNotNone(ev.evaluate(d,rs,stops))
        sim.config.shared_ride.max_shared_extra_ride_s=69.999
        self.assertIsNone(ev.evaluate(d,rs,stops))

    def test_capacity_deadline_latest_commitments_unreachable_group(self):
        sim,d,rs=prepared();ev=Evaluator(sim)
        d.capacity=1;self.assertEqual(ev.plans(d,rs),[])
        d.capacity=2;rs[1].pickup_deadline=5;self.assertEqual(ev.plans(d,rs),[])
        rs[1].pickup_deadline=600;rs[0].attrs['latest_dropoff']=50;self.assertEqual(ev.plans(d,rs),[])
        rs[0].attrs={};rs[0].attrs['latest_pickup']=-1;self.assertEqual(ev.plans(d,rs),[])
        rs[0].attrs={}
        calls=[]
        def no_route(o,d,t,group):calls.append(group);return float('inf'),float('inf')
        sim.traffic.estimate=no_route;d.group='bike';self.assertEqual(Evaluator(sim).plans(d,rs),[]);self.assertEqual(calls,['bike','bike'])

    def test_endpoint_filter_keeps_v1_limitation(self):
        sim,d,rs=prepared();self.assertEqual(len(list(candidate_pairs(sim,rs))),1)
        rs[1].dest=sim.network.node_at(5,0) # on A's route but 500 m from D_A
        self.assertEqual(len(list(candidate_pairs(sim,rs))),1)
        rs[1].dest=sim.network.node_at(4,0) # 600 m from D_A, excluded
        self.assertEqual(list(candidate_pairs(sim,rs)),[])

    def test_overlap_zero_is_infeasible(self):
        sim,d,rs=prepared();sim.config.boarding_s=0;sim.config.alighting_s=0
        for r in rs:r.origin=r.dest=0
        self.assertEqual(Evaluator(sim).plans(d,rs),[])

    def test_exact_450_second_boundary_includes_other_boarding(self):
        sim,d,rs=prepared();sim.config.boarding_s=450;sim.config.alighting_s=0
        rs[1].origin=rs[0].origin;rs[1].dest=rs[0].dest
        sim.config.shared_ride.max_shared_extra_ride_s=450
        self.assertEqual(len(Evaluator(sim).plans(d,rs)),4)
        sim.config.shared_ride.max_shared_extra_ride_s=449.999
        self.assertEqual(Evaluator(sim).plans(d,rs),[])

    @unittest.skipUnless(osm_build_deps(), 'needs OSM fixture build dependencies')
    def test_osm_oneway_oracle_and_group_unreachable(self):
        import math
        from kami.network import RoadNetwork, SquareZoneSystem
        from kami.traffic import TrafficLayer
        net=RoadNetwork('hoan_kiem_fixture',data_root=fixture_data_root(),backend='python')
        zones=SquareZoneSystem(net,500)
        sim,d,rs=prepared();sim.network=net
        sim.traffic=TrafficLayer(net,zones,hour_profile=[1]*24,vehicle_groups={'car':{},'bike':{}})
        # A directed OSM edge with a longer reverse route, on common reachable nodes.
        locs=set(net.location_nodes())
        a,b=next((a,b) for a,b in net.graph.edges if a in locs and b in locs
                 and (b,a) not in net.graph.edges and net.base_travel(b,a)[0]>net.base_travel(a,b)[0]+1)
        self.assertNotEqual(net.base_travel(a,b)[0],net.base_travel(b,a)[0])
        d.loc=a;rs[0].origin=a;rs[0].dest=b;rs[1].origin=b;rs[1].dest=a
        for r in rs:r.pickup_deadline=10000
        sim.config.shared_ride.max_shared_extra_ride_s=10000
        plans=Evaluator(sim).plans(d,rs);self.assertEqual(len(plans),4)
        for p in plans:
            t=sim.t;loc=d.loc;picks={};drops={};distance=0
            for stop in p.stops:
                tt,dd=sim.traffic.estimate(loc,stop.loc,t,group='car');t+=tt;distance+=dd;loc=stop.loc
                if stop.kind=='pickup':picks[stop.rider_id]=t;t+=sim.config.boarding_s
                else:drops[stop.rider_id]=t;t+=sim.config.alighting_s
            self.assertEqual(p.pickup_t,picks);self.assertEqual(p.dropoff_t,drops)
            self.assertEqual(p.total_dist_m,distance)
        # Motorbike-only node from the actual access graph: car infeasible, bike feasible.
        c=next(n for n in sorted(set(range(net.num_nodes()))-net._main_scc(net.graph.allow['car']))
               if Evaluator(sim).reachable(a,n,'bike') and Evaluator(sim).reachable(n,a,'bike')
               and not Evaluator(sim).reachable(a,n,'car'))
        rs[0].origin=c;rs[0].dest=a;rs[1].origin=c;rs[1].dest=b
        d.group='car';self.assertEqual(Evaluator(sim).plans(d,rs),[])
        d.group='bike';self.assertTrue(Evaluator(sim).plans(d,rs))
