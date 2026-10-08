-- kami 0.2 sprint 01: configuration entities, policy versions, runs and their results.
-- Entity tables share: id, name (unique among non-deleted rows), spec_json (the validated spec),
-- created_at / updated_at / deleted_at (ISO-8601 UTC; deleted_at = soft delete).

CREATE TABLE vehicle_type (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    spec_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE UNIQUE INDEX vehicle_type_name ON vehicle_type(name) WHERE deleted_at IS NULL;

CREATE TABLE fleet (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    spec_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE UNIQUE INDEX fleet_name ON fleet(name) WHERE deleted_at IS NULL;

CREATE TABLE fleet_vehicle (
    fleet_id         INTEGER NOT NULL REFERENCES fleet(id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    vehicle_type_id  INTEGER NOT NULL REFERENCES vehicle_type(id),
    count            INTEGER NOT NULL CHECK (count > 0),
    PRIMARY KEY (fleet_id, position)
);

CREATE TABLE charging_station (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    spec_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE UNIQUE INDEX charging_station_name ON charging_station(name) WHERE deleted_at IS NULL;

CREATE TABLE policy (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    plugin       TEXT NOT NULL,
    source_kind  TEXT NOT NULL DEFAULT 'builtin',     -- builtin | user | agent (sprint 07, 10)
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    deleted_at   TEXT
);
CREATE UNIQUE INDEX policy_name ON policy(name) WHERE deleted_at IS NULL;

-- immutable: a parameter change creates a new version
CREATE TABLE policy_version (
    id                  INTEGER PRIMARY KEY,
    policy_id           INTEGER NOT NULL REFERENCES policy(id),
    version             INTEGER NOT NULL,
    params_json         TEXT NOT NULL,
    params_schema_json  TEXT,                         -- sprint 07
    source_code         TEXT,                         -- sprint 07 (non built-in plug-ins)
    created_at          TEXT NOT NULL,
    UNIQUE (policy_id, version)
);

CREATE TABLE policy_group (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    spec_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE UNIQUE INDEX policy_group_name ON policy_group(name) WHERE deleted_at IS NULL;

-- policy_version_id is NULL for an inline member (plugin + params stored here)
CREATE TABLE policy_group_member (
    group_id           INTEGER NOT NULL REFERENCES policy_group(id) ON DELETE CASCADE,
    position           INTEGER NOT NULL,
    policy_version_id  INTEGER REFERENCES policy_version(id),
    plugin             TEXT NOT NULL,
    params_json        TEXT NOT NULL,
    enabled            INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (group_id, position)
);

CREATE TABLE scenario (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    spec_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE UNIQUE INDEX scenario_name ON scenario(name) WHERE deleted_at IS NULL;

CREATE TABLE run (
    id                INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    run_spec_json     TEXT NOT NULL,                  -- resolved snapshot: re-runnable without the DB (NFR-4)
    source_spec_json  TEXT NOT NULL,                  -- as submitted (may contain references)
    provenance_json   TEXT NOT NULL,                  -- ids / policy versions the references resolved to
    kami_version      TEXT NOT NULL,
    schema_version    INTEGER NOT NULL,
    seed              INTEGER,
    scenario_id       INTEGER REFERENCES scenario(id),
    policy_group_id   INTEGER REFERENCES policy_group(id),
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    finished_at       TEXT,
    wall_s            REAL,
    events            INTEGER,
    error             TEXT
);
CREATE INDEX run_status ON run(status);

CREATE TABLE run_metric_summary (
    run_id  INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    name    TEXT NOT NULL,
    value   REAL,                                     -- NULL = NaN (undefined)
    PRIMARY KEY (run_id, name)
);

CREATE TABLE run_metric_timeseries (
    run_id  INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    t       REAL NOT NULL,                            -- simulation seconds
    name    TEXT NOT NULL,
    value   REAL,
    PRIMARY KEY (run_id, name, t)
);

CREATE TABLE run_artifact (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,                        -- event_log | ...
    path        TEXT NOT NULL,
    format      TEXT NOT NULL,                        -- parquet | csv.gz | json
    size_bytes  INTEGER,
    sha256      TEXT,
    rows        INTEGER,
    created_at  TEXT NOT NULL
);
CREATE INDEX run_artifact_run ON run_artifact(run_id);
