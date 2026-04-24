"""NPC activation: TF-IDF relevance scoring and prompt context selection."""

import math
from typing import TYPE_CHECKING

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, NpcData
from .lifecycle import reactivate_npc
from .matching import find_npc
from .bond import get_npc_bond

if TYPE_CHECKING:
    from ..models import BrainResult

# TF-IDF NPC RELEVANCE SCORING (zero-dependency implementation)
# Replaces keyword-based activation. TF-IDF automatically weights rare/distinctive
# words higher (proper nouns > common words), works across all languages.


def compute_npc_tfidf_scores(npcs: list[NpcData], query_text: str) -> dict[str, float]:
    """Compute TF-IDF cosine similarity between query_text and each NPC's profile.
    Returns {npc_id: similarity_score}. Zero-dependency implementation."""
    if not query_text or not npcs:
        return {}

    _tf = eng().tf_idf
    min_tok = _tf.token_min_length

    # Tokenize: lowercase, split on non-alpha, filter short tokens
    def _tokenize(text: str) -> list[str]:
        return [w for w in text.lower().split() if len(w) >= min_tok and w.isalpha()]

    # Build NPC documents: combine name, description, agenda, aliases, memory events
    docs = {}  # npc_id → token list
    for npc in npcs:
        if npc.status not in ("active", "background"):
            continue
        npc_id = npc.id
        parts = [
            npc.name,
            npc.description,
            npc.agenda,
            " ".join(npc.aliases),
        ]
        # Include recent memory events
        for m in npc.memory[-_tf.memory_window :]:
            parts.append(m.event)
        docs[npc_id] = _tokenize(" ".join(parts))

    if not docs:
        return {}

    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return {}

    # Document frequency: how many docs contain each term
    all_docs = list(docs.values()) + [query_tokens]
    n_docs = len(all_docs)
    df: dict[str, int] = {}
    for doc in all_docs:
        seen = set(doc)
        for term in seen:
            df[term] = df.get(term, 0) + 1

    # IDF: log(N / df) — standard formulation
    idf = {}
    for term, count in df.items():
        idf[term] = math.log(n_docs / count) if count > 0 else 0

    # TF-IDF vectors
    def _tfidf_vector(tokens: list[str]) -> dict[str, float]:
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        # Normalize TF by document length. Empty token lists never reach here
        # (caller short-circuits on `if not tokens`) but guard anyway.
        if not tokens:
            return {}
        doc_len = len(tokens)
        return {t: (count / doc_len) * idf.get(t, 0) for t, count in tf.items()}

    query_vec = _tfidf_vector(query_tokens)
    _q_sumsq = sum(v * v for v in query_vec.values())
    query_norm = math.sqrt(_q_sumsq) if _q_sumsq > 0 else 1.0

    # Cosine similarity for each NPC
    scores = {}
    for npc_id, tokens in docs.items():
        if not tokens:
            scores[npc_id] = 0.0
            continue
        doc_vec = _tfidf_vector(tokens)
        _d_sumsq = sum(v * v for v in doc_vec.values())
        doc_norm = math.sqrt(_d_sumsq) if _d_sumsq > 0 else 1.0

        # Dot product
        dot = sum(query_vec.get(t, 0) * doc_vec.get(t, 0) for t in set(query_vec) | set(doc_vec))
        scores[npc_id] = dot / (query_norm * doc_norm)

    return scores


# NPC ACTIVATION FOR PROMPT


def _build_scan_text(brain: "BrainResult", game: "GameState", player_input: str) -> str:
    """Collect all text that might signal which NPCs are relevant this turn."""
    _tf = eng().tf_idf
    scan_parts = [
        player_input,
        brain.player_intent or "",
        brain.approach or "",
        game.world.current_scene_context or "",
        game.world.current_location or "",
    ]
    for s in game.narrative.session_log[-_tf.session_window :]:
        scan_parts.append(s.summary)
    return " ".join(scan_parts).lower()


