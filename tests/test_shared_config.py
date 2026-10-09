import math
import unittest
from kami.config import RunSpec, SpecError, build_run
from kami.shared import SharedRideConfig
from tests.helpers import small_run_spec
from tests.shared_helpers import world


class Config(unittest.TestCase):
    def test_build_preference_uses_demand_seed_independent_of_run_crn(self):
        from kami.core.crn import CRN
        d=small_run_spec(seed=11).to_dict()
        d['sim_config']['shared_ride']={'enabled':True,'preference_weights':{'shared_only':1,'exclusive_only':1}}
        a=build_run(RunSpec.from_dict(dict(d,crn_seed=101)))
        b=build_run(RunSpec.from_dict(dict(d,crn_seed=999)))
        self.assertEqual(a.scenario.requests,b.scenario.requests)
        crn=CRN(a.scenario.seed)
        for r in a.scenario.requests:
            expected='shared_only' if crn.u('service_preference',r.id)<.5 else 'exclusive_only'
            self.assertEqual(r.attrs['service_preference'],expected)

    def test_defaults_normalize_snapshot(self):
        spec=small_run_spec().to_dict(); spec['sim_config']['shared_ride']={'enabled':True,'preference_weights':{'shared_only':2,'exclusive_only':2}}
        parsed=RunSpec.from_dict(spec); cfg=parsed.sim_config.values['shared_ride']
        self.assertEqual((cfg['max_pickup_wait_s'],cfg['max_shared_extra_ride_s'],cfg['candidate_radius_m']),(600,450,500))
        self.assertEqual(cfg['preference_weights'],dict(shared_only=.5,exclusive_only=.5))
        self.assertEqual(cfg['fare_factor'],.7)
        built=build_run(parsed); self.assertTrue(built.config.shared_ride.enabled)
        self.assertNotIn('shared_ride',small_run_spec().to_dict()['sim_config'])

    def test_invalid_config_paths(self):
        for key,value in [('version',2),('max_pickup_wait_s',0),('max_shared_extra_ride_s',-1),('candidate_radius_m',math.inf),('preference_weights',{'shared_only':0}),('preference_weights',{'shared_fallback_exclusive':1}),('preference_weights',{'shared_only':math.nan}),('fare_factor',.8)]:
            with self.subTest(key=key,value=value):
                with self.assertRaises(SpecError) as err:
                    RunSpec.from_dict(dict(scenario={'source':{'kind':'preset'}},sim_config={'shared_ride':{'enabled':True,key:value}}))
                self.assertIn('sim_config.shared_ride',str(err.exception))

    def test_preference_override_and_stable_seed(self):
        sim=world(); sim.scenario.requests[0].attrs['service_preference']='exclusive_only'; sim.run()
        self.assertEqual(sim.riders[1].service_preference,'exclusive_only')
        self.assertEqual(len(sim.shared_pairs),0)
        sim=world(); sim.scenario.requests[0].attrs['service_preference']='shared_fallback_exclusive'
        with self.assertRaises(ValueError):
            type(sim)(sim.scenario,config=sim.config)

    def test_extreme_finite_weights(self):
        cfg=SharedRideConfig(preference_weights={'shared_only':1e308,'exclusive_only':1e308})
        self.assertEqual(cfg.preference_weights['shared_only'],.5)
