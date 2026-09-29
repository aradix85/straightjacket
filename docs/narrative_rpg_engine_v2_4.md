# Narrative RPG Engine

*A Design Document, version 2.4. Converted from the published PDF on 2026-09-29; the text is unchanged.*

AI storytelling is broken. Everyone tries to make AI smarter at telling stories. It doesn't work. AI can't plan ahead. It can't remember what happened three scenes ago. It will always try to give you a happy ending, because that's what language models do — they optimize for plausible and pleasant, not for meaningful.

This isn't a new observation. Several projects have tried to use AI as a gamemaster for solo RPGs. They failed — not because the AI wasn't good enough, but because they asked it to do everything: decide outcomes, track memory, manage pacing, and generate narrative all at once. That's not what language models are built for.

This document proposes a different approach. Instead of asking AI to be a better storyteller, strip it down to the one thing it's actually good at: writing prose. Everything else — memory, consequences, NPC behavior, timing, pacing — lives outside the AI in structured systems that don't forget and don't flinch.

The result is a solo narrative RPG engine where the player experiences only story and choices. All mechanics run invisibly in the background. The AI narrates. It does not decide.

To be precise about what that means: the AI does not generate the story. It does not choose what happens next. It does not determine whether you succeed or fail. It does not decide how an NPC feels about you. All of those decisions are made by structured systems — dice rolls, clocks, trackers, databases. The AI receives the results of those decisions and wraps them in narrative prose. It is a narrator in the literal sense: it tells you what happened, after something else has already decided what happened.

## The Core Problem

Current AI storytelling fails on four fundamental points.

No memory across sessions. Every conversation starts blank. The NPC you befriended last week doesn't know you exist today.

Pleasing behavior. AI resolves everything in the player's favor. It doesn't want to disappoint you. Failure gets softened into learning experiences and silver linings.

No slow burn. There's no tension that builds over time, no subplot that simmers for ten sessions before it explodes. AI lives in the eternal present.

No forward planning. No foreshadowing, no setups that pay off later, no narrative arcs. AI generates the next plausible beat, not the next good one.

These aren't bugs that better models will fix. They're structural. Language models predict the next token. They don't hold a story in their head. The solution isn't smarter AI — it's less AI, with more structure around it.

## What Makes a Story Satisfying

Before talking about systems, it's worth being explicit about what this engine is trying to produce. A satisfying narrative has characters with something to lose, NPCs who pursue their own goals rather than waiting for the player, consequences that persist and resurface, relationships built on actual history, and a world that does not revolve around the player. The player is part of a system with its own logic, navigating other people's stories while trying to pursue their own.

That last point is what separates this engine from most AI-driven narrative projects. In AI Dungeon and its successors, the player is the center of the universe. Everything exists to serve the player's story. That produces a theme park, not a world. This engine takes the opposite position: the player is a participant in a world that has its own conflicts and momentum. Sometimes those conflicts collide with yours. Sometimes they don't care about you at all.

Games that achieve this feeling include King of Dragon Pass, where clans make their own choices and the world has an agenda that isn't yours; Fallen London, where factions keep moving whether you participate or not; and the best Choice of Games titles, where real worlds with real history produce real consequences. The shared element: the world isn't built to give you a story. You're a player in their story who happens to also have goals.

## The Architecture

Three parties with separated responsibilities.

The player sees only story and choices. Natural language in, narrative out. No stats, no dice, no system references.

The engine (Python or equivalent) handles everything structural. It interprets player input, rolls dice, retrieves relevant context from the database, builds the prompt, processes AI output, and updates the game state. The engine also handles input parsing: it sends the player's natural language input to the AI as part of the narrator prompt, and the AI classifies the action type (social, physical, perception, or no mechanical action needed) and narrates the result in a single call. There is no separate parser. One call, one response.

