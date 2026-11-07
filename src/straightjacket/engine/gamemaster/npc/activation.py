import math
from collections import Counter

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.npc.lifecycle import reactivate_npc
from straightjacket.engine.gamemaster.npc.matching import find_npc, named_in, proper_name_words, stands_in
from straightjacket.engine.gamemaster.questions import answers
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import BrainResult, GameState, NpcData


def _tokenize(text: str) -> list[str]:
    min_tok = gm().tf_idf.token_min_length
    return [w for w in text.lower().split() if len(w) >= min_tok and w.isalpha()]


def _npc_documents(npcs: list[NpcData]) -> dict[str, list[str]]:
    window = gm().tf_idf.memory_window
    docs = {}
    for npc in npcs:
        if npc.status not in gm().npc_status_groups.in_play:
            continue
        parts = [npc.name, npc.description, npc.agenda, " ".join(npc.aliases)]
        parts.extend(m.event for m in npc.memory[-window:])
        docs[npc.id] = _tokenize(" ".join(parts))
    return docs


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    doc_len = len(tokens)
    return {t: (count / doc_len) * idf[t] for t, count in Counter(tokens).items()}


def _norm(vector: dict[str, float]) -> float:
    sumsq = sum(v * v for v in vector.values())
    return math.sqrt(sumsq) if sumsq > 0 else 1.0


def compute_npc_tfidf_scores(npcs: list[NpcData], query_text: str) -> dict[str, float]:
    docs = _npc_documents(npcs)
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return {}

    all_docs = [*list(docs.values()), query_tokens]
    df = Counter(term for doc in all_docs for term in set(doc))
    idf = {term: math.log(len(all_docs) / count) for term, count in df.items()}

    query_vec = _tfidf_vector(query_tokens, idf)
    query_norm = _norm(query_vec)

    scores = {}
    for npc_id, tokens in docs.items():
        if not tokens:
            scores[npc_id] = 0.0
            continue
        doc_vec = _tfidf_vector(tokens, idf)
        dot = sum(query_vec.get(t, 0) * doc_vec.get(t, 0) for t in set(query_vec) | set(doc_vec))
        scores[npc_id] = dot / (query_norm * _norm(doc_vec))

    return scores


def _build_story_text(brain: BrainResult, game: GameState) -> str:
    tf = gm().tf_idf
    scan_parts = [
        brain.player_intent,
        brain.approach,
        game.world.current_scene_context,
        game.world.current_location,
    ]
    scan_parts.extend(s.summary for s in game.narrative.session_log[-tf.session_window :])
    return " ".join(scan_parts)


def _mentioned(label: str, player_input: str, story_text: str) -> bool:
    return stands_in(label, player_input, ignore_case=True) or stands_in(label, story_text, ignore_case=False)


def _score_npc(
    npc: NpcData,
    game: GameState,
    *,
    target_id: str | None,
    player_input: str,
    story_text: str,
    tfidf: float,
) -> float:
    scores = gm().activation_scores
    tf = gm().tf_idf
    score = 0.0

    if npc.id == target_id:
        score += scores.target

    if _mentioned(npc.name, player_input, story_text):
        score += scores.name_match
    elif any(_mentioned(word, player_input, story_text) for word in proper_name_words(npc)):
        score += scores.name_part

    if any(_mentioned(alias, player_input, story_text) for alias in npc.aliases):
        score += scores.alias_match

    if tfidf > tf.score_floor:
        score += min(tf.memory_score_cap, tfidf * tf.memory_score_multiplier)

    npc_desc = (npc.description + " " + npc.agenda).lower()
    if game.world.current_location and game.world.current_location.lower() in npc_desc:
        score += scores.location_match

    recent_scenes = [m.scene for m in npc.memory[-tf.recency_window :]]
    if recent_scenes and max(recent_scenes) >= game.narrative.scene_count - tf.recency_offset:
        score += scores.recent_interaction

    return score


def _cap_activated_overflow(
    activated: list[NpcData], mentioned: list[NpcData], target_id: str | None, game: GameState
) -> tuple[list[NpcData], list[NpcData]]:
    max_activated = gm().npc.max_activated
    if len(activated) <= max_activated:
        return activated, mentioned

    target_npc = find_npc(game, target_id) if target_id else None
    non_target = [n for n in activated if n is not target_npc]
    non_target.sort(key=lambda n: answers().closeness(game, n.id), reverse=True)
    overflow = non_target[max_activated - (1 if target_npc else 0) :]
    activated = [n for n in activated if n not in overflow]
    mentioned = [*mentioned, *overflow]
    return activated, mentioned


def _recursive_activation(activated: list[NpcData], mentioned: list[NpcData], game: GameState) -> list[NpcData]:
    secondary: list[NpcData] = []
    for npc in activated:
        ref_text = " ".join(npc.secrets) + " " + npc.agenda
        if not ref_text.strip():
            continue
        for other in game.npcs:
            if other in activated or other in mentioned or other in secondary:
                continue
            if other.status not in gm().npc_status_groups.in_play:
                continue
            if named_in(other, ref_text):
                secondary.append(other)
                if len(secondary) >= gm().activation_scores.max_recursive:
                    break
        if secondary:
            break
    return secondary


def activate_npcs_for_prompt(
    game: GameState, brain: BrainResult, player_input: str
) -> tuple[list[NpcData], list[NpcData]]:
    target_id = brain.target_npc
    story_text = _build_story_text(brain, game)
    tfidf_scores = compute_npc_tfidf_scores(game.npcs, f"{player_input} {story_text}")

    activated: list[NpcData] = []
    mentioned: list[NpcData] = []

    for npc in game.npcs:
        if npc.status not in gm().npc_status_groups.in_play:
            continue

        tfidf = tfidf_scores.get(npc.id, 0.0)
        score = _score_npc(
            npc, game, target_id=target_id, player_input=player_input, story_text=story_text, tfidf=tfidf
        )

        if score >= gm().npc.activation_threshold:
            activated.append(npc)
            if npc.status == "background":
                reactivate_npc(npc, reason=f"context activation (score={score:.2f})")
        elif score >= gm().npc.mention_threshold:
            mentioned.append(npc)

    activated, mentioned = _cap_activated_overflow(activated, mentioned, target_id, game)
    mentioned = [*mentioned, *_recursive_activation(activated, mentioned, game)]

    log(f"[NPC Activation] Activated: {[n.name for n in activated]}, Mentioned: {[n.name for n in mentioned]}")

    return activated, mentioned
