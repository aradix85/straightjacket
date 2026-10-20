from ...logging_util import log
from ...models import GameState, NpcData
from ..config import gm
from ..questions import answers
from .matching import normalize_for_match, sanitize_npc_name
from .memory import consolidate_memory


def new_npc(
    *,
    id: str,
    name: str,
    disposition: str,
    status: str,
    name_rolled: bool,
    description: str,
    agenda: str,
    instinct: str,
    secrets: list[str],
    aliases: list[str],
    last_location: str,
    introduced: bool,
) -> NpcData:
    return NpcData(
        id=id,
        name=name,
        disposition=disposition,
        status=status,
        name_rolled=name_rolled,
        description=description,
        agenda=agenda,
        instinct=instinct,
        arc="",
        secrets=secrets,
        memory=[],
        introduced=introduced,
        aliases=aliases,
        importance_accumulator=0,
        last_reflection_scene=0,
        last_location=last_location,
        needs_reflection=False,
        gather_count=0,
    )


def retire_distant_npcs(game: GameState) -> None:
    max_active = gm().npc.max_active
    active = [n for n in game.npcs if n.status == "active"]
    if len(active) <= max_active:
        return

    def relevance(npc: NpcData) -> int:
        last_scene = max((m.scene for m in npc.memory), default=0)

        dd = gm().description_dedup
        score = last_scene + answers().closeness(game, npc.id) * dd.bond_multiplier
        if not npc.memory or last_scene >= game.narrative.scene_count:
            score += dd.identity_score_delta
        return score

    active.sort(key=relevance)
    to_demote = len(active) - max_active
    for npc in active[:to_demote]:
        npc.status = "background"
        log(f"[NPC] Demoted to background: {npc.name}")


def reactivate_npc(npc: NpcData, reason: str, force: bool = False) -> None:
    if npc.status == "deceased":
        if force:
            npc.status = "active"
            log(f"[NPC] Resurrected deceased NPC: {npc.name} (reason: {reason})")
        else:
            log(f"[NPC] Refused reactivation of deceased NPC: {npc.name}")
        return
    if npc.status in gm().npc_status_groups.reactivatable:
        log(f"[NPC] Reactivated {npc.status} NPC: {npc.name} (reason: {reason})")
        npc.status = "active"


def rename_npc(npc: NpcData, new_name: str, extra_aliases: list[str]) -> None:
    new_norm = normalize_for_match(new_name)
    if npc.name and normalize_for_match(npc.name) not in {normalize_for_match(a) for a in npc.aliases}:
        npc.aliases.append(npc.name)
    npc.name = new_name
    npc.aliases = [a for a in npc.aliases if normalize_for_match(a) != new_norm]
    for alias in extra_aliases:
        alias_norm = normalize_for_match(alias)
        if alias_norm != new_norm and alias_norm not in {normalize_for_match(a) for a in npc.aliases}:
            npc.aliases.append(alias)


def merge_npc_identity(existing: NpcData, new_name: str, new_desc: str = "", *, game: GameState) -> None:
    old_name = existing.name
    new_name = new_name.strip()
    clean_name, extra_aliases = sanitize_npc_name(new_name)
    new_name = clean_name
    if normalize_for_match(old_name) == normalize_for_match(new_name):
        log(f"[NPC] Identity merge skipped: '{old_name}' → '{new_name}' (same name)")
        return
    rename_npc(existing, new_name, extra_aliases)
    if new_desc and not existing.description:
        existing.description = new_desc
    if existing.status in gm().npc_status_groups.reactivatable:
        reactivate_npc(existing, reason=f"identity revealed as {new_name}")

    _transfer_clocks(game, old_name, new_name)
    log(f"[NPC] Identity merged: '{old_name}' → '{new_name}' (aliases: {existing.aliases})")


def _transfer_clocks(game: GameState, old_name: str, new_name: str) -> None:
    old_name_norm = normalize_for_match(old_name)
    for clock in game.world.clocks:
        if clock.owner_kind != "npc" or clock.owner_id is None:
            continue
        if normalize_for_match(clock.owner_id) == old_name_norm:
            clock.owner_id = new_name
            log(f"[Clock] Owner of '{clock.name}': '{old_name}' → '{new_name}'")


