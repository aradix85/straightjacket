CREATE TABLE IF NOT EXISTS npcs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    agenda      TEXT NOT NULL,
    instinct    TEXT NOT NULL,
    arc         TEXT NOT NULL,
    secrets     TEXT NOT NULL,
    disposition TEXT NOT NULL,
    status      TEXT NOT NULL,
    introduced  INTEGER NOT NULL,
    aliases     TEXT NOT NULL,
    keywords    TEXT NOT NULL,
    importance_accumulator INTEGER NOT NULL,
    last_reflection_scene  INTEGER NOT NULL,
    last_location TEXT NOT NULL,
    needs_reflection INTEGER NOT NULL,
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
    linked_track_id TEXT,
    active      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS characters_list (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    entry_type  TEXT NOT NULL,
    weight      INTEGER NOT NULL,
    active      INTEGER NOT NULL,
    ac_status   TEXT NOT NULL,
    ac_turning_point_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS plotlines_list (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,
    turning_point_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clocks (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    clock_type  TEXT NOT NULL,
    segments    INTEGER NOT NULL,
    filled      INTEGER NOT NULL,
    trigger_description TEXT NOT NULL,
    owner_kind  TEXT NOT NULL,
    owner_id    TEXT,
    creation_source TEXT NOT NULL,
    fired       INTEGER NOT NULL,
    fired_at_scene INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_log (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    scene       INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    move        TEXT NOT NULL,
    result      TEXT NOT NULL,
    consequences TEXT NOT NULL,
    clock_events TEXT NOT NULL,
    position    TEXT NOT NULL,
    effect      TEXT NOT NULL,
    scene_type  TEXT NOT NULL,
    npc_activation TEXT NOT NULL,
    rich_summary TEXT NOT NULL,
    director_trigger TEXT NOT NULL,
    oracle_answer TEXT NOT NULL,
    revelation_check TEXT NOT NULL
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
    linked_vow_id   TEXT,
    rank            TEXT NOT NULL,
    menace_ticks    INTEGER NOT NULL,
    max_menace_ticks INTEGER NOT NULL,
    status          TEXT NOT NULL,
    creation_source TEXT NOT NULL
);

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
