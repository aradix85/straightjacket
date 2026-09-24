# Elvira report: starforged, explorer, 8 turns

Verdict: 1 problem(s) found.

## Problems

- Turn 5: narration audit scored 4/10: The catch fails and worsens, but the scraping stopping gives the MISS a silver lining.

## Coverage

Exercised: result:MISS (3), result:WEAK_HIT (2), dialog (2), clock_fired (1), director (7), correction (1), save_roundtrip (2), stream_complete (7), pay_the_price (3).

Not exercised: result:STRONG_HIT, match, combat, npc_introduced, npc_died, location_change, burn_offered, burn_taken, chapter_transition, game_over, succession, bonus_used, chained_move.

## Narration audit

7 turns audited. Overall 7.4 out of 10.
- result_integrity: 4.3 out of 5
- prompt_elements: 4.1 out of 5
- npc_voice: 4.3 out of 5
- player_agency: 4.1 out of 5
- restraint: 3.4 out of 5
- prose: 4.3 out of 5

## Streaming

7 turns streamed; first sentence after 2.9 seconds (median).
7 complete, 7 identical to the final text.

## Engine events

New NPCs extracted from narration: 0.
Bonuses: 0.
Chained moves: 0.
Pay the Price: 3.
- You are stressed
- You face a tough choice
- You are separated from something or someone
Director tool rounds: 39.

## Speed

Turn time: median 8.7 seconds, longest 10.3.

## Cost

- brain (gpt-6-luna): 8 calls, 14510 in, 935 out, about $0.002
- correction (gpt-6-luna): 1 calls, 916 in, 91 out, about $0.000
- director (gpt-6-luna): 23 calls, 37457 in, 5072 out, about $0.006
- narrator (gpt-6-luna): 8 calls, 32122 in, 1569 out, about $0.004
- narrator_metadata (gpt-6-luna): 8 calls, 6366 in, 320 out, about $0.001
- revelation_check (gpt-6-luna): 7 calls, 3457 in, 388 out, about $0.001
- Total: about $0.01. Input is counted at full price, so prompt caching makes the real cost lower.