def sanitize_aliases(npc: NpcData) -> None:
    name = npc.name
    dd = gm().description_dedup
    seen = set()
    clean = []
    for a in npc.aliases:
        a_stripped = a.strip()
        low = a_stripped.lower()
        if not a_stripped or low in seen or low == name.lower():
            continue
        if len(a_stripped.split()) > dd.max_alias_word_count:
            continue
        seen.add(low)
        clean.append(a_stripped)
    npc.aliases = clean


def _npc_richness(npc: NpcData, game: GameState) -> int:
    dd = gm().description_dedup
    return (
        len(npc.memory) * dd.richness_memory
        + bool(npc.agenda) * dd.richness_aim
        + bool(npc.instinct) * dd.richness_aim
        + answers().closeness(game, npc.id) * dd.richness_memory
        + bool(npc.description) * dd.richness_other
    )


def _absorb_richer_duplicate_fields(original: NpcData, dup: NpcData) -> None:
    if dup.description:
        original.description = dup.description
    if dup.agenda:
        original.agenda = dup.agenda
    if dup.instinct:
        original.instinct = dup.instinct
    if dup.disposition != gm().npc.default_new_npc_disposition:
        original.disposition = dup.disposition
    if dup.last_location:
        original.last_location = dup.last_location
    if dup.secrets:
        original.secrets.extend(s for s in dup.secrets if s not in original.secrets)
    if dup.last_reflection_scene > original.last_reflection_scene:
        original.last_reflection_scene = dup.last_reflection_scene
    if dup.needs_reflection:
        original.needs_reflection = True


def _fill_empty_fields_from_duplicate(original: NpcData, dup: NpcData) -> None:
    if not original.description and dup.description:
        original.description = dup.description
    if not original.agenda and dup.agenda:
        original.agenda = dup.agenda
    if not original.instinct and dup.instinct:
        original.instinct = dup.instinct


def _merge_aliases_and_location(original: NpcData, dup: NpcData) -> None:
    known_norms = {normalize_for_match(a) for a in original.aliases} | {normalize_for_match(original.name)}
    for alias in [dup.name, *dup.aliases]:
        alias_norm = normalize_for_match(alias)
        if alias_norm not in known_norms:
            original.aliases.append(alias)
            known_norms.add(alias_norm)
    if dup.last_location and not original.last_location:
        original.last_location = dup.last_location


def _take_over_list_entry(game: GameState, original: NpcData, dup: NpcData) -> None:
    entries = game.narrative.characters_list
    dup_entry = next((c for c in entries if c.id == dup.id), None)
    if dup_entry is None:
        return
    own_entry = next((c for c in entries if c.id == original.id), None)
    if own_entry is None:
        dup_entry.id, dup_entry.name = original.id, original.name
        return
    own_entry.weight = min(own_entry.weight + dup_entry.weight, gm().random_events.list_weight_max)
    entries.remove(dup_entry)


def absorb_npc(game: GameState, original: NpcData, dup: NpcData) -> None:
    original.memory.extend(dup.memory)
    original.importance_accumulator = original.importance_accumulator + dup.importance_accumulator

    if _npc_richness(dup, game) > _npc_richness(original, game):
        _absorb_richer_duplicate_fields(original, dup)
        log(
            f"[NPC] Absorb: '{dup.name}' ({dup.id}) was richer — "
            f"its fields promoted into '{original.name}' ({original.id})"
        )
    else:
        _fill_empty_fields_from_duplicate(original, dup)

    _merge_aliases_and_location(original, dup)
    answers().merge_npcs(game, original, dup)
    _transfer_clocks(game, dup.name, original.name)
    _take_over_list_entry(game, original, dup)

    game.npcs.remove(dup)
    log(f"[NPC] Absorbed '{dup.name}' ({dup.id}) into '{original.name}' ({original.id}): {len(dup.memory)} memories")
    sanitize_aliases(original)
    consolidate_memory(original)


def absorb_duplicate_npc(game: GameState, original: NpcData, merged_name: str) -> None:
    merged_norm = normalize_for_match(merged_name)
    for dup in game.npcs:
        if dup is original:
            continue
        if normalize_for_match(dup.name) == merged_norm or merged_norm in {normalize_for_match(a) for a in dup.aliases}:
            absorb_npc(game, original, dup)
            return
