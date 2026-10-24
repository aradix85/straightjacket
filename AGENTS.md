# Agents

How a session of the maintainer hands work to sub-agents, and what every sub-agent works from. A session that starts a sub-agent gives it this file: its task tells it to read AGENTS.md first and act by it (the user's choice). The rules the work itself keeps are not repeated here; this file names where each one stands.

## What a session hands off

Sub-agents do the work whose conclusion is all the session needs, so that only their findings enter the session's context (the user's choice):

- reading the md files outside the session's own list (roadmap.md, Sessions with the user) for what bears on NEXT STEP;
- a broad search of the codebase;
- checking documents against the code;
- an audit's hit-lists (Audits below);
- reading a rule in a book or a Datasworn file (Reading a source below);
- checking a finished release with eyes that did not write it (Checking a release below).

**What the session keeps.** It reads the code it will change itself and hands no map of it to a sub-agent first, since it must read that code anyway and the map only doubles the work (the user's choice). It keeps the decisions, its own edits, the quality gate, and the commit, so two writers never touch one file. Agents that only read run side by side.

**Models.** A sub-agent that only searches or reads runs on a lighter model (Sonnet, or Haiku for a plain search), since it gathers rather than judges; a check of a release keeps the session's model (the user's choice).

## What a task carries

A sub-agent sees no conversation, so its task carries all it needs:

1. **What to read.** AGENTS.md first, to act by it; then CONTRIBUTING.md, the ground every change stands on; then what its kind of work names below.
2. **The intent.** What the change or the work intends, and the user's choices it needs.
3. **Where to look.** The files the change touched, or where to look, so it does not search for them. For a check, the diff of those files itself, since a sub-agent starts without the session's context and gathering it is most of its time.
4. **Its questions.** For a check, the seams where the writer knows the change can go wrong, each as a question. Always one open question too, what else it finds wrong, since the writer's list shares the writer's blind spots.
5. **Its budget**, scaled to its questions: about ten to twenty tool calls for one aimed question, after which it reports what it has and names what it left open.
   - Calls that do not depend on each other, such as reading several files, it makes at once in one round, not one after the other.
   - It tries a case in a script of its own only where reading cannot settle it.
   - A change with many paths to walk gets more checkers side by side, one per area where it can go wrong, rather than one checker with a long list.
6. **What it reports:** findings only, each with file and line and a sentence on why, the most important first, under a stated length, and what it cannot settle marked as such. It edits, stages, and commits nothing in the repository: the session, which holds the whole picture, makes every change (the user's choice).
7. **Its progress file**, outside the repository in the session's scratchpad, named in the task. It appends each finding there as soon as it has it, and one line when it finishes a question; its report still comes at the end. A sub-agent cannot message the session while it runs, and the session hears of it only when it ends, so the session follows each file with a monitor and sees how far every sub-agent is (the user's choice).

## Checking a release

**Which releases.** A release that changes the game, its code in `src/` or the yaml and prompt stores the engine reads, is checked before its commit by sub-agents that did not write it. A release that changes only documents, tests, or Elvira is not: the session reads its whole diff back itself (CONTRIBUTING.md, Workflow step 4), since there a check adds less than it costs (the user's choice).

**What a checker reads.** The diff, untracked files included, against each of these where it stands, and the files themselves where it needs them:

1. CONTRIBUTING.md: the reading of Workflow step 4, Rules for a change, Project rules, and Code standards.
2. ARCHITECTURE.md: the order of preference (a source first, then an engine rule, the AI last), the four layers with what each owns, and the import layers.
3. AUDIT.md: the six principles, applied to the changed code only, by the questions of their passes.
4. roadmap.md: the Decisions the change touches, and the definition of done of NEXT STEP.
5. `docs/divergences.md`: a departure from a source that the change adds or settles has its entry, and an entry the change makes wrong is fixed.
6. The md files of the repository root and `docs/`: every statement the change makes wrong.
7. The tests: every new behaviour and every fix has a test that fails without it, through the real path where the behaviour plays in a turn (CONTRIBUTING.md, Testing).

**Timing.** The check of the code starts as soon as the code and its tests are done and the quality gate is green, while the session writes the documents; the check of the documents follows them, so the check adds little to the release's time.

**Splitting.** A release that touches several areas, such as the rules, the page, and the documents, splits the check among checkers that run side by side, one per area, each with the list above and a task sharpened to its files and to the cases its area can go wrong in; a small release has one checker.

A checker does not run the quality gate, which the session has run. The session reads each finding against the code before it acts on it.

## Audits

An audit (AUDIT.md) hands the reading of its hit-lists to sub-agents, one per submodule or per batch of hits, each working from AUDIT.md besides CONTRIBUTING.md and returning its hits classified with file and line. The session merges their lists, checks a sample of each against the code, and makes the fixes itself.

## Reading a source

A sub-agent that reads a rule in a book, a Datasworn file, or the design document quotes the text that settles it, exactly and in full where it is short, with its Datasworn path or its page, and says where the reading needs a book the repository does not hold. The Datasworn files are in `data/`; the design document is a pdf in the user's repository `aradix85/narrative-rpg-engine`, which `pdftotext` reads (roadmap.md, Sessions with the user).