def _score_npc(
    npc: NpcData,
    target_id: str | None,
    scan_text: str,
    tfidf: float,
    game: "GameState",
) -> tuple[float, list[str]]:
    """Return (score, reasons) for a single NPC. Six signals:
    direct target, name match, alias match, TF-IDF similarity, location match,
    recent interaction.
    """
    _scores = eng().activation_scores
    _tf = eng().tf_idf
    score = 0.0
    reasons: list[str] = []
    npc_name_lower = npc.name.lower()

    if target_id and (npc.id == target_id or npc_name_lower == target_id.lower()):
        score += _scores.target
        reasons.append("target")

    if npc_name_lower in scan_text:
        score += _scores.name_match
        reasons.append("name")
    else:
        for part in npc_name_lower.split():
            if len(part) >= _tf.token_min_length and part in scan_text:
                score += _scores.name_part
                reasons.append(f"part:{part}")
                break

    for alias in npc.aliases:
        if alias.lower() in scan_text:
            score += _scores.alias_match
            reasons.append(f"alias:{alias}")
            break

    if tfidf > _tf.score_floor:
        tfidf_contrib = min(_tf.memory_score_cap, tfidf * _tf.memory_score_multiplier)
        score += tfidf_contrib
        reasons.append(f"tfidf:{tfidf:.2f}")

    npc_desc = (npc.description + " " + npc.agenda).lower()
    if game.world.current_location and game.world.current_location.lower() in npc_desc:
        score += _scores.location_match
        reasons.append("location")

    recent_scenes = [m.scene for m in npc.memory[-_tf.recency_window :]]
    if recent_scenes and max(recent_scenes) >= game.narrative.scene_count - _tf.recency_offset:
        score += _scores.recent_interaction
        reasons.append("recent")

    return score, reasons


def _cap_activated_overflow(
    activated: list[NpcData], mentioned: list[NpcData], target_id: str | None, game: "GameState"
) -> tuple[list[NpcData], list[NpcData]]:
    """Enforce the max_activated hard limit. Overflow (lowest-bond non-target
    NPCs) drops from activated to mentioned.
    """
    _max_activated = eng().npc.max_activated
    if len(activated) <= _max_activated:
        return activated, mentioned

    target_npc = find_npc(game, target_id) if target_id else None
    non_target = [n for n in activated if n is not target_npc]
    non_target.sort(key=lambda n: get_npc_bond(game, n.id), reverse=True)
    overflow = non_target[_max_activated - (1 if target_npc else 0) :]
    activated = [n for n in activated if n not in overflow]
    mentioned = mentioned + overflow
    return activated, mentioned


def _recursive_activation(activated: list[NpcData], mentioned: list[NpcData], game: "GameState") -> list[NpcData]:
    """If an activated NPC's secrets/agenda references another NPC by name,
    surface that NPC as 'mentioned'. Stops at max_recursive, and after the
    first activated NPC that produces any references.
    """
    secondary: list[NpcData] = []
    for npc in activated:
        ref_text = " ".join(npc.secrets) + " " + npc.agenda
        if not ref_text.strip():
            continue
        for other in game.npcs:
            if other in activated or other in mentioned or other in secondary:
                continue
            if other.status not in ("active", "background"):
                continue
            other_name = other.name.lower()
            if other_name and other_name in ref_text.lower():
                secondary.append(other)
                if len(secondary) >= eng().activation_scores.max_recursive:
                    break
        if secondary:
            break
    return secondary


def activate_npcs_for_prompt(
    game: "GameState", brain: "BrainResult", player_input: str
) -> tuple[list[NpcData], list[NpcData], dict]:
    """Decide which NPCs get full context vs name-only mention in narrator prompt.

    Four phases: build scan text, score each active/background NPC, enforce
    max_activated overflow, then recursively surface NPCs referenced in secrets/agenda.

    Returns (activated_npcs, mentioned_npcs, activation_debug).
    activated = full context (memories, secrets, agenda)
    mentioned = name + disposition only
    activation_debug = {npc_name: {score, reasons, status}} for diagnostics
    """
    target_id = brain.target_npc
    scan_text = _build_scan_text(brain, game, player_input)
    tfidf_scores = compute_npc_tfidf_scores(game.npcs, scan_text)

    _e = eng()
    activated: list[NpcData] = []
    mentioned: list[NpcData] = []
    activation_debug: dict = {}

    for npc in game.npcs:
        if npc.status not in ("active", "background"):
            continue

        tfidf = tfidf_scores.get(npc.id, 0.0)
        score, reasons = _score_npc(npc, target_id, scan_text, tfidf, game)

        if score >= _e.npc.activation_threshold:
            activated.append(npc)
            activation_debug[npc.name] = {"score": round(score, 2), "reasons": reasons, "status": "activated"}
            if npc.status == "background":
                reactivate_npc(npc, reason=f"context activation (score={score:.2f})")
        elif score >= _e.npc.mention_threshold:
            mentioned.append(npc)
            activation_debug[npc.name] = {"score": round(score, 2), "reasons": reasons, "status": "mentioned"}
        elif reasons:
            activation_debug[npc.name] = {"score": round(score, 2), "reasons": reasons, "status": "inactive"}

    activated, mentioned = _cap_activated_overflow(activated, mentioned, target_id, game)
    mentioned = mentioned + _recursive_activation(activated, mentioned, game)

    log(f"[NPC Activation] Activated: {[n.name for n in activated]}, Mentioned: {[n.name for n in mentioned]}")

    return activated, mentioned, activation_debug
