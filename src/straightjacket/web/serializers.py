import re

from ..engine.engine_loader import eng
from ..engine.mechanics.impacts import impact_label
from ..engine.models import GameState
from ..engine.npc import get_npc_bond
from ..engine.story_state import get_current_act
from ..engine.datasworn.loader import extract_title
from ..engine.datasworn.settings import list_packages, load_package
from ..engine.logging_util import log
from ..i18n import (
    get_disposition_labels,
    get_story_phase_labels,
    get_time_labels,
    t,
)


def _describe_resource(value: int, descriptions: dict[int, str]) -> str:
    for threshold in sorted(descriptions.keys(), reverse=True):
        if value >= threshold:
            return descriptions[threshold]
    return descriptions[min(descriptions.keys())]


def _status_resources_line(game: GameState) -> str:
    tl = get_time_labels()
    _defaults = eng().ai_text.narrator_defaults
    r = game.resources
    time_label = tl.get(game.world.time_of_day, "") if game.world.time_of_day else ""
    return t(
        "status.resources",
        name=game.player_name,
        location=game.world.current_location or _defaults["unknown_location"],
        time=time_label or _defaults["unknown_time"],
        health=_describe_resource(r.health, eng().status_descriptions.health),
        spirit=_describe_resource(r.spirit, eng().status_descriptions.spirit),
        supply=_describe_resource(r.supply, eng().status_descriptions.supply),
    )


def _status_impact_lines(game: GameState) -> list[str]:
    if not game.impacts:
        return []
    return [t("status.impacts", impacts=", ".join(impact_label(k) for k in game.impacts))]


def _status_track_lines(game: GameState) -> list[str]:
    track_desc = eng().status_descriptions.track
    return [
        t("status.tracks", name=tr.name, progress=_describe_resource(tr.filled_boxes, track_desc))
        for tr in game.progress_tracks
        if tr.status == "active"
    ]


def _status_npc_lines(game: GameState) -> list[str]:
    dl = get_disposition_labels()
    bond_desc = eng().status_descriptions.bond
    lines: list[str] = []
    for n in game.npcs:
        disp_label = dl.get(n.disposition, n.disposition)
        bond = _describe_resource(get_npc_bond(game, n.id), bond_desc)
        if n.status == "deceased":
            lines.append(t("status.npc_deceased", name=n.name))
        elif n.status == "background":
            lines.append(t("status.npc_background", name=n.name, disposition=disp_label, bond=bond))
        elif n.status == "active":
            lines.append(t("status.npc", name=n.name, disposition=disp_label, bond=bond))
    return lines


def _status_clock_lines(game: GameState) -> list[str]:
    lines: list[str] = []
    clock_desc = eng().status_descriptions.clock
    for c in game.world.clocks:
        if c.fired:
            lines.append(t("status.clock_fired", name=c.name))
            continue
        ratio = c.filled / c.segments if c.segments > 0 else 0
        if ratio >= 0.75:
            urgency = clock_desc["late"]
        elif ratio >= 0.35:
            urgency = clock_desc["mid"]
        else:
            urgency = clock_desc["early"]
        lines.append(t("status.clock", name=c.name, urgency=urgency))
    return lines


def _status_story_arc_lines(game: GameState) -> list[str]:
    bp = game.narrative.story_blueprint
    if not (bp and bp.acts):
        return []
    pl = get_story_phase_labels()
    act = get_current_act(game)
    return [
        t(
            "status.act",
            title=act.title,
            phase=pl.get(act.phase, act.phase),
            progress=act.progress,
        )
    ]


