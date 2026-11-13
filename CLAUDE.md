# Straightjacket — Sessions

What every session of the maintainer works from: Claude Code hands it this file at its start. The order of work is in roadmap.md, the rules every change keeps and the checks before a commit in CONTRIBUTING.md, and the audit method in AUDIT.md.

Claude Code hands this file to a sub-agent too. A sub-agent is no session: it works by AGENTS.md, and edits, stages, and commits nothing.

## Always

Every substep and every session ends with both of these before its commit:

- **Read the whole diff back** against CONTRIBUTING.md (Workflow, step 4) and fix what it finds; a green suite does not replace it.
- **Move what is finished to DONE.** A finished step, substep, or session leaves its list in roadmap.md and goes under DONE at the bottom there, cut to its essence, only what a later session may still need, into its step's line while the step stays open. This is the user's standing way of working, so that what belongs together stands together: the open work above, the finished work below. Every session also reads DONE for what can be shorter and cuts it.

## Sessions with the user

**The user.** The user writes in Dutch and reads with a screen reader: answers are in Dutch and in plain prose; the repository stays in English.

**One session, one or two releases.** A session starts in a fresh conversation and does one or two releases. A long conversation fills the model's context with every file, diff, and test run it reads, and the app then summarizes its beginning, which loses detail. What the next session needs is in the roadmap, the CHANGELOG, and `docs/`.

**Where the work happens.**

- The work happens in Claude Code on the user's laptop (Windows 11), in the project's folder `C:\Users\radix\Documents\straightjacket`, the clone of `aradix85/straightjacket` on GitHub. Beside Claude Code's own tools the session has the radix-mcp tools and the git and GitHub command lines, which are signed in to the user's GitHub account.
- The user's opening grants commits and pushes; what follows here holds from then on. The session works and runs the quality gate in that folder, commits each finished release to main, and pushes it.
- The gate's tools are in `.venv`, which `uv sync` fills (CONTRIBUTING.md, Testing), not in the `venv` that `run.py` makes to play the game.
- The user does not edit the folder, so a change a session finds there at its start, or a main that is not level with origin's, was left by an earlier session: find out what it is before anything else, and never reset or force.
- The API keys live in the laptop's Windows user environment (`ANTHROPIC_API_KEY` for the game and Elvira); a process started by a tool may need them set in its own environment.

**What a session reads.** Claude Code hands it this file and, through the import at its end, AGENTS.md. It reads these itself: roadmap.md, CONTRIBUTING.md, ARCHITECTURE.md, and the CHANGELOG, which holds the releases of the step in progress. It also reads the md files of the area NEXT STEP touches:

- the ruleset's rules (moves, tracks, meters, impacts, legacy, assets, threats): `docs/ruleset.md`;
- the game master (scenes, chaos, random events, fate, facts, generators, NPCs, clocks): `docs/gamemaster.md`;
- the story (blueprint, revelations, chapters, succession): `docs/story.md`;
- any rule of those three: `docs/divergences.md` beside it;
- the AI calls, prompts, and configuration: `docs/ai.md`;
- an Elvira run: `docs/elvira.md`;
- settings, rulesets, and character creation: `docs/settings.md`;
- an audit: AUDIT.md;
- the server and the player's input: SECURITY.md.

README.md and ORIGINS.md are background. For anything else a sub-agent reports what bears on the step. Then the session continues with NEXT STEP.

**The design document** is not in the repository; README.md links it, and the user's repository `aradix85/narrative-rpg-engine` holds it as a pdf (version 2.4), which `pdftotext` reads. It is theory, and the engine is its practice, which may depart from it (the user's words).

**Sources before prompts.** The user wants as much as possible to come from the source material: where a rulebook table can settle what the narrator still invents, that is the fix to reach for, ahead of new prompt wording, which on Sonnet stayed within the noise (9f).

**Elvira runs.**

- An Elvira run a release needs plays straight after the push to main, with no branch in between (CONTRIBUTING.md, Workflow step 5).
- Elvira runs on the real models again since 9i, the user's choice now that the work builds rather than tidies, but only when a run makes a real difference to the work, and never more runs or turns than that needs: tokens and credit are not to be wasted. A measurement of the engine as it was, when the decision does not hang on it, is no such run. The runs that releases without them left open are not caught up.
- The Elvira sessions a step needs are part of the work. Say what a measuring round will cost before starting it, estimated from the last run's report; the API spend limit is set in the Claude Console (Settings, Billing). The user keeps runs to what a change needs, no extra ones.

**Sub-agents.** A session that hands work to a sub-agent does it by AGENTS.md, which says what a session hands off and keeps, what a task carries, and how a release is checked (the user's choice). The line below imports that file, so that Claude Code hands it over with this one.

@AGENTS.md
