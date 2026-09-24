# Elvira report: starforged, explorer, 5 turns

Verdict: no problems found.

## Coverage

Exercised: result:WEAK_HIT (1), result:STRONG_HIT (2), dialog (2), location_change (1), director (2), save_roundtrip (2), stream_complete (5).

Not exercised: result:MISS, match, combat, npc_introduced, npc_died, clock_fired, burn_offered, burn_taken, correction, chapter_transition, game_over, succession.

## Narration audit

5 turns audited. Overall 9.8 out of 10.
- result_integrity: 5.0 out of 5
- prompt_elements: 5.0 out of 5
- npc_voice: 5.0 out of 5
- player_agency: 5.0 out of 5
- restraint: 4.8 out of 5
- prose: 5.0 out of 5

## Streaming

5 turns streamed; first sentence after 8.8 seconds (median).
5 complete, 5 identical to the final text.

## Speed

Turn time: median 17.9 seconds, longest 24.2.

## Cost

- brain (claude-haiku-4-5-20251001): 5 calls, 12241 in, 544 out, about $0.015
- narrator (claude-opus-5-5): 5 calls, 33359 in, 4912 out, about $0.232
- revelation_check (claude-haiku-4-5-20251001): 5 calls, 4740 in, 296 out, about $0.006
- Total: about $0.25. Input is counted at full price, so prompt caching makes the real cost lower.
