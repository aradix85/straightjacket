#!/usr/bin/env python3
"""
Straightjacket AI Package
====================
Re-exports public symbols.
  from engine.ai import call_brain, call_narrator, ...
"""

__all__ = [
    "AIProvider",
    "AIResponse",
    "AnthropicProvider",
    "CHAPTER_SUMMARY_OUTPUT_SCHEMA",
    "CORRECTION_OUTPUT_SCHEMA",
    "DIRECTOR_OUTPUT_SCHEMA",
    "NARRATOR_METADATA_SCHEMA",
    "OPENING_SETUP_SCHEMA",
    "OpenAICompatibleProvider",
    "STORY_ARCHITECT_OUTPUT_SCHEMA",
    "apply_narrator_metadata",
    "call_brain",
    "call_chapter_summary",
    "call_narrator",
    "call_narrator_metadata",
    "call_opening_setup",
    "call_recap",
    "call_story_architect",
    "clear_provider_cache",
    "create_with_retry",
    "get_brain_output_schema",
    "get_provider",
    "post_process_response",
]


from .api_client import clear_provider_cache, get_provider
from .architect import call_chapter_summary, call_recap, call_story_architect
from .brain import call_brain
from .metadata import apply_narrator_metadata
from .narrator import call_narrator, call_narrator_metadata, call_opening_setup
from .provider_anthropic import AnthropicProvider

# Provider abstraction
from .provider_base import (
    AIProvider,
    AIResponse,
    create_with_retry,
    post_process_response,
)
from .provider_openai import OpenAICompatibleProvider
from .schemas import (
    CHAPTER_SUMMARY_OUTPUT_SCHEMA,
    CORRECTION_OUTPUT_SCHEMA,
    DIRECTOR_OUTPUT_SCHEMA,
    NARRATOR_METADATA_SCHEMA,
    OPENING_SETUP_SCHEMA,
    STORY_ARCHITECT_OUTPUT_SCHEMA,
    get_brain_output_schema,
)