The AI receives structured data — roll results, NPC states, active threats, relationship history, hard constraints — and writes narrative prose within those boundaries. It does not determine outcomes. It does not decide what NPCs do. It wraps predetermined results in story.

The database holds persistent memory across sessions. Everything that matters is stored and retrieved when relevant. NPCs remember. Factions advance. Grudges persist.

### Engine-AI Communication: Tool Use

The engine exposes its subsystems to the AI as callable tools, using the function-calling capabilities that most modern LLMs support. Each subsystem — action resolution, oracle tables, NPC memory, faction tracker, world state — is a Python module with a defined interface. The AI receives a description of each available tool and can request to call them when it needs information or results. This mirrors how modern AI tool-use works in other domains. The AI might recognize that a player action requires a dice roll and call the action resolution tool. Or it might need to generate a new NPC and call the character generator. The crucial principle remains: the tools determine results, the AI narrates them. The AI can request a roll but cannot change the outcome.

Two constraints are essential. First, rate limiting: a maximum number of tool calls per turn prevents the AI from entering infinite loops. Second, result immutability: tool outputs are final. The AI receives them as facts to narrate, not suggestions to modify. If an API call fails or returns unusable output, the engine must not update any game state — the game pauses, not breaks. The player gets a clean message, and the engine retries or falls back to a simpler prompt.

### AI Provider Integration

The engine communicates with the AI through a provider-agnostic interface. A configuration file defines which provider is used, which model, and with what credentials. The engine translates internally to the correct API format. This makes it possible to switch between providers without modifying the engine itself.

Most providers support the OpenAI-compatible API format, which simplifies implementation. Services like OpenRouter offer a single endpoint to hundreds of models from different providers, further reducing integration complexity. At current pricing, midrange models capable of narrative prose cost fractions of a cent per turn. A casual player can expect to spend a few euros per month at most.

Running models locally is technically possible but not recommended. It requires significant hardware, the quality of locally-run models varies, and maintaining a local setup adds complexity that most players will not want to deal with. The engine should be designed for API-based providers as the primary path.

### Context Window Management

Modern LLMs offer large context windows — 131K tokens and up, with some providers offering 200K. For most RPG sessions, this is more than sufficient. However, large context windows do not mean the engine should load everything into every prompt. More context means higher cost per turn and more noise for the AI to parse, which degrades output quality.

The design recommendation is: choose a provider with a large context window so the engine never hits a hard limit, but load context selectively per turn. The engine should prioritize what it includes: first the core prompt with constraints, then the current scene, then active NPC data, then active threats and quests, then background context if there is room. Session history should be stored in the database and summarized rather than included in full. The database is the memory; the prompt is the attention.

## The Six Functions

Every narrative RPG engine needs to handle six things. This is the functional map — what each function does and what kinds of systems can fill it. The specific systems named here are examples. Other systems that serve the same function would work equally well.

A note on licensing: not all referenced systems are openly licensed. Where a system is proprietary, a builder would need to create equivalent implementations that serve the same function. The concepts themselves — chaos-driven probability, bond tracking, faction reputation — are established design patterns in tabletop RPG design, not proprietary inventions. What is protected is the specific implementation: the particular tables, values, and mechanics of a given product.

### 1. Action Resolution — what happens when you try something

This determines whether an attempt succeeds or fails and to what degree. It needs to be dice-driven, not AI-driven, because AI will always bias toward success.

Example system: Starforged moves. A strong hit / weak hit / miss structure across dozens of moves covering combat, exploration, social interaction, and more. The key feature is that outcomes are graduated — weak hits create complications even on success, which gives the narrative texture. Starforged is released under a Creative Commons license, which means its moves and oracles can be used directly in an implementation.

What matters for the architecture: the engine rolls dice and determines the mechanical outcome before the AI sees anything. The AI receives "you failed, and here's what that means mechanically" and writes the narrative around it.

### 2. Fiction Generation — what exists in the world

