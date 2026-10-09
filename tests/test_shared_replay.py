import json
import tempfile
import unittest
from pathlib import Path
from kami.replay import export
from kami.shared.metrics import pair_actual
from tests.shared_helpers import world
from tests.helpers import hanoi_built


class Replay(unittest.TestCase):
    @unittest.skipUnless(hanoi_built(), 'needs Hanoi graph for Shared lifecycle walkthrough')
    def test_walkthrough_has_real_waiting_and_four_distinct_stops(self):
        import runpy
        root = Path(__file__).resolve().parents[1]
        build = runpy.run_path(str(root/'examples/10_shared_ride_walkthrough.py'))['build_demo']
        sim = build().run()
        self.assertEqual(sim.metrics()['shared.shared_only.served'], 2)
        pair = sim.shared_pairs[1]
        self.assertEqual(len({s['loc'] for s in pair['stops']}), 4)
        self.assertGreater(pair['created_t'], max(r.t_booked for r in sim.riders.values()))
        self.assertGreater(min(pair['pickups'].values()) - pair['created_t'], 30)
        self.assertGreater(max(pair['dropoffs'].values()) - min(pair['dropoffs'].values()), 30)
        with tempfile.TemporaryDirectory() as tmp:
            out = export(sim, tmp, run={'name': 'Shared V1 — từ đặt xe đến trả khách (minh họa)', 'seed': 7})
            fixture = root/'web/public/fixtures/shared_v1_walkthrough'
            for p in out.iterdir():
                self.assertEqual(p.read_bytes(), (fixture/p.name).read_bytes(), p.name)

    @unittest.skipUnless(hanoi_built(), 'needs Hanoi graph for the separate Shared demo fixture')
    def test_shared_hanoi_fixture_matches_current_export(self):
        from kami.config import build_run, load_run_spec
        from kami.replay.cli import export_run
        root = Path(__file__).resolve().parents[1]
        spec = load_run_spec(root/'scenarios/shared/v1-demo.json')
        sim = build_run(spec).simulation().run()
        with tempfile.TemporaryDirectory() as tmp:
            out = export_run(spec, sim, tmp)
            fixture = root/'web/public/fixtures/shared_v1_demo'
            self.assertEqual({p.name for p in out.iterdir()}, {p.name for p in fixture.iterdir()})
            for p in out.iterdir():
                self.assertEqual(p.read_bytes(), (fixture/p.name).read_bytes(), p.name)

    def test_cli_folder_roundtrip_and_json_null(self):
        from kami.cli import main
        from kami.config import build_run
        from kami.replay.cli import from_run_folder, run_meta
        from tests.helpers import small_run_spec
        import contextlib
        import io
        spec = small_run_spec(demand=40, drivers=10).to_dict()
        spec['sim_config'] = {'shared_ride': {'enabled': True}, 'timeseries_interval_s': 60}
        spec['outputs'] = {'event_log': 'csv.gz', 'trajectories': 'parquet', 'replay': 'json'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'spec.json'; source.write_text(json.dumps(spec))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['run','--spec',str(source),'--out',str(root/'run')]),0)
            resolved, inp = from_run_folder(root/'run')
            sim = build_run(resolved).simulation().run()
            direct = export(sim, root/'direct', run=run_meta(resolved))
            restored = export(inp, root/'restored')
            for p in direct.iterdir():
                self.assertEqual(p.read_bytes(),(restored/p.name).read_bytes(),p.name)
            metrics = (root/'run'/'metrics.json').read_text()
            self.assertNotIn('NaN',metrics)
            self.assertIsNone(json.loads(metrics)['shared.shared_only.wait_p50'])

    def test_deterministic_metadata_and_overlap_milestones(self):
        sim=world(record_trajectories=True,timeseries_interval_s=20).run()
        with tempfile.TemporaryDirectory() as tmp:
            a=export(sim,Path(tmp)/'a');b=export(sim,Path(tmp)/'b')
            for p in a.iterdir():self.assertEqual(p.read_bytes(),(b/p.name).read_bytes())
            man=json.loads((a/'manifest.json').read_text(encoding='utf-8'));pair=man['shared']['pairs'][0]
            self.assertEqual(pair['rider_ids'],[1,2]);self.assertEqual(len(pair['stops']),4)
            self.assertEqual(pair['actual_overlap_s'],120)
            self.assertEqual(pair['overlap_start'],40);self.assertEqual(pair['overlap_end'],160)
            for t,count in [(0,1),(39,1),(40,2),(159,2),(160,1),(190,0)]:
                self.assertEqual(sum(r.t_pickup<=t<r.t_dropoff for r in sim.riders.values()),count)
        pair=sim.shared_pairs[1]
        self.assertFalse(pair_actual(dict(pair,pickups={1:0,2:160},dropoffs={1:160,2:190}),190)['actual_shared'])

    def test_disabled_no_metadata_and_summary_independent_of_recording(self):
        from kami import Simulation
        from tests.helpers import assert_metrics_equal
        a=world(record_trajectories=True);a.config.shared_ride.enabled=False;a=Simulation(a.scenario,behavior=a.behavior.suite,config=a.config).run()
        with tempfile.TemporaryDirectory() as tmp:
            path=export(a,tmp);self.assertNotIn('shared',json.loads((path/'manifest.json').read_text(encoding='utf-8')))
        a=world(timeseries_interval_s=20).run();b=world(timeseries_interval_s=20,record_events=False).run()
        self.assertEqual(len(a.timeseries.rows),len(b.timeseries.rows))
        for x,y in zip(a.timeseries.rows,b.timeseries.rows):assert_metrics_equal(self,x,y)
        m=a.metrics()
        self.assertEqual(m['shared.shared_only.served'],len(a.log.filter('DROPOFF')))
        self.assertEqual(m['shared.shared_only.booked'],len(a.log.filter('OFFER_ACCEPTED')))
        self.assertEqual(m['shared.shared_only.gmv'],sum(row[4]['fare'] for row in a.log.filter('DROPOFF')))
