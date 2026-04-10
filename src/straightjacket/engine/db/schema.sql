-- Straightjacket database schema.
-- Tables mirror engine dataclasses. Columns match field names.
-- Ephemeral: rebuilt from GameState on every load/restore.

CREATE TABLE IF NOT EXISTS npcs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    agenda      TEXT NOT NULL DEFAULT '',
    instinct    TEXT NOT NULL DEFAULT '',
    arc         TEXT NOT NULL DEFAULT '',
    secrets     TEXT NOT NULL DEFAULT '[]',    -- JSON array
    disposition TEXT NOT NULL DEFAULT 'neutral',
    bond        INTEGER NOT NULL DEFAULT 0,
    bond_max    INTEGER NOT NULL DEFAULT 4,
    status      TEXT NOT NULL DEFAULT 'active',
    introduced  INTEGER NOT NULL DEFAULT 1,    -- boolean
    aliases     TEXT NOT NULL DEFAULT '[]',     -- JSON array
    keywords    TEXT NOT NULL DEFAULT '[]',     -- JSON array
    importance_accumulator INTEGER NOT NULL DEFAULT 0,
    last_reflection_scene  INTEGER NOT NULL DEFAULT 0,
    last_location TEXT NOT NULL DEFAULT '',
    needs_reflection INTEGER NOT NULL DEFAULT 0,  -- boolean
    gather_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memories (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_id      TEXT NOT NULL REFERENCES npcs(id),
    scene       INTEGER NOT NULL DEFAULT 0,
    event       TEXT NOT NULL DEFAULT '',
    emotional_weight TEXT NOT NULL DEFAULT 'neutral',
    importance  INTEGER NOT NULL DEFAULT 3,
    type        TEXT NOT NULL DEFAULT 'observation',
    about_npc   TEXT,
    tone        TEXT NOT NULL DEFAULT '',
    tone_key    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS threads (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    thread_type TEXT NOT NULL DEFAULT 'vow',
    weight      INTEGER NOT NULL DEFAULT 1,
    source      TEXT NOT NULL DEFAULT 'creation',
    linked_track_id TEXT NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1     -- boolean
);

CREATE TABLE IF NOT EXISTS characters_list (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    entry_type  TEXT NOT NULL DEFAULT 'npc',
    weight      INTEGER NOT NULL DEFAULT 1,
    active      INTEGER NOT NULL DEFAULT 1     -- boolean
);

CREATE TABLE IF NOT EXISTS clocks (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL DEFAULT '',
    clock_type  TEXT NOT NULL DEFAULT 'threat',
    segments    INTEGER NOT NULL DEFAULT 6,
    filled      INTEGER NOT NULL DEFAULT 0,
    trigger_description TEXT NOT NULL DEFAULT '',
    owner       TEXT NOT NULL DEFAULT '',
    fired       INTEGER NOT NULL DEFAULT 0,    -- boolean
    fired_at_scene INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scene_log (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    scene       INTEGER NOT NULL DEFAULT 0,
    summary     TEXT NOT NULL DEFAULT '',
    move        TEXT NOT NULL DEFAULT '',
    result      TEXT NOT NULL DEFAULT '',
    consequences TEXT NOT NULL DEFAULT '[]',    -- JSON array
    clock_events TEXT NOT NULL DEFAULT '[]',    -- JSON array of ClockEvent dicts
    position    TEXT NOT NULL DEFAULT 'risky',
    effect      TEXT NOT NULL DEFAULT 'standard',
    chaos_interrupt TEXT,
    npc_activation TEXT NOT NULL DEFAULT '{}',  -- JSON dict
    validator   TEXT NOT NULL DEFAULT '{}',     -- JSON dict
    rich_summary TEXT NOT NULL DEFAULT '',
    director_trigger TEXT NOT NULL DEFAULT '',
    revelation_check TEXT NOT NULL DEFAULT '{}' -- JSON dict
);

CREATE TABLE IF NOT EXISTS narration_history (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    scene       INTEGER NOT NULL DEFAULT 0,
    prompt_summary TEXT NOT NULL DEFAULT '',
    narration   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vow_tracks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    track_type  TEXT NOT NULL DEFAULT 'vow',
    rank        TEXT NOT NULL DEFAULT 'dangerous',
    ticks       INTEGER NOT NULL DEFAULT 0,
    max_ticks   INTEGER NOT NULL DEFAULT 40
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
CREATE INDEX IF NOT EXISTS idx_scene_log_scene ON scene_log(scene);