This generates concrete details when the story needs them. What does this planet look like? Who is the stranger at the bar? What's behind the sealed door?

Example systems: Starforged oracles provide setting-specific details (planets, NPCs, locations, creatures) through extensive random tables. Mythic GME meaning tables provide abstract interpretation through action/subject pairs for plot-level questions. The distinction matters: one answers "what do you see," the other answers "what does this mean."

Licensing note: Starforged's oracles are Creative Commons and can be used directly. Mythic GME is not openly licensed. However, the concept of abstract meaning tables is an established design pattern. A builder would need to create their own meaning tables rather than copying Mythic's specific content. This is feasible and may produce tables better tailored to the engine's specific needs.

What matters for the architecture: the engine can roll on these tables programmatically and feed the results to the AI as raw material to narrate, rather than asking the AI to invent details from nothing.

### 3. Timing and Pacing — when things happen

This determines when scenes shift, when tension escalates, when a simmering threat boils over. Without it, the story has no rhythm.

Example systems: Mythic GME scene management handles altered scenes and interrupts — moments when events deviate from expectations. Progress tracks accumulate toward endpoints. Clocks fill segment by segment until they trigger consequences.

Licensing note: Mythic GME's chaos factor — a variable that increases the probability of unexpected events as the story becomes more volatile — is a useful concept. The concept of chaos-driven event probability is not unique to Mythic; a builder would need to create their own implementation with custom values and thresholds.

Known gap: faction turn timing. When do NPC and faction plans advance independently of the player? One approach: every N scenes or at specific triggers, the engine advances faction clocks regardless of player action. The world moves without you.

What matters for the architecture: the engine ticks clocks and checks triggers between player actions. This creates the feeling that the world doesn't wait.

### 4. Relationships and Memory — who cares and what they remember

This tracks how NPCs and factions feel about the player and what they remember. Without persistent memory, relationships are meaningless.

Example systems: Faces in the Dark provides NPC memory tags and bond clocks — concrete tracking of what an NPC remembers about you and how your relationship stands. Feats & Favors handles faction-level reputation and tenets (what groups value). DramaSystem concepts from Robin D. Laws' Hillfolk add relational tension through tracking emotional requests, refusals, and concessions between characters.

These operate at three scales that work together: individual (what does this person remember about me), group (how does this faction see me), and dynamic (who asked what of whom, who refused, who gave in).

Licensing note: Faces in the Dark, Feats & Favors, and DramaSystem are not openly licensed. The concepts they implement — bond clocks, faction reputation scores, emotional request/refusal dynamics — are established patterns in RPG design. A builder would need to create equivalent systems. This is feasible and may produce systems better tailored to the engine's specific needs. What matters for the architecture: every interaction updates relationship state. When the AI narrates an NPC, it receives their full relational context — memories, bond status, outstanding debts, grudges. The NPC's behavior is constrained by this data.

### 5. Agency and Motivation — what they want and what they do about it

This determines what NPCs and factions are actively pursuing and what actions they take. Without it, NPCs are reactive props rather than agents in the world.

Example systems: Feats & Favors includes a schemes module where factions have their own projects that progress over time. The AIMS framework (Agenda, Instinct, Moves, Secrets) gives individual NPCs proactive goals and concrete behavioral patterns.

Licensing note: The AIMS framework originates from a Gnome Stew blog post and is an openly shared GM technique. Feats & Favors' schemes module is proprietary, but the concept of faction goal-clocks that progress independently is a common design pattern.

This was the biggest gap in the initial design. Systems for memory and relationships tell you who someone is and how they feel, but not what they want or what they'll do to get it. Adding an agency layer transforms NPCs from reactive to proactive — they pursue goals, they make moves, they collide with the player not because the plot demands it but because their interests conflict. Competing agendas. When an NPC is loyal to a faction but has a conflicting personal goal, the system needs a simple resolution. Each NPC has a loyalty threshold — a value derived from their bond with their faction. When the faction bond is above this threshold, the NPC follows the faction's agenda. When it drops below, the personal goal takes priority. This is not a new system; it is a single comparison using data that already exists in the relationship and agency layers. The threshold can shift based on events: a betrayal by the faction lowers it, a reward raises it. The result is NPCs whose loyalty is not binary but a live variable that the player can influence.

