-- Sprint 08 A: service-owned templates and run lifecycle; legacy tables stay intact.
CREATE TABLE service_scenario (
    scenario_id INTEGER PRIMARY KEY REFERENCES scenario(id),
    run_spec_json TEXT NOT NULL
);
CREATE TABLE service_run (
    run_id INTEGER PRIMARY KEY REFERENCES run(id),
    owner TEXT,
    progress_json TEXT NOT NULL DEFAULT '{}',
    error_code TEXT,
    updated_at TEXT NOT NULL
);
