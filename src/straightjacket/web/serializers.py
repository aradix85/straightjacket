#!/usr/bin/env python3
"""State serializers: game state → client-facing text and JSON.

build_narrative_status: plain-text narrative summary for /status command.
build_creation_options: JSON for character creation form.
highlight_dialog: wrap quoted speech in HTML spans.
build_ui_strings: all strings.yaml entries for the client.
"""

import re

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


def build_narrative_status(game: GameState) -> str:
    """Plain-text narrative status for /status and /score commands."""
    dl = get_disposition_labels()
    tl = get_time_labels()
    pl = get_story_phase_labels()

    r = game.resources
    time_label = tl.get(game.world.time_of_day, "") if game.world.time_of_day else ""
    lines = [
        t(
            "status.resources",
            name=game.player_name,
            scene=game.narrative.scene_count,
            location=game.world.current_location or "?",
            time=time_label or "?",
            health=r.health,
            spirit=r.spirit,
            supply=r.supply,
            momentum=r.momentum,
            max_momentum=r.max_momentum,
            chaos=game.world.chaos_factor,
        )
    ]

    # Progress tracks
    for tr in game.progress_tracks:
        lines.append(t("status.tracks", name=tr.name, rank=tr.rank, filled=tr.filled_boxes))

    # NPCs
    for n in game.npcs:
        disp_label = dl.get(n.disposition, n.disposition)
        bond = get_npc_bond(game, n.id)
        if n.status == "deceased":
            lines.append(t("status.npc_deceased", name=n.name))
        elif n.status == "background":
            lines.append(t("status.npc_background", name=n.name, disposition=disp_label, bond=bond, bond_max=10))
        elif n.status == "active":
            lines.append(t("status.npc", name=n.name, disposition=disp_label, bond=bond, bond_max=10))

    # Clocks
    for c in game.world.clocks:
        if c.fired:
            lines.append(t("status.clock_fired", name=c.name))
        else:
            lines.append(t("status.clock", name=c.name, filled=c.filled, segments=c.segments))

    # Story arc
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        lines.append(
            t(
                "status.act",
                n=act.act_number,
                total=act.total_acts,
                title=act.title,
                phase=pl.get(act.phase, act.phase),
                progress=act.progress,
            )
        )

    return "\n".join(lines)


def build_creation_options() -> dict:
    """All character creation data for the client form."""
    from ..engine.engine_loader import eng

    _e = eng()
    settings = []
    for pkg_id in list_packages():
        if pkg_id == "delve":
            continue
        try:
            pkg = load_package(pkg_id)

            # Paths
            paths = []
            for asset in pkg.data.paths():
                asset_id = asset.get("_id", "").rsplit("/", 1)[-1]
                paths.append({"id": asset_id, "title": extract_title(asset, asset_id)})

            # Truths (if setting has them)
            truths = []
            flow = pkg.creation_flow
            if flow.get("has_truths"):
                raw_truths = pkg.data.truths()
                for truth_id, truth_data in raw_truths.items():
                    options = []
                    for opt in truth_data.get("options", []):
                        options.append(
                            {
                                "summary": opt.get("summary", ""),
                                "description": str(opt.get("description", ""))[:300],
                                "quest_starter": str(opt.get("quest_starter", ""))[:200],
                            }
                        )
                    truths.append(
                        {
                            "id": truth_id,
                            "name": truth_data.get("name", truth_id),
                            "options": options,
                        }
                    )

            # Name tables
            name_tables = {}
            if flow.get("has_name_tables"):
                for table_id, table in pkg.data.name_tables().items():
                    name_tables[table_id] = [row.text for row in table.rows]

            # Backstory prompts
            backstory_prompts = []
            if flow.get("has_backstory_oracle"):
                bs = pkg.data.backstory_prompts()
                if bs:
                    backstory_prompts = [row.text for row in bs.rows]

            # Starting assets (non-path)
            starting_assets = []
            asset_cats = flow.get("starting_asset_categories", [])
            for cat in asset_cats:
                for asset in pkg.data.assets(cat):
                    asset_id = asset.get("_id", "").rsplit("/", 1)[-1]
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
                    "creation_flow": flow,
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
            "vow_ranks": ["troublesome", "dangerous", "formidable", "extreme", "epic"],
        },
    }


def highlight_dialog(text: str) -> str:
    """Wrap quoted dialog in <span class="dialog"> for CSS styling."""

    def _wrap(open_q: str, content: str, close_q: str) -> str:
        inner = content.strip()
        if not inner:
            return open_q + content + close_q
        return f'{open_q}<span class="dialog">{inner}</span>{close_q}'

    # DE: „..."
    text = re.sub(
        r'(\u201e)([^\u201e\u201c\u201d"\n]{1,600}?)([\u201c\u201d"])',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)),
        text,
    )
    # EN curly: "..."
    text = re.sub(
        r"(\u201c)([^\u201c\u201d\n]{1,600}?)(\u201d)", lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text
    )
    # Guillemets
    text = re.sub(
        r"(\u00bb)([^\u00ab\u00bb\n]{1,600}?)(\u00ab)" r"|(\u00ab)([^\u00ab\u00bb\n]{1,600}?)(\u00bb)",
        lambda m: (
            _wrap(m.group(1), m.group(2), m.group(3)) if m.group(1) else _wrap(m.group(4), m.group(5), m.group(6))
        ),
        text,
    )
    # Straight ASCII
    text = re.sub(r'(?<!<span class="dialog">)"([^"\n]{1,600}?)"', lambda m: _wrap('"', m.group(1), '"'), text)
    # EN single curly
    text = re.sub(
        r"(\u2018)([^\u2018\u2019\n]{1,600}?)(\u2019)", lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text
    )
    # French single guillemets
    text = re.sub(
        r"(\u2039)([^\u2039\u203a\n]{1,600}?)(\u203a)", lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text
    )
    return text


def build_ui_strings() -> dict[str, str]:
    """All strings.yaml entries for the client. Sent once at connect."""
    from ..strings_loader import all_strings

    return all_strings()