What matters for the architecture: NPC goal-clocks tick alongside faction schemes. When a clock fills, the NPC takes action. This creates emergent conflict — the player didn't cause it, the world's internal logic did.

### 6. World State — where and when the story takes place

This defines the setting and maintains its evolving state throughout play. Without it, the other five functions have no context to operate in.

A world state has two layers. The static layer defines the setting at the start of play: the world and its tone, the factions and their relationships to each other, the locations and their properties, the active threats and tensions, and the vocabulary — the terms and naming conventions that define this world. The vocabulary matters because AI imports its own associations through loaded words. If a setting describes an entity as a "vampire," the AI will import lore from its training data that may not match the intended tone. A well-designed setting controls its language to steer the AI away from unwanted associations.

The generator layer produces new content when the engine needs it. A player enters an unknown town; the generator creates a settlement with inhabitants, economy, and local tensions. A player meets a stranger; the generator creates an NPC with personality, agenda, and connections to existing factions. A player travels through dangerous territory; the encounter generator selects an event weighted to the properties of that area.

The generators use a hybrid approach. They are not pure AI generation and they are not pure table rolls. A generator has templates and tables with structured data. The generator rolls on these tables to produce structured output ("this is a fishing village with a trade dispute"), and the AI writes a concrete description within that structure. The structure decides, the AI narrates.

The generators are context-aware. They use the current world state to ensure consistency: a generator does not create a prosperous trading post in a region that is at war unless the setting specifically allows for that. As the game progresses and the world state changes, the generators reflect those changes.

The engine is setting-agnostic. The world state is not hardcoded; it is loaded as a data package. Starforged's Forge is one possible setting, but the engine supports any setting that provides the required components: factions, locations, threats, oracles, vocabulary, and generator data. A fantasy setting has oracles for villages, taverns, and forest threats. A sci-fi setting has oracles for planets, space stations, and alien factions. The mechanism is the same; the content differs. Starforged's oracles are released under a Creative Commons license and can serve as a reference implementation or be used directly for a sci-fi setting.

What matters for the architecture: the world state is both a data store and a set of generators. It is the context that all other functions query. Building a setting — including its generator data — is significant work. Each setting needs its own tables, templates, naming conventions, and vocabulary. This is an investment, but it is also what makes each setting feel distinct rather than generic.

## How AI Fits In

The AI's role is constrained and specific. It receives structured data and writes prose within hard boundaries.

The prompt is not one large system prompt. It's modular, assembled per turn based on what's relevant. A small core prompt defines the AI's role (narrator, not decider) and hard constraints. Dynamic context is loaded per turn: only the NPCs present in the scene, only the active threads that touch this moment, only the relevant relationship data.

### Constraints: The Engine Decides, the AI Tells

There are two strategies for constraining AI output. Option A: prompt-constraints, where hard rules in the prompt let the AI choose how things go wrong within boundaries. Option B: engine-dictated consequences, where the engine specifies exactly what goes wrong and the AI only narrates the predetermined outcome.

The default should be option B. This is consistent with the engine's core philosophy: structure decides, AI narrates. When the engine specifies "you fail AND you lose Kira's trust AND she leaves without saying goodbye," the AI has a richer and more specific scene to write than when it's told "something goes wrong, you choose." Specificity does not reduce creative space — it redirects it. The AI stops spending its capacity on choosing what happens and devotes it entirely to how it's told. Tighter constraints produce better prose, for the same reason that sonnets are more powerful than free verse: limitation forces craft.

