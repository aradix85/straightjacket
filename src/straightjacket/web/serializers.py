from typing import Any
import re

from ..engine.engine_loader import eng
from ..engine.format_utils import describe_by_threshold
from ..engine.mechanics.impacts import impact_label
from ..engine.models import GameState
from ..engine.npc import get_npc_bond
from ..engine.story_state import get_current_act
from ..engine.datasworn.settings import list_packages, load_package
from ..i18n import t


def _status_resources_line(game: GameState) -> str:
    _defaults = eng().ai_text.narrator_defaults
    r = game.resources
    return t(
        "status.resources",
        name=game.player_name,
        location=game.world.current_location or _defaults["unknown_location"],
        time=t(f"time.{game.world.time_of_day}"),
        health=describe_by_threshold(r.health, eng().status_descriptions.health),
        spirit=describe_by_threshold(r.spirit, eng().status_descriptions.spirit),
        supply=describe_by_threshold(r.supply, eng().status_descriptions.supply),
    )


def _status_impact_lines(game: GameState) -> list[str]:
    if not game.impacts:
        return []
    return [t("status.impacts", impacts=", ".join(impact_label(game, k) for k in game.impacts))]


def _status_track_lines(game: GameState) -> list[str]:
    track_desc = eng().status_descriptions.track
    return [
        t("status.tracks", name=tr.name, progress=describe_by_threshold(tr.filled_boxes, track_desc))
        for tr in game.progress_tracks
        if tr.status == "active"
    ]


def _status_npc_lines(game: GameState) -> list[str]:
    bond_desc = eng().status_descriptions.bond
    lines: list[str] = []
    for n in game.npcs:
        disp_label = t(f"disposition.{n.disposition}")
        bond = describe_by_threshold(get_npc_bond(game, n.id), bond_desc)
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
        urgency = describe_by_threshold(100 * c.filled // c.segments, clock_desc)
        lines.append(t("status.clock", name=c.name, urgency=urgency))
    return lines


def _status_story_arc_lines(game: GameState) -> list[str]:
    if game.narrative.story_blueprint is None:
        return []
    act = get_current_act(game)
    return [
        t(
            "status.act",
            title=act.title,
            phase=t(f"story.{act.phase}"),
            progress=eng().status_descriptions.act_progress[act.progress],
        )
    ]


def _status_xp_and_legacy_lines(game: GameState) -> list[str]:
    lines: list[str] = []
    camp = game.campaign
    if camp.xp_available > 0 or camp.xp_spent > 0:
        lines.append(t("status.xp", xp=describe_by_threshold(camp.xp_available, eng().status_descriptions.xp)))
    if any(lt.filled_boxes > 0 for lt in (camp.legacy_quests, camp.legacy_bonds, camp.legacy_discoveries)):
        legacy_desc = eng().status_descriptions.legacy
        lines.append(
            t(
                "status.legacy",
                quests=t(
                    "status.legacy_item",
                    name=camp.legacy_quests.name,
                    progress=describe_by_threshold(camp.legacy_quests.filled_boxes, legacy_desc),
                ),
                bonds=t(
                    "status.legacy_item",
                    name=camp.legacy_bonds.name,
                    progress=describe_by_threshold(camp.legacy_bonds.filled_boxes, legacy_desc),
                ),
                discoveries=t(
                    "status.legacy_item",
                    name=camp.legacy_discoveries.name,
                    progress=describe_by_threshold(camp.legacy_discoveries.filled_boxes, legacy_desc),
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
        track_desc = describe_by_threshold(tr.filled_boxes, track_desc_map)
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
        urgency = describe_by_threshold(th.menace_filled_boxes, menace_desc)
        lines.append(t("status.threat", name=th.name, urgency=urgency))

    return "\n".join(lines)


def build_creation_options() -> dict[str, Any]:
    _e = eng()
    settings = []
    for pkg_id in list_packages():
        pkg = load_package(pkg_id)
        if not pkg.playable:
            continue

        paths = []
        for asset in pkg.data.paths():
            asset_id = asset["_id"].rsplit("/", 1)[-1]
            paths.append({"id": asset_id, "title": asset["name"]})

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
                        }
                    )

                truths.append(
                    {
                        "id": truth_id,
                        "name": truth_data["name"],
                        "options": options,
                    }
                )

        name_tables = {}
        if flow.has_name_tables:
            for table_id, table in pkg.name_tables(eng().naming.category).items():
                name_tables[table_id] = [row.text for row in table.rows]

        backstory_prompts = []
        if flow.has_backstory_oracle:
            backstory_prompts = [row.text for row in pkg.oracle_table(pkg.oracle_paths.backstory).rows]

        starting_assets = []
        for cat in flow.starting_asset_categories:
            for asset in pkg.data.assets(cat):
                asset_id = asset["_id"].rsplit("/", 1)[-1]
                starting_assets.append(
                    {
                        "id": asset_id,
                        "title": asset["name"],
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
                "default_tone": pkg.default_tone,
            }
        )

    return {
        "settings": settings,
        "stat_constraints": {
            "names": _e.stats.character_names,
            "target_sum": _e.stats.target_sum,
            "min": _e.stats.min,
            "max": _e.stats.max,
        },
        "creation_defaults": {
            "max_paths": _e.creation.max_paths,
            "max_starting_assets": _e.creation.max_starting_assets,
            "background_vow_default_rank": _e.creation.background_vow_default_rank,
            "pronoun_options": _e.creation.pronoun_options,
            "vow_ranks": list(_e.legacy.ticks_by_rank.keys()),
        },
        "tones": [{"id": tone, "label": t(f"tone.{tone}")} for tone in _e.story.kishotenketsu_probability],
    }


def build_succession_summary(game: GameState) -> dict[str, Any]:
    record = game.campaign.predecessors[-1]
    end_reason = record.end_reason
    title_key = f"succession.title_{end_reason}"
    headline_key = f"succession.headline_{end_reason}"

    inheritance: list[str] = []
    for roll in record.inheritance_rolls:
        if roll.result == "STRONG_HIT":
            text_key = "succession.legacy_full"
        elif roll.result == "WEAK_HIT":
            text_key = "succession.legacy_partial"
        else:
            text_key = "succession.legacy_lost"
        inheritance.append(t(text_key, track=t(f"succession.legacy_track_{roll.track_name}")))

    return {
        "title": t(title_key),
        "headline": t(headline_key, predecessor=record.player_name),
        "history": t(
            "succession.predecessor_history",
            name=record.player_name,
            chapters=record.chapters_played,
            scenes=record.scenes_played,
        ),
        "inheritance": inheritance,
    }


_DIALOG_QUOTES = re.compile(
    r"(\u201c)([^\u201c\u201d\n]{1,600}?)(\u201d)"
    r'|(")([^"\n]{1,600}?)(")'
    r"|(\u2018)([^\u2018\u2019\n]{1,600}?)(\u2019)"
)


def highlight_dialog(text: str) -> str:
    def _wrap(match: re.Match[str]) -> str:
        groups = match.groups()
        start = next(i for i in (0, 3, 6) if groups[i] is not None)
        open_q, content, close_q = groups[start], groups[start + 1], groups[start + 2]
        inner = content.strip()
        if not inner:
            return open_q + content + close_q
        return f'{open_q}<span class="dialog">{inner}</span>{close_q}'

    return _DIALOG_QUOTES.sub(_wrap, text)
