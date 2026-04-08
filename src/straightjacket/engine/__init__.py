#!/usr/bin/env python3
"""
Straightjacket Engine Package
========================
Re-exports public symbols used by app.py and ui/.
"""

# Re-export i18n symbols used by engine modules
from ..i18n import E
from .ai import (
    AIProvider,
    AIResponse,
    AnthropicProvider,
    OpenAICompatibleProvider,
    call_brain,
    call_chapter_summary,
    call_narrator,
    call_narrator_metadata,
    call_opening_setup,
    call_recap,
    call_story_architect,
    clear_provider_cache,
    create_with_retry,
    get_provider,
)
from .config_loader import (
    GLOBAL_CONFIG_FILE,
    USERS_DIR,
    VERSION,
    cfg,
    default_player_name,
    narration_language,
    reload_config,
)
from .correction import process_correction, process_momentum_burn
from .director import build_director_prompt, call_director, reset_stale_reflection_flags
from .game import (
    generate_epilogue,
    process_turn,
    run_deferred_director,
    start_new_chapter,
    start_new_game,
)
from .logging_util import (
    create_user,
    delete_user,
    list_users,
    load_global_config,
    load_user_config,
    log,
    save_global_config,
    save_user_config,
    setup_file_logging,
)
from .models import (
    NPC_STATUSES,
    ChapterSummary,
    ClockData,
    ClockEvent,
    CurrentAct,
    DirectorGuidance,
    EngineConfig,
    GameState,
    MemoryEntry,
    NarrationEntry,
    NpcData,
    NpcEvolution,
    PossibleEnding,
    Revelation,
    RollResult,
    SceneLogEntry,
    StoryAct,
    StoryBlueprint,
    TurnSnapshot,
)
from .parser import parse_narrator_response
from .persistence import (
    delete_save,
    list_saves_with_info,
    load_game,
    save_game,
)
from .prompt_builders import build_action_prompt, build_dialog_prompt, build_new_game_prompt
from .story_state import get_current_act