Option A can serve as an exception for low-stakes moments where the specific consequence genuinely doesn't matter — minor environmental setbacks, flavor complications, moments where creative surprise adds value without risking narrative coherence.

Here's what a constraint looks like in practice. On a failed roll:

```
ROLL: miss
CONSEQUENCE: You lose 1 supply. The rope snaps. You fall to the ledge below,
unhurt but stranded. Your pack lands in the river.
CONSTRAINT: Narrate this as it happens. The situation is concretely worse.
No silver lining.
```

For NPC interactions:

```
NPC: Kira Vance
AGENDA: Wants access to the vault, will use others to get it
INSTINCT: Charming but always calculating
MEMORY: Player promised to help but didn't, two sessions ago
BOND: 2/4, distrustful
CONSTRAINT: Kira remembers the broken promise. This colors all her
interactions until the player makes it right.
```

The AI doesn't decide that Kira is distrustful. The system tells it she is, based on tracked data, and the AI writes dialogue and behavior that reflects that state.

### Constraint Writing Principles

The engine determines what happens. The prompt tells the AI how to narrate it. But how that prompt is written matters as much as what it contains. Language models do not evaluate rules — they follow the path of least resistance through patterns learned during training. Effective constraints work with this tendency, not against it.

Give direction, not exclusions. Telling the AI what not to do activates the concept you want to avoid. "Don't soften the failure" activates softening. "Narrate the concrete loss" gives the AI somewhere to go. Constraints should describe what the scene is, not what it isn't. The examples in this document already follow this principle: "Write the absence, not the event" is direction. "Don't describe the event" would undermine itself.

Provide patterns, not rules. The AI copies patterns more reliably than it follows conditional logic. An example of how a scene should read is more effective than a rule about how scenes should be written. When the engine needs a specific narrative register — terse, atmospheric, confrontational — a brief demonstration in the prompt anchors the AI's output more reliably than an abstract instruction.

Reinforce every turn. Any instruction not present in the current prompt loses influence. The AI does not remember previous prompts. It does not carry forward lessons from earlier turns. Every turn is a fresh context, and the AI will drift toward its trained defaults — helpful, pleasant, generic — unless actively steered otherwise. The engine must include constraints, vocabulary, and narrative direction in every prompt, not as a one-time setup. This is not a limitation to work around; it is a fundamental property of how these models operate. Drift is the default. Sustained direction is the engineering challenge.

### Narrative Direction: How It's Told

Mechanical constraints tell the AI what happened. Narrative direction tells the AI how to write it. This is the difference between a scene that functions correctly and a scene that makes a player feel something.

No existing tabletop system covers this. In traditional play, the GM reads the table and adjusts tone intuitively. In an automated engine, that intuition must be made explicit. But it does not require a new module or database. The data needed to derive narrative direction already exists in the game state. What's needed is a mapping from game state to writing instructions, built into the prompt builder. The engine derives narrative parameters from existing data: intensity (from threat levels, clock states, stakes), tempo (from scene type — combat is fast, aftermath is slow), perspective (loss and discovery call for sensory detail; conflict calls for sharp dialogue; quiet moments call for atmosphere), player relation (did the player cause this, is it happening to them, or are they witnessing something external), and narrative position (building toward something, climax, or aftermath).

These parameters translate into brief writing instructions appended to the prompt. When a bond clock drops to zero because of the player's actions:

```
NARRATIVE DIRECTION: High intensity. Slow tempo. Sensory perspective.
Player caused this. This is aftermath. Write the absence, not the event.
```

This is the engine telling the AI what register to write in, derived from data that already exists. A lookup, not a module. The structure directs, the AI performs.

### Vocabulary Control

