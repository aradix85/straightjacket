# Elvira report: starforged, explorer, 8 turns

Verdict: 2 problem(s) found.

## Problems

- Turn 3: narration audit scored 4/10: The magnetic shudder and comms failure add a serious complication despite the strong hit.
- Turn 6: narration audit scored 4/10: The failed attempt still yields a useful access-log clue, giving the MISS a silver lining.

## Coverage

Exercised: result:MISS (2), result:WEAK_HIT (2), result:STRONG_HIT (1), dialog (2), npc_introduced (1), director (6), correction (1), save_roundtrip (2), stream_complete (7), pay_the_price (2).

Not exercised: match, combat, npc_died, clock_fired, location_change, burn_offered, burn_taken, chapter_transition, game_over, succession, bonus_used, chained_move.

## Narration audit

7 turns audited. Overall 7.0 out of 10.
- result_integrity: 4.0 out of 5
- prompt_elements: 4.4 out of 5
- npc_voice: 4.1 out of 5
- player_agency: 4.4 out of 5
- restraint: 4.4 out of 5
- prose: 4.4 out of 5

## Streaming

7 turns streamed; first sentence after 3.1 seconds (median).
7 complete, 7 identical to the final text.

## Engine events

New NPCs extracted from narration: 1.
Bonuses: 0.
Chained moves: 0.
Pay the Price: 2.
- A new enemy is revealed
- Roll twice; A trusted individual or community acts against you; A surprising development complicates your quest
Director tool rounds: 49.

## Speed

Turn time: median 9.2 seconds, longest 10.6.

## Cost

- brain (gpt-6-luna): 8 calls, 14674 in, 903 out, about $0.002
- correction (gpt-6-luna): 1 calls, 906 in, 91 out, about $0.000
- director (gpt-6-luna): 24 calls, 46509 in, 5981 out, about $0.008
- narrator (gpt-6-luna): 8 calls, 32453 in, 1720 out, about $0.004
- narrator_metadata (gpt-6-luna): 8 calls, 6170 in, 358 out, about $0.001
- revelation_check (gpt-6-luna): 7 calls, 3618 in, 391 out, about $0.001
- Total: about $0.02. Input is counted at full price, so prompt caching makes the real cost lower.
