# Elvira report: starforged, explorer, 8 turns

Verdict: 1 problem(s) found.

## Problems

- Engine WARNING: [Tools] Hit max rounds (3), forcing text from last response

## Coverage

Exercised: result:WEAK_HIT (4), result:STRONG_HIT (2), match (1), dialog (1), location_change (2), director (4), burn_offered (1), burn_taken (1), correction (1), save_roundtrip (2), stream_complete (7).

Not exercised: result:MISS, combat, npc_introduced, npc_died, clock_fired, chapter_transition, game_over, succession, bonus_used, chained_move, pay_the_price.

## Narration audit

7 turns audited. Overall 7.9 out of 10.
- result_integrity: 4.7 out of 5
- prompt_elements: 4.6 out of 5
- npc_voice: 4.3 out of 5
- player_agency: 4.3 out of 5
- restraint: 4.4 out of 5
- prose: 4.3 out of 5

## Streaming

7 turns streamed; first sentence after 2.9 seconds (median).
7 complete, 7 identical to the final text.

## Engine events

New NPCs extracted from narration: 0.
Bonuses: 0.
Chained moves: 0.
Pay the Price: 0.
Director tool rounds: 29.

## Speed

Turn time: median 7.8 seconds, longest 9.3.

## Cost

- brain (gpt-6-luna): 8 calls, 14862 in, 976 out, about $0.002
- correction (gpt-6-luna): 1 calls, 937 in, 132 out, about $0.000
- director (gpt-6-luna): 15 calls, 24076 in, 2794 out, about $0.004
- narrator (gpt-6-luna): 9 calls, 36816 in, 1979 out, about $0.005
- narrator_metadata (gpt-6-luna): 9 calls, 7020 in, 368 out, about $0.001
- revelation_check (gpt-6-luna): 7 calls, 3589 in, 397 out, about $0.001
- Total: about $0.01. Input is counted at full price, so prompt caching makes the real cost lower.
