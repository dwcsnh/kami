import unittest
from kami.core.agents import Quote, RiderState
from kami.pricing import FareModel
from kami.shared.pricing import shared_quote
from tests.shared_helpers import world
from tests.helpers import assert_metrics_equal


class Pricing(unittest.TestCase):
    def test_exact_vnd_and_minimum_surge(self):
        for reference, expected in [(100000,70000),(25000,17500),(60000,42000),(40000,28000)]:
            self.assertEqual(shared_quote(Quote(reference,0),'shared_only').fare,expected)
        fm=FareModel()
        self.assertEqual(shared_quote(Quote(fm.fare(0,0),0),'shared_only').fare, fm.min_fare*.7)
        ref=fm.fare(12000,1500,2)
        self.assertEqual(shared_quote(Quote(ref,0,2),'shared_only').fare, ref*7/10)

    def test_booking_and_driver_see_discount_accounting_no_log(self):
        sim=world(); prices=[]; offers=[]
        class Booking:
            def p_book(self,r,q,ctx):
                prices.append(q.fare); self.assert_price=q.exclusive_reference_fare; return 1
        class Driver:
            def p_accept(self,d,offer,ctx): offers.append(offer); return 1
        sim.behavior.suite=sim.behavior.suite.replace(booking=Booking(),driver_accept=Driver())
        sim.run(); m=sim.metrics()
        self.assertTrue(all(r.state==RiderState.DONE for r in sim.riders.values()))
        self.assertEqual(prices,[r.fare for r in sim.riders.values()])
        self.assertEqual(offers[0].fare,sim.drivers[1].earnings)
        self.assertTrue(offers[0].shared)
        self.assertEqual(m['shared.shared_only.gmv'],m['shared.shared_only.payout']+m['shared.shared_only.platform_fee'])
        assert_metrics_equal(self,m,world(record_events=False).run().metrics())

    def test_no_service_no_charge(self):
        sim=world(drivers=[]).run()
        self.assertEqual(sim.metrics()['shared.shared_only.gmv'],0)
        self.assertEqual(sim.metrics()['shared.shared_only.payout'],0)