def _status_xp_and_legacy_lines(game: GameState) -> list[str]:
    lines: list[str] = []
    camp = game.campaign
    if camp.xp_available > 0 or camp.xp_spent > 0:
        lines.append(t("status.xp", xp=_describe_resource(camp.xp_available, eng().status_descriptions.xp)))
    if any(lt.filled_boxes > 0 for lt in (camp.legacy_quests, camp.legacy_bonds, camp.legacy_discoveries)):
        legacy_desc = eng().status_descriptions.legacy
        lines.append(
            t(
                "status.legacy",
                quests=t(
                    "status.legacy_item",
                    name=camp.legacy_quests.name,
                    progress=_describe_resource(camp.legacy_quests.filled_boxes, legacy_desc),
                ),
                bonds=t(
                    "status.legacy_item",
                    name=camp.legacy_bonds.name,
                    progress=_describe_resource(camp.legacy_bonds.filled_boxes, legacy_desc),
                ),
                discoveries=t(
                    "status.legacy_item",
                    name=camp.legacy_discoveries.name,
                    progress=_describe_resource(camp.legacy_discoveries.filled_boxes, legacy_desc),
                ),
            )
        )
    return lines


def build_narrative_status(game: GameState) -> str:
    lines: list[str] = [_status_resources_line(game)]
    lines.extend(_status_impact_lines(game))
    lines.extend(_status_track_lines(game))
    lines.extend(_status_npc_lines(game))
    lines.extend(_status_clock_lines(game))
    lines.extend(_status_story_arc_lines(game))
    lines.extend(_status_xp_and_legacy_lines(game))
    return "\n".join(lines)


def build_tracks_status(game: GameState) -> str:
    active = [tr for tr in game.progress_tracks if tr.status == "active"]
    if not active:
        return t("status.no_tracks")

    lines = []
    track_desc_map = eng().status_descriptions.track
    combat_pos_desc = eng().status_descriptions.combat_position
    for tr in active:
        track_desc = _describe_resource(tr.filled_boxes, track_desc_map)
        if tr.track_type == "combat":
            cp = game.world.combat_position
            pos_desc = combat_pos_desc[cp] if cp else ""
            lines.append(t("status.track_combat", name=tr.name, progress=track_desc, position=pos_desc))
        elif tr.track_type == "expedition":
            lines.append(t("status.track_expedition", name=tr.name, progress=track_desc))
        elif tr.track_type == "scene_challenge":
            lines.append(t("status.track_scene_challenge", name=tr.name, progress=track_desc))
        else:
            lines.append(t("status.tracks", name=tr.name, progress=track_desc))

    return "\n".join(lines)


def build_threats_status(game: GameState) -> str:
    active = [th for th in game.threats if th.status == "active"]
    if not active:
        return t("status.no_threats")

    lines = []
    menace_desc = eng().status_descriptions.menace
    for th in active:
        urgency = _describe_resource(th.menace_filled_boxes, menace_desc)
        lines.append(t("status.threat", name=th.name, urgency=urgency))

    return "\n".join(lines)


