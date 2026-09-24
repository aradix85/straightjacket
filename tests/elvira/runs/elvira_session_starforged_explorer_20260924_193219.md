# Elvira report: starforged, explorer, 20 turns

Verdict: 1 problem(s) found.

## Problems

- Turn 6: narration audit scored 4/10: The narration lets the hatch close successfully despite the MISS.

## Coverage

Exercised: result:MISS (2), result:WEAK_HIT (9), result:STRONG_HIT (4), dialog (3), location_change (1), director (13), burn_offered (2), burn_taken (2), correction (2), save_roundtrip (5), stream_complete (18).

Not exercised: match, combat, npc_introduced, npc_died, clock_fired, chapter_transition, game_over, succession.

## Narration audit

18 turns audited. Overall 7.7 out of 10.
- result_integrity: 4.6 out of 5
- prompt_elements: 4.7 out of 5
- npc_voice: 4.7 out of 5
- player_agency: 3.8 out of 5
- restraint: 4.1 out of 5
- prose: 4.1 out of 5

## Streaming

18 turns streamed; first sentence after 3.1 seconds (median).
18 complete, 18 identical to the final text.

## Speed

Turn time: median 7.3 seconds, longest 8.4.

## Cost

- brain (gpt-6-luna): 20 calls, 34090 in, 2258 out, about $0.005
- correction (gpt-6-luna): 2 calls, 1759 in, 214 out, about $0.000
- narrator (gpt-6-luna): 21 calls, 77340 in, 3141 out, about $0.009
- narrator_metadata (gpt-6-luna): 21 calls, 14519 in, 777 out, about $0.002
- revelation_check (gpt-6-luna): 18 calls, 8046 in, 918 out, about $0.001
- Total: about $0.02. Input is counted at full price, so prompt caching makes the real cost lower.
