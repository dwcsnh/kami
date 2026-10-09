import unittest
from kami.core.agents import RiderState
from kami.scenario import RequestSpec,DriverSpec
from kami.shared.evaluate import Evaluator
from tests.shared_helpers import world
from tests.helpers import assert_metrics_equal


class Dispatch(unittest.TestCase):
    def test_four_shared_and_exclusive_compete_for_one_driver(self):
        reqs=[RequestSpec(i,0,(i-1)*11,110+(i-1)*11,
              {'service_preference':'exclusive_only' if i==5 else 'shared_only'}) for i in range(1,6)]
        sim=world(requests=reqs).run()
        self.assertEqual(len(sim.shared_pairs),2)
        paired=[rid for p in sim.shared_pairs.values() for rid in p['rider_ids']]
        self.assertEqual(sorted(paired),[1,2,3,4])
        self.assertEqual(len(set(paired)),4)
        self.assertEqual(sim.riders[5].pair_history,[])
        self.assertEqual(sim.riders[5].effective_mode,'exclusive')
        self.assertTrue(all(r.state==RiderState.DONE for r in sim.riders.values()))
        self.assertEqual(sim.drivers[1].trips,5)
        count=0
        for _,ev,_,_,_ in sim.log.rows:
            if ev=='PICKUP':count+=1
            if ev=='DROPOFF':count-=1
            self.assertLessEqual(count,2);self.assertGreaterEqual(count,0)

    def test_three_requests_two_drivers_no_duplicates_exclusive(self):
        reqs=[RequestSpec(i,0,(i-1)*11,110+i*11) for i in range(1,4)]
        sim=world(requests=reqs,drivers=[DriverSpec(1,0,0,3000),DriverSpec(2,0,0,3000)]).run()
        self.assertEqual(len(sim.shared_pairs),1)
        self.assertEqual(sum(r.state==RiderState.DONE for r in sim.riders.values()),2)
        ids=sim.shared_pairs[1]['rider_ids'];self.assertEqual(len(set(ids)),2)
        self.assertEqual(sum(d.trips for d in sim.drivers.values()),2)

    def test_rejection_keeps_original_jobs_unmerged(self):
        sim=world()
        class Reject:
            def p_accept(self,*args):return 0
        sim.behavior.suite=sim.behavior.suite.replace(driver_accept=Reject())
        sim.run();self.assertEqual(sim.shared_pairs,{})
        self.assertEqual(len(sim.jobs),2)
        self.assertGreater(sim.drivers[1].rejections,0)
        self.assertTrue(all(r.t_cancel==600 for r in sim.riders.values()))

    def test_best_plan_matches_exhaustive_oracle_ties_stable(self):
        sim=world(drivers=[DriverSpec(2,0,0,3000),DriverSpec(1,0,0,3000)])
        expected=[]
        original=sim._offer_shared_plan
        def offer(d,rs,ev):
            oracle=Evaluator(sim)
            for drv in sim.idle_drivers():
                expected.extend((p.total_dropoff_s,p.total_dist_m,drv.id,p.order) for p in oracle.plans(drv,rs))
            self.assertEqual((ev.total_dropoff_s,ev.total_dist_m,d.id,ev.order),min(expected))
            sim._offer_shared_plan=original
            return original(d,rs,ev)
        sim._offer_shared_plan=offer;sim.run()
        self.assertEqual(sim.shared_pairs[1]['driver_id'],1)

    def test_reproducible_and_disabled_compatible(self):
        a=world().run();b=world().run();self.assertEqual(a.log.rows,b.log.rows);assert_metrics_equal(self,a.metrics(),b.metrics())
        from kami import Simulation
        a=world();a.config.shared_ride.enabled=False;a=Simulation(a.scenario,behavior=a.behavior.suite,config=a.config).run()
        b=world();from kami.shared import SharedRideConfig
        b.config.shared_ride=SharedRideConfig();b=Simulation(b.scenario,behavior=b.behavior.suite,config=b.config).run()
        self.assertEqual(a.log.rows,b.log.rows);assert_metrics_equal(self,a.metrics(),b.metrics())
