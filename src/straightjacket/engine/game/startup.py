from straightjacket.engine.ai.api_client import check_configured_models
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.ruleset.config import rules


def check_startup() -> None:
    for load_store in (eng, gm, crafter, rules):
        load_store()
    check_configured_models()