AI imports associations through loaded words. The word "vampire" activates a constellation of tropes from the AI's training data — Twilight, Dracula, Buffy, Interview with the Vampire — and the AI will default to one of those framings even if the setting intends something different. The word "knight" brings Arthurian romanticism. The word "spaceship" brings Star Wars or Star Trek. The solution is vocabulary control at the setting level. A setting defines not just what exists in the world but how it is described. Instead of "vampire," the setting describes "an entity that draws life force from proximity, leaving its victims weakened and translucent." Instead of "knight," the setting describes "an armored enforcer sworn to a patron house, operating under a code that prioritizes the house's interests over justice."

This vocabulary becomes part of the world state and is included in the AI's prompt context. The more specific the vocabulary, the more the AI writes in the setting's voice rather than defaulting to generic genre conventions.

## Text In, Text Out

The engine is text-in, text-out by design. The player types natural language. The engine returns narrative prose. No maps, no visual character sheets, no sourcebook flipping.

This isn't an accessibility add-on. It's what the architecture looks like when you strip away everything that doesn't serve the core experience. But it has a significant side effect: it's inherently accessible, including for screen reader users. There are very few narrative games with this level of systemic depth that work well with assistive technology. This one does, by design rather than by afterthought.

## Open Questions

This design is untested. These are the problems that need solving through building and iteration, not through more theorizing.

Constraint verification. How does the engine verify that AI output actually follows constraints? The default toward engine-dictated consequences (option B) reduces this problem significantly — when the engine specifies exactly what happens, there is less to verify. For the remaining cases: a second, cheaper AI call that evaluates output against constraints; predefined severity markers that the engine checks programmatically; or leaning harder on option B wherever possible. The more the engine specifies, the less there is to verify.

Context management. The engine should load context selectively per turn, prioritizing the current scene and active elements over background information. Large context windows from modern providers (131K–200K tokens) mean the engine is unlikely to hit hard limits, but selective loading remains important for output quality and cost efficiency.

Pacing. When should NPC goal-clocks tick? Every scene? Every N scenes? Only on specific triggers? The pacing of the world's independent movement is a tuning problem that probably requires playtesting.

Generator data. Each setting requires its own tables, templates, naming conventions, and vocabulary for the generators to produce context-appropriate content. This is significant authoring work per setting. A minimum viable setting needs at least: location types with properties, NPC templates with personality and agenda ranges, encounter tables weighted by location properties, and a vocabulary list that controls the AI's associations. Tooling that helps setting authors create this data efficiently would lower the barrier to entry.

Licensing and intellectual property. Not all systems referenced in this document are openly licensed. Starforged and the AIMS framework can be used directly. Mythic GME, Faces in the Dark, Feats & Favors, and DramaSystem are proprietary products. A builder must create equivalent implementations for these functions rather than copying their specific content. The underlying concepts are established design patterns that can be independently implemented. This is feasible and may produce systems better tailored to the engine's specific needs.

Distribution and AI access. The engine requires access to a large language model. The practical path is API-based access through providers like OpenRouter, which offer a single endpoint to hundreds of models at low cost. The engine should use a configuration file where the user specifies their provider, model, and API key. Supporting the OpenAI-compatible API format covers most providers. The engine should not be locked to any single provider.

Vocabulary drift. Even with a controlled vocabulary in the setting, AI will gradually drift toward its default associations over extended sessions. This is not a bug but a fundamental property of how language models work: trained defaults reassert when positioning weakens. The engine counters this by including vocabulary in every prompt, not as a one-time setup. The remaining tuning question is how much vocabulary context to include per turn before it competes with scene data for attention. This is best solved by iteration during playtesting.

Narrative direction tuning. The mapping from game state to writing instructions is a small system, but its parameters need calibration through play. Which game states matter most for narrative quality? How specific should writing instructions be before they constrain the AI's prose rather than enhance it? This is a tuning problem best solved by iteration.

## Starting Points

