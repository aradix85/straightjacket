# Settings and character creation

A setting is a data package: a Datasworn JSON file with the game content (moves, oracles, assets) and a settings yaml with what the engine needs to use it (vocabulary, oracle paths, creation flow). The shipped settings are classic Ironsworn (`classic`), Starforged (`starforged`), and Sundered Isles (`sundered_isles`), plus Delve (`delve`), which only extends classic. `setting/packages.py` loads the packages.

## Character creation

Creation is driven by the setting's Datasworn data, with no AI call: the client receives the options from `web/serializers.py` → `build_creation_options`, the setting's `creation_flow` decides which steps it shows, `ruleset/character.py` → `make_character` checks and builds what the ruleset decides of the character: its stats with the array of `ruleset/stats.yaml` (`docs/mechanics.md`, Stats), its paths, from which its concept is named, its starting assets from the setting's `starting_asset_categories`, and its background vow, and `game/game_start.py` → `validate_creation` checks the rest (the name, the truths, the tone). A new game and a successor take up their character through the same `take_up_character`. The chosen truths are stored on the game state and reach every narrator prompt as a `<world_truths>` block (`prompt_blocks.py` → `truths_block`), which the narrator treats as canon. How creation seeds the first threads and tracks is in `docs/mechanics.md`.

## Adding a new setting

1. Place the Datasworn JSON at `data/<datasworn_id>.json`, where `<datasworn_id>` is the value the yaml declares. The format is documented at [github.com/rsek/datasworn](https://github.com/rsek/datasworn).
2. Create `data/settings/<id>.yaml`, with `data/settings/starforged.yaml` as template. The file's stem is the setting id the engine uses; `datasworn_id` inside it points at the JSON.
3. The setting appears in character creation automatically; no Python changes.

Discovery is yaml-only: `list_packages()` scans `data/settings/*.yaml`, and `get_moves()` merges the moves along the package's `parent:` chain, the parent's first, so a child's move replaces its parent's.

## Settings yaml format

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `playable`, `description`, `oracle_paths`, `generators`, `vocabulary`. Optional: `parent`, and `default_tone` and `creation_flow` for a setting whose parent chain supplies them (Inheritance). `default_tone` is one of the tones in `story.kishotenketsu_probability`, the one character creation offers first; the player's choice decides the chapters' story structure and reaches the narrator (`docs/mechanics.md`, Blueprint). A missing required key raises `KeyError`, and so does a key the loader does not know, at the top level or inside `oracle_paths`, `vocabulary`, or `creation_flow`.

```yaml
id: your_setting
title: "Your Setting Name"
datasworn_id: your_setting
playable: true
description: "One paragraph."
parent: classic

vocabulary:
  substitutions: { spaceship: "starship — worn, patched" }
  sensory_palette: "Metal, recycled air, ozone."

oracle_paths:
  action_theme: ["core/action", "core/theme"]
  backstory: "campaign_launch/backstory_prompts"
  threats: "campaign_launch/sector_trouble"

generators:
  npc:
    given_name: "characters/name/given"
    family_name: "characters/name/family_name"
  location:
    theme: "location_themes/type"
    feature: "location_themes/{theme}/feature"

creation_flow:
  has_truths: true
  has_backstory_oracle: true
  has_name_tables: true
  has_ship_creation: false
  starting_asset_categories: [companion, module]
```

`id` must equal the yaml file's stem, which the loader checks, and `datasworn_id` is the basename of the Datasworn JSON. `playable: false` keeps a package out of character creation and out of Elvira's choice, as for Delve. `parent` names the setting it inherits from. `vocabulary` keeps the narrator's word choice in the setting and is the one block of hand-written game content the Yaml content boundary allows (CONTRIBUTING.md). `oracle_paths.threats` drives threat naming (`docs/mechanics.md`). `generators` names, for each category registered in `gamemaster/generation.yaml` apart from `fact`, the oracle table every role of it rolls: `npc` for NPC names (and the name buttons of character creation), `location` and `settlement` for places. A role's path may name an earlier role of the same category in braces, which stands for the table that role's row links to or for its text; a name that no earlier role rolls raises at load (`docs/mechanics.md`, Generators). `creation_flow` controls the client's creation steps.

## Inheritance

With `parent:`, blocks inherit from the parent yaml, resolved at load. `oracle_paths` and `creation_flow` inherit per field: an omitted field takes the parent's value, a present field (even an empty one) overrides it, and a root setting must specify every field. `generators` inherits per category: a category the setting names replaces its parent's. `default_tone` comes from the nearest setting in the chain that names it. `vocabulary` inherits as a whole: when both sub-fields are empty, the block comes from the parent.
