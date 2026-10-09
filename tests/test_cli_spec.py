"""Sprint 01 — CLI: ``run --spec``, ``spec``, ``db init`` (S01-3); 0.1 commands unchanged."""
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from kami.cli import main
from kami.config import RunSpec
from kami.store import Repository
from tests.helpers import small_run_spec


def quiet(argv):
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCliSpec(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.spec = self.d / "run.json"
        self.spec.write_text(small_run_spec("rain", "surge").to_json())

    def tearDown(self):
        self.tmp.cleanup()

    def test_spec_command_prints_valid_json(self):
        code, out, _ = quiet(["spec", "--preset", "accident", "--policy", "pool_after_wait", "--arg", "surcharge=0",
                              "--arg", "include_matched=true", "--network", "road:example_network",
                              "--zones", "example_zones"])
        self.assertEqual(code, 0)
        spec = RunSpec.from_dict(json.loads(out))
        self.assertEqual(spec.scenario.network.kind, "road")
        self.assertEqual(spec.scenario.zones.name, "example_zones")
        self.assertEqual(spec.policy_group.members[0].policy.params, {"surcharge": 0, "include_matched": True})

    def test_run_spec_with_db(self):
        db = self.d / "k.db"
        code, out, err = quiet(["run", "--spec", str(self.spec), "--db", str(db), "--artifacts",
                                str(self.d / "runs"), "--out", str(self.d / "out")])
        self.assertEqual(code, 0, err)
        self.assertIn("run_id 1", out)
        repo = Repository.open(db)
        self.assertEqual(repo.get_run(1)["status"], "succeeded")
        self.assertTrue(Path(repo.run_artifacts(1)[0]["path"]).exists())
        repo.close()
        self.assertTrue((self.d / "out" / "events.parquet").exists())
        self.assertTrue((self.d / "out" / "metrics.json").exists())

    def test_spec_conflicts_with_legacy_flags(self):
        code, _, err = quiet(["run", "--spec", str(self.spec), "--preset", "rain"])
        self.assertEqual(code, 2)
        self.assertIn("--preset", err)
        code, _, err = quiet(["run", "--db", str(self.d / "k.db")])
        self.assertEqual(code, 2)

    def test_invalid_spec_reports_field(self):
        bad = self.d / "bad.json"
        bad.write_text(json.dumps({"scenario": {"source": {"kind": "preset", "preset": "rainy"}}}))
        code, _, err = quiet(["run", "--spec", str(bad)])
        self.assertEqual(code, 2)
        self.assertIn("scenario.source.preset", err)

    def test_reference_without_db(self):
        ref = self.d / "ref.json"
        ref.write_text(json.dumps({"scenario": {"ref": "rain"}}))
        code, _, err = quiet(["run", "--spec", str(ref)])
        self.assertEqual(code, 2)
        self.assertIn("Repository.resolve", err)

    def test_db_init(self):
        # Exercise the real CLI process, including OS release of SQLite file handles on Windows.
        from kami.store.db import migrations
        db = self.d / "x.db"
        def invoke():
            return subprocess.run([sys.executable, "-m", "kami", "db", "init", "--db", str(db)],
                                  capture_output=True, text=True, timeout=20)
        first = invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f"schema version {max(v for v, _, _ in migrations())}", first.stdout)
        second = invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("up to date", second.stdout)

    def test_presets_command_unchanged(self):
        code, out, _ = quiet(["presets"])
        self.assertEqual(code, 0)
        self.assertIn("weekday_am_peak", out)


if __name__ == "__main__":
    unittest.main()