If you want to build on this, here are possible entry points depending on what interests you. The minimum viable version starts with one NPC who remembers and wants. Build a single NPC with memory, an agenda, and a bond clock. Connect it to a database that persists between sessions. Add one action resolution system. Add an AI that narrates within constraints. Get one conversation where the NPC remembers what you said last session, behaves according to their goals, and reacts differently based on your relationship. If that works, everything else is scaling. A setting package. If you're interested in world-building rather than code, design a complete setting with its static layer (factions, locations, threats, vocabulary) and generator data (tables, templates, encounter weights). A well-built setting package demonstrates the engine's potential even before the engine itself is fully built. This is the most accessible entry point for non-programmers who understand narrative and world design.

The AI constraint problem. If you're interested in how to make AI narrate failure honestly, the tension between prompt-constraints and engine-dictated consequences is where the interesting work is. Build a simple loop where the AI narrates outcomes of varying severity and test how reliably it follows hard constraints. Test how engine-dictated consequences compare to prompt-constraints in output quality.

The systems integration. If you're interested in how tabletop systems combine, the NPC data structure is the nexus. How do you merge memory, relationship tracking, personal agendas, and faction affiliation into one coherent object that the engine can query and the AI can use? Accessibility. A text-only RPG engine with hidden complexity is a genuinely underserved space. Most narrative games with mechanical depth assume visual interfaces. A well-built engine like this could serve a community that has very few options.

## What This Is and Isn't

This is a design document. There is no code. It's a blueprint and an argument for how AI-assisted narrative RPGs could work — not by replacing structure with AI, but by using structure to make AI useful.

The specific systems referenced throughout are examples of what works in each functional role. They're drawn from the solo RPG and tabletop communities and chosen because they solve specific problems well. They are not requirements. Any system that serves the same function could substitute.

This document was developed collaboratively with AI as a thinking and writing partner. This document is the product of extensive design work, collaborative thinking, and community feedback. Build on it, challenge it, take what's useful. That's what it's here for.

If you want to discuss, collaborate, or point out where this breaks, the author can be reached through the project page at blindgamer85.itch.io.

## Version History

Version 1.0 — Initial release. Five functions, core architecture, open questions.

Version 2.0 — Added sixth function (World State) covering settings, generators, and vocabulary control. Expanded architecture section with tool-use communication, AI provider integration, and context window management. Added licensing information per referenced system. Expanded open questions with generator data requirements, distribution, vocabulary drift, and intellectual property considerations. Clarified the distinction between AI-as-narrator and AI-as-storyteller. Incorporated community feedback from r/Solo_Roleplaying, r/RPGdesign, and r/Ironsworn.

Version 2.1 — Reordered starting points to foreground setting design as an accessible entry point. Strengthened constraint verification with cross-reference to the constraint spectrum. Added contact information.

Version 2.2 — Restructured constraint spectrum: engine-dictated consequences (option B) as default, prompt-constraints (option A) as exception for low-stakes moments. Added narrative direction system: writing instructions derived from existing game state data via prompt builder. Simplified input parsing: LLMs handle natural language classification well; parser and narrator as separate AI roles. Integrated graceful degradation into tool-use section. Strengthened "what makes a story satisfying" with explicit position that the player is not the center of the world. Removed specific model recommendations to future-proof the document. Added narrative direction tuning to open questions. Reordered starting points to lead with the NPC as the core building block.

Version 2.3 — Removed separate parser role: input parsing integrated into the single narrator call, eliminating unnecessary complexity. Resolved competing agendas: NPC loyalty thresholds using existing relationship data rather than a new system. Downgraded vocabulary drift from architectural concern to playtesting tuning problem.

Version 2.4 — Added constraint writing principles: direction over exclusion, patterns over rules, per-turn reinforcement as non-negotiable. Reframed vocabulary drift as a fundamental model property requiring continuous counter-pressure rather than a one-time solution. Incorporates prompt engineering principles from cepunkt's mlpoking framework (github.com/cepunkt/mlpoking, CC0 licensed).