def build_creation_options() -> dict:
    _e = eng()
    settings = []
    for pkg_id in list_packages():
        if pkg_id == "delve":
            continue
        try:
            pkg = load_package(pkg_id)

            paths = []
            for asset in pkg.data.paths():
                asset_id = asset["_id"].rsplit("/", 1)[-1]
                paths.append({"id": asset_id, "title": extract_title(asset, asset_id)})

            truths = []
            flow = pkg.creation_flow
            if flow.has_truths:
                raw_truths = pkg.data.truths()
                _trunc = eng().truncations
                for truth_id, truth_data in raw_truths.items():
                    options = []

                    for opt in truth_data["options"]:
                        summary_text = opt["summary"] if "summary" in opt else opt["description"]
                        options.append(
                            {
                                "summary": str(summary_text)[: _trunc.prompt_medium],
                                "description": str(opt["description"])[: _trunc.prompt_medium],
                                "quest_starter": str(opt["quest_starter"])[: _trunc.prompt_short],
                            }
                        )

                    truths.append(
                        {
                            "id": truth_id,
                            "name": truth_data.get("name", truth_id),
                            "options": options,
                        }
                    )

            name_tables = {}
            if flow.has_name_tables:
                for table_id, table in pkg.name_tables().items():
                    name_tables[table_id] = [row.text for row in table.rows]

            backstory_prompts = []
            if flow.has_backstory_oracle:
                bs = pkg.backstory_prompts()
                if bs:
                    backstory_prompts = [row.text for row in bs.rows]

            starting_assets = []
            for cat in flow.starting_asset_categories:
                for asset in pkg.data.assets(cat):
                    asset_id = asset["_id"].rsplit("/", 1)[-1]
                    starting_assets.append(
                        {
                            "id": asset_id,
                            "title": extract_title(asset, asset_id),
                            "category": cat,
                        }
                    )

            settings.append(
                {
                    "id": pkg_id,
                    "title": pkg.title,
                    "description": pkg.description,
                    "paths": paths,
                    "truths": truths,
                    "name_tables": name_tables,
                    "backstory_prompts": backstory_prompts,
                    "starting_assets": starting_assets,
                    "creation_flow": {
                        "has_truths": flow.has_truths,
                        "has_backstory_oracle": flow.has_backstory_oracle,
                        "has_name_tables": flow.has_name_tables,
                        "has_ship_creation": flow.has_ship_creation,
                        "starting_asset_categories": flow.starting_asset_categories,
                    },
                }
            )
        except Exception as e:
            log(f"[Web] Failed to load package {pkg_id}: {e}", level="warning")

    return {
        "settings": settings,
        "stat_constraints": {
            "target_sum": _e.stats.target_sum,
            "min": _e.stats.min,
            "max": _e.stats.max,
            "valid_arrays": [list(a) for a in _e.stats.valid_arrays],
        },
        "creation_defaults": {
            "max_paths": _e.creation.max_paths,
            "max_starting_assets": _e.creation.max_starting_assets,
            "background_vow_default_rank": _e.creation.background_vow_default_rank,
            "vow_ranks": list(_e.legacy.ticks_by_rank.keys()),
        },
    }


def build_succession_summary(game: GameState) -> dict:
    if not game.campaign.pending_succession or not game.campaign.predecessors:
        return {"pending": False}

    record = game.campaign.predecessors[-1]
    end_reason = record.end_reason
    title_key = f"succession.title_{end_reason}"
    headline_key = f"succession.headline_{end_reason}"

    track_lines: list[dict] = []
    for roll in record.inheritance_rolls:
        if roll.result == "STRONG_HIT":
            text_key = "succession.legacy_full"
        elif roll.result == "WEAK_HIT":
            text_key = "succession.legacy_partial"
        else:
            text_key = "succession.legacy_lost"
        track_label = t(f"succession.legacy_track_{roll.track_name}")
        track_lines.append(
            {
                "track": roll.track_name,
                "text": t(text_key, track=track_label),
            }
        )

    return {
        "pending": True,
        "title": t(title_key),
        "headline": t(headline_key, predecessor=record.player_name),
        "predecessor": {
            "name": record.player_name,
            "concept": record.character_concept,
            "history": t(
                "succession.predecessor_history",
                name=record.player_name,
                chapters=record.chapters_played,
                scenes=record.scenes_played,
            ),
            "end_reason": end_reason,
        },
        "inheritance": track_lines,
    }


def highlight_dialog(text: str) -> str:
    def _wrap(open_q: str, content: str, close_q: str) -> str:
        inner = content.strip()
        if not inner:
            return open_q + content + close_q
        return f'{open_q}<span class="dialog">{inner}</span>{close_q}'

    text = re.sub(
        r"(\u201c)([^\u201c\u201d\n]{1,600}?)(\u201d)", lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text
    )

    text = re.sub(r'(?<!<span class="dialog">)"([^"\n]{1,600}?)"', lambda m: _wrap('"', m.group(1), '"'), text)

    text = re.sub(
        r"(\u2018)([^\u2018\u2019\n]{1,600}?)(\u2019)", lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text
    )
    return text
