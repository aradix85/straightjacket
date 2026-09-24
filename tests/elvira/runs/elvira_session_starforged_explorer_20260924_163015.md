# Elvira report: starforged, explorer, 3 turns

Verdict: no problems found.

## Coverage

Exercised: result:WEAK_HIT (1), result:STRONG_HIT (1), dialog (1), director (2), save_roundtrip (1), stream_complete (3).

Not exercised: result:MISS, match, combat, npc_introduced, npc_died, clock_fired, location_change, burn_offered, burn_taken, correction, chapter_transition, game_over, succession.

## Narration audit

3 turns audited. Overall 6.0 out of 10.
- result_integrity: 4.0 out of 5
- prompt_elements: 3.0 out of 5
- npc_voice: 2.3 out of 5
- player_agency: 4.3 out of 5
- restraint: 2.3 out of 5
- prose: 4.0 out of 5

## Streaming

3 turns streamed; first sentence after 7.5 seconds (median).
3 complete, 3 identical to the final text.

## Speed

Turn time: median 15.9 seconds, longest 17.0.

## Cost

- brain (gpt-6-luna): 3 calls, 4850 in, 327 out, about $0.001
- narrator (claude-opus-5-5): 3 calls, 17510 in, 2527 out, about $0.121
- Total: about $0.12. Input is counted at full price, so prompt caching makes the real cost lower.
