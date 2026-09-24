# Elvira report: starforged, explorer, 8 turns

Verdict: 1 problem(s) found.

## Problems

- Engine WARNING: [Director] Failed (BadRequestError: Error code: 400 - {'error': {'message': "Function tools with reasoning_effort are not supported for gpt-6-luna in /v1/chat/completions. To use function too (6 times)

## Coverage

Exercised: result:WEAK_HIT (5), result:STRONG_HIT (1), dialog (1), director (6), correction (1), save_roundtrip (2), stream_complete (7), bonus_used (1).

Not exercised: result:MISS, match, combat, npc_introduced, npc_died, clock_fired, location_change, burn_offered, burn_taken, chapter_transition, game_over, succession, chained_move, pay_the_price.

## Narration audit

7 turns audited. Overall 8.3 out of 10.
- result_integrity: 4.6 out of 5
- prompt_elements: 4.6 out of 5
- npc_voice: 4.4 out of 5
- player_agency: 4.3 out of 5
- restraint: 5.0 out of 5
- prose: 4.4 out of 5

## Streaming

7 turns streamed; first sentence after 2.8 seconds (median).
7 complete, 7 identical to the final text.

## Engine events

New NPCs extracted from narration: 0.
Bonuses: 2.
- Gearhead: +1
- Gearhead: +1 momentum on a hit
Chained moves: 0.
Pay the Price: 0.
Director tool rounds: 0.

## Speed

Turn time: median 7.3 seconds, longest 8.7.

## Cost

- brain (gpt-6-luna): 8 calls, 14673 in, 902 out, about $0.002
- correction (gpt-6-luna): 1 calls, 840 in, 98 out, about $0.000
- narrator (gpt-6-luna): 8 calls, 29127 in, 1436 out, about $0.004
- narrator_metadata (gpt-6-luna): 8 calls, 5691 in, 296 out, about $0.001
- revelation_check (gpt-6-luna): 7 calls, 3327 in, 370 out, about $0.001
- Total: about $0.01. Input is counted at full price, so prompt caching makes the real cost lower.
