import re
from typing import Any

from ..engine.engine_loader import eng
from ..engine.format_utils import describe_by_threshold
from ..engine.gamemaster.config import gm
from ..engine.gamemaster.questions import answers
from ..engine.models import GameState
from ..engine.ruleset.bond import bonded_tracks, get_npc_bond
from ..engine.ruleset.config import rules
from ..engine.ruleset.datasworn import load_ruleset
from ..engine.ruleset.impacts import impact_label
from ..engine.ruleset.progress import filled_boxes, menace_boxes, ranks
from ..engine.ruleset.stats import stat_descriptions
from ..engine.ruleset.threats import active_threats
from ..engine.ruleset.tracks import active_tracks
from ..engine.setting.packages import list_packages, load_package
from ..engine.story_state import get_current_act
from ..i18n import t


def _status_resources_line(game: GameState) -> str:
    _defaults = eng().ai_text.narrator_defaults
    meters = game.resources.meters
    return t(
        "status.resources",
        name=game.player_name,
        location=game.world.current_location or _defaults["unknown_location"],
        time=t(f"time.{game.world.time_of_day}"),
        **{
            meter: describe_by_threshold(meters[meter], levels)
            for meter, levels in eng().status_descriptions.meters.items()
        },
    )


def _status_impact_lines(game: GameState) -> list[str]:
    if not game.impacts:
        return []
    return [t("status.impacts", impacts=", ".join(impact_label(game, k) for k in game.impacts))]


def _status_track_lines(game: GameState) -> list[str]:
    track_desc = eng().status_descriptions.track
    return [
        t("status.tracks", name=tr.name, progress=describe_by_threshold(filled_boxes(tr), track_desc))
        for tr in active_tracks(game)
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
    if any(filled_boxes(track) > 0 for track in camp.legacy.values()):
        legacy_desc = eng().status_descriptions.legacy
        items = [
            t("status.legacy_item", name=track.name, progress=describe_by_threshold(filled_boxes(track), legacy_desc))
            for track in camp.legacy.values()
        ]
        lines.append(t("status.legacy", tracks="; ".join(items)))
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
    active = active_tracks(game)
    bonded = bonded_tracks(game)
    if not active and not bonded:
        return t("status.no_tracks")

    lines = [t("status.track_bonded", name=tr.name) for tr in bonded]
    track_desc_map = eng().status_descriptions.track
    cp = game.world.combat_position
    position = eng().status_descriptions.combat_position[cp] if cp else ""
    for tr in active:
        progress = describe_by_threshold(filled_boxes(tr), track_desc_map)
        lines.append(t(f"status.track_{tr.track_type}", name=tr.name, progress=progress, position=position))

    return "\n".join(lines)


def build_threats_status(game: GameState) -> str:
    active = active_threats(game)
    if not active:
        return t("status.no_threats")

    lines = []
    menace_desc = eng().status_descriptions.menace
    for th in active:
        urgency = describe_by_threshold(menace_boxes(th), menace_desc)
        lines.append(t("status.threat", name=th.name, urgency=urgency))

    return "\n".join(lines)


def build_creation_options() -> dict[str, Any]:
    settings = []
    for pkg_id in list_packages():
        pkg = load_package(pkg_id)
        if not pkg.playable:
            continue

        own = load_ruleset(pkg_id).setting_file
        paths = []
        for asset in own.assets_of("path"):
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
            for table_id, table in pkg.name_tables(gm().naming.category).items():
                name_tables[table_id] = [row.text for row in table.rows]

        backstory_prompts = []
        if flow.has_backstory_oracle:
            backstory_prompts = [row.text for row in pkg.oracle_table(pkg.oracle_paths.backstory).rows]

        starting_assets = []
        for cat in flow.starting_asset_categories:
            for asset in own.assets_of(cat):
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
                "stats": list(stat_descriptions(pkg_id)),
            }
        )

    stat_array = rules().stats.creation_array
    return {
        "settings": settings,
        "stat_constraints": {
            "target_sum": sum(stat_array),
            "min": min(stat_array),
            "max": max(stat_array),
        },
        "creation_defaults": {
            "max_paths": rules().creation.max_paths,
            "max_starting_assets": rules().creation.max_starting_assets,
            "background_vow_default_rank": rules().creation.background_vow_default_rank,
            "pronoun_options": rules().creation.pronoun_options,
            "vow_ranks": ranks(),
        },
        "tones": [{"id": tone, "label": t(f"tone.{tone}")} for tone in gm().story.tones],
    }


def build_succession_summary(game: GameState) -> dict[str, Any]:
    record = game.campaign.predecessors[-1]
    end_reason = record.end_reason
    title_key = f"succession.title_{end_reason}"
    headline_key = f"succession.headline_{end_reason}"

    inheritance = [
        t(
            f"succession.legacy_{answers().outcome(roll.result)}",
            track=t(f"succession.legacy_track_{roll.track_name}"),
        )
        for roll in record.inheritance_rolls
    ]

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
