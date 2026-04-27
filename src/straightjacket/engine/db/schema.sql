-- Straightjacket database schema.
-- Tables mirror engine dataclasses. Columns match field names.
-- Ephemeral: rebuilt from GameState on every load/restore.
--
-- INSERT contract: sync.py is the sole writer and always provides every
-- column. No DEFAULT clauses on data columns — a missing value from a
-- caller is a bug to surface, not to paper over.

CREATE TABLE IF NOT EXISTS npcs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    agenda      TEXT NOT NULL,
    instinct    TEXT NOT NULL,
    arc         TEXT NOT NULL,
    secrets     TEXT NOT NULL,                  -- JSON array
    disposition TEXT NOT NULL,
    status      TEXT NOT NULL,
    introduced  INTEGER NOT NULL,                -- boolean; fresh NPCs not yet shown on-screen
    aliases     TEXT NOT NULL,                   -- JSON array
    keywords    TEXT NOT NULL,                   -- JSON array
    importance_accumulator INTEGER NOT NULL,
    last_reflection_scene  INTEGER NOT NULL,
    last_location TEXT NOT NULL,
    needs_reflection INTEGER NOT NULL,           -- boolean
    gather_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_id      TEXT NOT NULL REFERENCES npcs(id),
    scene       INTEGER NOT NULL,
    event       TEXT NOT NULL,
    emotional_weight TEXT NOT NULL,
    importance  INTEGER NOT NULL,
    type        TEXT NOT NULL,
    about_npc   TEXT,
    tone        TEXT NOT NULL,
    tone_key    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threads (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    thread_type TEXT NOT NULL,
    weight      INTEGER NOT NULL,
    source      TEXT NOT NULL,
    linked_track_id TEXT NOT NULL,
    active      INTEGER NOT NULL                 -- boolean
);

CREATE TABLE IF NOT EXISTS characters_list (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    entry_type  TEXT NOT NULL,
    weight      INTEGER NOT NULL,
    active      INTEGER NOT NULL                 -- boolean
);

CREATE TABLE IF NOT EXISTS clocks (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    clock_type  TEXT NOT NULL,
    segments    INTEGER NOT NULL,
    filled      INTEGER NOT NULL,
    trigger_description TEXT NOT NULL,
    owner       TEXT NOT NULL,
    fired       INTEGER NOT NULL,                -- boolean
    fired_at_scene INTEGER NOT NULL              -- 0 = not yet fired (runtime state)
);

CREATE TABLE IF NOT EXISTS scene_log (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    scene       INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    move        TEXT NOT NULL,
    result      TEXT NOT NULL,
    consequences TEXT NOT NULL,                  -- JSON array
    clock_events TEXT NOT NULL,                  -- JSON array of ClockEvent dicts
    position    TEXT NOT NULL,
    effect      TEXT NOT NULL,
    scene_type  TEXT NOT NULL,
    npc_activation TEXT NOT NULL,                -- JSON dict
    rich_summary TEXT NOT NULL,
    director_trigger TEXT NOT NULL,
    oracle_answer TEXT NOT NULL,
    revelation_check TEXT NOT NULL               -- JSON dict
);

CREATE TABLE IF NOT EXISTS narration_history (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    scene       INTEGER NOT NULL,
    prompt_summary TEXT NOT NULL,
    narration   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_tracks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    track_type  TEXT NOT NULL,
    rank        TEXT NOT NULL,
    ticks       INTEGER NOT NULL,
    max_ticks   INTEGER NOT NULL,
    status      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threats (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT NOT NULL,
    linked_vow_id   TEXT NOT NULL,
    rank            TEXT NOT NULL,
    menace_ticks    INTEGER NOT NULL,
    max_menace_ticks INTEGER NOT NULL,
    status          TEXT NOT NULL
);

-- Indexes for common query patterns.
CREATE INDEX IF NOT EXISTS idx_npcs_status ON npcs(status);
CREATE INDEX IF NOT EXISTS idx_npcs_disposition ON npcs(disposition);
CREATE INDEX IF NOT EXISTS idx_npcs_last_location ON npcs(last_location);
CREATE INDEX IF NOT EXISTS idx_memories_npc_id ON memories(npc_id);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
CREATE INDEX IF NOT EXISTS idx_memories_scene ON memories(scene);
CREATE INDEX IF NOT EXISTS idx_threads_active ON threads(active);
CREATE INDEX IF NOT EXISTS idx_clocks_clock_type ON clocks(clock_type);
CREATE INDEX IF NOT EXISTS idx_clocks_fired ON clocks(fired);
CREATE INDEX IF NOT EXISTS idx_threats_status ON threats(status);
CREATE INDEX IF NOT EXISTS idx_threats_linked_vow ON threats(linked_vow_id);
CREATE INDEX IF NOT EXISTS idx_scene_log_scene ON scene_log(scene);
