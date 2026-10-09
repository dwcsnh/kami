import unittest
from kami.core.agents import RiderState, DriverState
from kami.core.events import EventType as E
from kami.scenario import RequestSpec, DriverSpec
from tests.shared_helpers import world


class CancelAt(type(world())):
    def _on_policy_timer(self, rider_id=None, **payload):
        self._cancel_shared(self.riders[rider_id],'behavior')


def cancel_sim(at, rider=2, **kw):
    base=world(**kw)
    sim=CancelAt(base.scenario,behavior=base.behavior.suite,config=base.config)
    sim._push(at,E.POLICY_TIMER,rider_id=rider)
    return sim


class Lifecycle(unittest.TestCase):
    def test_traffic_makes_matched_pickups_late_cleanup_at_deadline(self):
        reqs=[RequestSpec(1,0,220,330),RequestSpec(2,0,220,330)]
        sim=world(requests=reqs);sim.scenario.weather=[(5,'heavy_rain')]
        sim.traffic.weather_factor['heavy_rain']=4
        sim.run()
        self.assertEqual(len(sim.shared_pairs),1)
        self.assertFalse(sim.shared_pairs[1]['pickups'])
        for r in sim.riders.values():
            self.assertEqual(r.t_cancel,600)
            self.assertEqual(r.cancellation_reason,'pickup_timeout')
        self.assertEqual(sim.drivers[1].trips,0)
        self.assertLessEqual(sim.drivers[1].dist_total,2000)
        self.assertFalse(sim.drivers[1].plan)

    def test_shift_end_and_cancel_at_same_timestamp_as_pickup(self):
        sim=cancel_sim(40,drivers=[DriverSpec(1,0,0,20)]).run()
        self.assertEqual(sim.riders[2].t_pickup,40)
        self.assertTrue(all(r.state==RiderState.DONE for r in sim.riders.values()))
        self.assertEqual(sim.drivers[1].trips,2)
        self.assertEqual(sim.drivers[1].state,DriverState.OFFLINE)
        self.assertEqual(len(sim.log.filter('PICKUP')),2)

    def test_timeout_without_partner_or_driver(self):
        for sim in [world(drivers=[]),world(requests=[RequestSpec(1,0,0,110)])]:
            sim.run()
            for r in sim.riders.values():
                self.assertEqual(r.state,RiderState.CANCELLED); self.assertEqual(r.t_cancel,600)
                self.assertEqual(r.cancellation_reason,'pickup_timeout')
                self.assertEqual(r.fare_paid,0)

    def test_exact_deadline_and_onboard_beyond_deadline(self):
        # singleton Exclusive: pickup at 600 is allowed, 610 is rejected before offer.
        for origin,expected in [(110,RiderState.DONE),(121,RiderState.CANCELLED)]:
            sim=world(requests=[RequestSpec(1,0,origin,220,{'service_preference':'exclusive_only'})],boarding_s=0)
            sim.config.shared_ride.max_pickup_wait_s=100
            sim.run(); r=sim.riders[1]
            self.assertEqual(r.state,expected)
            if expected==RiderState.DONE:self.assertEqual(r.t_pickup,100)
        sim=world(boarding_s=650)
        # Increased own boarding prevents second pickup by 600: evaluator rejects.
        sim.run();self.assertFalse(sim.shared_pairs)

    def test_pair_dissolves_before_pickup_requeues_old_clock(self):
        sim=cancel_sim(5,drivers=[DriverSpec(1,22,0,3000)]).run()
        r=sim.riders[1]
        self.assertEqual(r.t_booked,0);self.assertEqual(r.pickup_deadline,600)
        self.assertEqual(r.t_cancel,600);self.assertEqual(r.driver_id,None)
        self.assertEqual(len(sim.shared_pairs),1)
        self.assertFalse(sim.shared_pairs[1]['pickups'])
        self.assertEqual(sim.drivers[1].dist_total,50)

    def test_partner_cancel_after_pickup_keeps_quote_dwell(self):
        sim=cancel_sim(10).run();a,b=sim.riders[1],sim.riders[2]
        self.assertEqual(a.state,RiderState.DONE);self.assertEqual(b.state,RiderState.CANCELLED)
        self.assertEqual(a.t_pickup,0);self.assertEqual(a.t_dropoff,130)
        self.assertEqual(a.fare,a.quote.fare); self.assertEqual(a.surcharge,0)
        self.assertEqual(sim.drivers[1].dist_total,1000)
        self.assertEqual(len(sim.log.filter('PICKUP',rider_id=1)),1)
        self.assertEqual(sim.metrics()['shared.actual_pairs'],0)

    def test_traffic_during_boarding_preserves_departure(self):
        sim=world();sim.scenario.weather=[(10,'rain')];sim.traffic.weather_factor={'clear':1,'rain':1}
        sim.run();self.assertEqual(sim.riders[2].t_pickup,40)
        self.assertEqual(sim.drivers[1].dist_total,1100)

    def test_waiting_hazard_budget_not_redrawn(self):
        sim=cancel_sim(25,drivers=[DriverSpec(1,22,20,3000)])
        class Hazard:
            def hazard(self,*args): return .001
        sim.behavior.suite=sim.behavior.suite.replace(cancel_wait=Hazard(),cancel_matched=Hazard())
        sim.run();r=sim.riders[1]
        self.assertAlmostEqual(r.hazard_budget,sim.crn.exp('cancel_waiting',1))
        self.assertAlmostEqual(r.hazard_history['waiting'][1],20*.001/60)
        self.assertAlmostEqual(r.hazard_acc,595*.001/60)

    def test_shared_pickups_exactly_600_onboard_not_timed_out(self):
        reqs=[RequestSpec(1,0,220,330),RequestSpec(2,0,220,330)]
        sim=world(requests=reqs,boarding_s=0)
        sim.network.speed=10/3
        sim.run()
        self.assertEqual(len(sim.shared_pairs),1)
        for r in sim.riders.values():
            self.assertEqual(r.t_pickup,600);self.assertEqual(r.state,RiderState.DONE)
            self.assertIsNone(r.cancellation_reason)

    def test_repair_after_dissolution_keeps_price_and_deadline(self):
        reqs=[RequestSpec(1,0,0,110),RequestSpec(2,0,11,121),RequestSpec(3,10,11,121)]
        sim=cancel_sim(5,requests=reqs,drivers=[DriverSpec(1,22,0,3000)]).run()
        r=sim.riders[1]
        self.assertEqual(r.pair_history,[1,2]);self.assertEqual(r.t_booked,0);self.assertEqual(r.pickup_deadline,600)
        self.assertEqual(r.fare,r.quote.fare);self.assertEqual(r.state,RiderState.DONE)
        self.assertEqual(sim.metrics()['shared.planned_pairs'],2);self.assertEqual(sim.metrics()['shared.actual_pairs'],1)
