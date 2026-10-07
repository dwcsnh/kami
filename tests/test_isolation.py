"""Sprint 01 — NFR-5 / AC01-7: the engine runs as a plain library, without database libraries."""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_MODULES = ("sqlite3", "kami.store", "sqlalchemy", "psycopg", "psycopg2")
ALLOWED = {ROOT / "kami" / "cli.py", ROOT / "kami" / "bench.py"}


def _run(code: str) -> str:
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return proc.stdout


class TestIsolation(unittest.TestCase):
    def test_import_kami_loads_no_db_library(self):
        out = _run("import sys, kami, kami.config, kami.timeseries\n"
                   f"print([m for m in sys.modules if m.split('.')[0] in {DB_MODULES!r} or m.startswith('kami.store')])")
        self.assertEqual(out.strip(), "[]")

    def test_quickstart_and_spec_run_without_db(self):
        code = ("import runpy, sys\n"
                "runpy.run_path('examples/01_quickstart.py', run_name='__main__')\n"
                "from kami.cli import main\n"
                "main(['run', '--spec', 'examples/specs/preset_weekday_am_peak.json'])\n"
                f"print('DBMODS', [m for m in sys.modules if m.split('.')[0] in {DB_MODULES!r} "
                "or m.startswith('kami.store')])")
        out = _run(code)
        self.assertIn("DBMODS []", out)

    def test_no_static_db_import_outside_store(self):
        offenders = []
        for path in (ROOT / "kami").rglob("*.py"):
            if (ROOT / "kami" / "store") in path.parents or path in ALLOWED:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if any(n.split(".")[0] in DB_MODULES or n.startswith("kami.store") for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
