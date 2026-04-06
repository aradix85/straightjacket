#!/usr/bin/env python3
"""Help panel: game rules reference from the player's perspective."""

from nicegui import ui

from ..engine import E
from ..i18n import t


def render_help() -> None:
    with ui.expansion(f"{E['question']} {t('help.title')}").classes("w-full"):
        ui.markdown(t("help.intro_title"))
        ui.label(t("help.intro_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(t("help.freedom_title"))
        ui.label(t("help.freedom_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(t("help.probe_title"))
        ui.label(t("help.probe_text")).classes("text-xs text-gray-400")
        ui.html(t("help.probe_detail")).style(
            "font-size:0.85em; line-height:1.8; padding:0.3em 0")
        ui.separator()

        ui.markdown(t("help.results_title"))
        ui.label(t("help.results_text")).classes("text-xs text-gray-400")
        with ui.element('div').style("font-size:0.85em; line-height:1.6; padding:0.2em 0"):
            for _ico, _lbl_key, _desc_key in [
                (E['check'],  "help.result_strong", "help.result_strong_desc"),
                (E['warn'],   "help.result_weak",   "help.result_weak_desc"),
                (E['x_mark'], "help.result_miss",   "help.result_miss_desc"),
            ]:
                ui.html(f"{_ico} {t(_lbl_key)}")
                ui.label(t(_desc_key)).classes(
                    "text-xs text-gray-400").style("margin-bottom:0.4em")
        ui.separator()

        ui.markdown(f"{t('help.match_title')} {E['comet']}")
        ui.label(t("help.match_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(t("help.position_title"))
        ui.label(t("help.position_text")).classes("text-xs text-gray-400")
        with ui.element('div').style("font-size:0.85em; line-height:1.6; padding:0.2em 0"):
            for _ico, _lbl_key, _desc_key in [
                (E['green_circle'],  "help.pos_controlled", "help.pos_controlled_desc"),
                (E['orange_circle'], "help.pos_risky",      "help.pos_risky_desc"),
                (E['red_circle'],    "help.pos_desperate",  "help.pos_desperate_desc"),
            ]:
                ui.html(f"{_ico} {t(_lbl_key)}")
                ui.label(t(_desc_key)).classes(
                    "text-xs text-gray-400").style("margin-bottom:0.4em")
        ui.separator()

        ui.markdown(t("help.stats_title"))
        ui.label(t("help.stats_text")).classes("text-xs text-gray-400")
        ui.html(
            f"{E['lightning']} {t('help.stat_edge')}<br>"
            f"{E['heart_red']} {t('help.stat_heart')}<br>"
            f"{E['shield']} {t('help.stat_iron')}<br>"
            f"{E['dark_moon']} {t('help.stat_shadow')}<br>"
            f"{E['brain']} {t('help.stat_wits')}"
        ).style("font-size:0.85em; line-height:2")
        ui.separator()

        ui.markdown(t("help.tracks_title"))
        ui.label(t("help.tracks_text")).classes("text-xs text-gray-400")
        ui.html(
            f"{E['heart_red']} {t('help.track_health')}<br>"
            f"{E['heart_blue']} {t('help.track_spirit')}<br>"
            f"{E['yellow_dot']} {t('help.track_supply')}"
        ).style("font-size:0.85em; line-height:2")
        ui.separator()

        ui.markdown(t("help.momentum_title"))
        ui.label(t("help.momentum_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(f"{t('help.chaos_title')} {E['tornado']}")
        ui.label(t("help.chaos_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(f"{t('help.clocks_title')} {E['clock']}")
        ui.label(t("help.clocks_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(f"{t('help.crisis_title')} {E['skull']}")
        ui.label(t("help.crisis_text")).classes("text-xs text-gray-400")
        ui.separator()

        ui.markdown(f"{t('help.correction_title')} {E['pen']}")
        ui.label(t("help.correction_text")).classes("text-xs text-gray-400")
        ui.label(t("help.correction_example")).classes("text-xs text-gray-400")
