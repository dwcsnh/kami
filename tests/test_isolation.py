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
    def test_shared_engine_runs_without_db_web_or_global_rng(self):
        code = ("import sys, random, numpy.random\n"
                "def forbidden(*a, **kw): raise AssertionError('global RNG')\n"
                "random.random = forbidden; numpy.random.random = forbidden\n"
                "from tests.shared_helpers import world\nworld().run()\n"
                f"print([m for m in sys.modules if m.split('.')[0] in {DB_MODULES + WEB_MODULES!r} or m.startswith('kami.store')])")
        self.assertEqual(_run(code).strip(), '[]')

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
            if any((ROOT / "kami" / package) in path.parents for package in ("store", "service")) or path in ALLOWED:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if any(n.split(".")[0] in DB_MODULES or n.startswith("kami.store") for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


WEB_MODULES = ("flask", "fastapi", "django", "starlette", "aiohttp", "tornado", "uvicorn", "websockets", "streamlit",
               "dash", "bokeh", "plotly", "folium", "pydeck", "keplergl")


class TestReplayIsolation(unittest.TestCase):
    """Sprint 03 — AC03-9: the replay exporter is outside the engine core and no Python code imports web libraries."""

    def test_import_kami_does_not_load_replay(self):
        out = _run("import sys, kami, kami.core.engine, kami.config\n"
                   "print([m for m in sys.modules if m.startswith('kami.replay')])")
        self.assertEqual(out.strip(), "[]")

    def test_core_does_not_import_replay(self):
        offenders = []
        for path in (ROOT / "kami").rglob("*.py"):
            rel = path.relative_to(ROOT / "kami")
            if rel.parts[0] in ("replay", "store", "service") or path in ALLOWED:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if any(n.startswith("kami.replay") for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_no_web_library_imports(self):
        offenders = []
        for path in (ROOT / "kami").rglob("*.py"):
            if (ROOT / "kami" / "service") in path.parents:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if any(n.split(".")[0] in WEB_MODULES for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_core_does_not_import_service(self):
        for path in (ROOT / "kami").rglob("*.py"):
            if (ROOT / "kami" / "service") in path.parents:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                self.assertFalse(any(n.startswith("kami.service") for n in names), str(path))
        self.assertEqual(_run("import sys, kami, kami.config; print(any(n.startswith('kami.service') for n in sys.modules))").strip(), "False")

    def test_service_package_import_has_no_process_or_web_side_effect(self):
        code = ("import sys, multiprocessing, kami.service; "
                "print(multiprocessing.active_children()); "
                "print([n for n in ('fastapi', 'sqlite3', 'uvicorn') if n in sys.modules])")
        self.assertEqual(_run(code).strip(), "[]\n[]")

    def test_replay_runs_without_db(self):
        out = _run("import sys\nfrom kami.replay import export, validate\n"
                   f"print([m for m in sys.modules if m.split('.')[0] in {DB_MODULES!r} or m.startswith('kami.store')])")
        self.assertEqual(out.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
