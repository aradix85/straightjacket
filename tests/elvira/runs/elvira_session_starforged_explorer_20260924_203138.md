# Elvira report: starforged, explorer, 20 turns

Verdict: 3 problem(s) found.

## Problems

- Spatial: Turn 20: NPC 'Vey' teleported from 'A cramped dock beside a patched courier starship; the specific location is unknown.' to 'Courier starship interior' without appearing in narration
- Spatial: Turn 20: NPC 'Unidentified figure' teleported from 'A cramped dock beside a patched courier starship; the specific location is unknown.' to 'Courier starship interior' without appearing in narration
- Turn 20: narration audit scored 4/10: The narrowing route and repeated impacts add pressure to a clean strong hit.

## Coverage

Exercised: result:MISS (4), result:WEAK_HIT (4), result:STRONG_HIT (8), match (1), dialog (2), combat (1), location_change (1), director (13), burn_offered (2), burn_taken (2), correction (2), save_roundtrip (5), stream_complete (18), pay_the_price (4).

Not exercised: npc_introduced, npc_died, clock_fired, chapter_transition, game_over, succession, bonus_used, chained_move.

## Narration audit

18 turns audited. Overall 8.2 out of 10.
- result_integrity: 4.5 out of 5
- prompt_elements: 4.7 out of 5
- npc_voice: 4.7 out of 5
- player_agency: 4.5 out of 5
- restraint: 4.5 out of 5
- prose: 4.2 out of 5

## Streaming

18 turns streamed; first sentence after 3.2 seconds (median).
18 complete, 18 identical to the final text.

## Engine events

New NPCs extracted from narration: 1.
Bonuses: 0.
Chained moves: 0.
Pay the Price: 4.
- You are delayed or put at a disadvantage
- The environment or terrain introduces a new hazard
- A new enemy is revealed
- You face the consequences of an earlier choice
Director tool rounds: 0.

## Speed

Turn time: median 9.0 seconds, longest 12.1.

## Cost

- brain (gpt-6-luna): 20 calls, 34705 in, 2317 out, about $0.005
- correction (gpt-6-luna): 2 calls, 1857 in, 202 out, about $0.000
- narrator (gpt-6-luna): 22 calls, 82277 in, 3359 out, about $0.010
- narrator_metadata (gpt-6-luna): 22 calls, 16421 in, 879 out, about $0.002
- revelation_check (gpt-6-luna): 18 calls, 8043 in, 937 out, about $0.001
- Total: about $0.02. Input is counted at full price, so prompt caching makes the real cost lower.
