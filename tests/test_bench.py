"""Sprint 01 — benchmark harness (S01-8)."""
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from kami.bench import DEFAULT_SUITE, compare, run_suite
from kami.cli import main
from tests.helpers import small_run_spec


class TestBench(unittest.TestCase):
    def test_suite_json_and_compare(self):
        with tempfile.TemporaryDirectory() as d:
            suite = Path(d) / "suite"
            suite.mkdir()
            (suite / "tiny.json").write_text(small_run_spec().to_json())
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = main(["bench", "--suite", str(suite), "--repeat", "2", "--out", f"{d}/r.json"])
            self.assertEqual(code, 0)
            res = json.loads(Path(f"{d}/r.json").read_text())
            c = res["cases"]["tiny"]
            for k in ("wall_s", "build_s", "events", "events_per_s", "peak_rss_mb", "metrics"):
                self.assertIn(k, c)
            self.assertEqual(set(c["wall_s"]), {"median", "min", "max"})
            self.assertGreater(c["events"], 0)
            self.assertGreater(c["peak_rss_mb"], 1)
            self.assertTrue(c["deterministic"])
            for k in ("python", "cpu", "git_commit", "kami_version", "cpp_router_built"):
                self.assertIn(k, res["env"])
            # regression detection
            slow = json.loads(json.dumps(res))
            slow["cases"]["tiny"]["wall_s"]["median"] *= 1.5
            _, bad = compare(slow, res)
            self.assertEqual(bad, ["tiny"])
            _, bad = compare(res, res)
            self.assertEqual(bad, [])

    def test_default_suite_is_valid(self):
        from kami.config import load_run_spec

        files = sorted(DEFAULT_SUITE.glob("*.json"))
        self.assertGreaterEqual(len(files), 4)
        names = {f.stem for f in files}
        self.assertIn("road_example_400", names)
        for f in files:
            load_run_spec(f)

    def test_unknown_case(self):
        with self.assertRaises(FileNotFoundError):
            run_suite(DEFAULT_SUITE, ["nope"], repeat=1, progress=False)


if __name__ == "__main__":
    unittest.main()
