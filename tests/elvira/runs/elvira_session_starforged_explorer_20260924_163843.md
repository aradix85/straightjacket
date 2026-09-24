# Elvira report: starforged, explorer, 3 turns

Verdict: no problems found.

## Coverage

Exercised: result:MISS (1), result:STRONG_HIT (1), match (1), dialog (1), director (2), save_roundtrip (1), stream_complete (3).

Not exercised: result:WEAK_HIT, combat, npc_introduced, npc_died, clock_fired, location_change, burn_offered, burn_taken, correction, chapter_transition, game_over, succession.

## Narration audit

3 turns audited. Overall 6.3 out of 10.
- result_integrity: 4.0 out of 5
- prompt_elements: 4.0 out of 5
- npc_voice: 4.0 out of 5
- player_agency: 3.7 out of 5
- restraint: 2.0 out of 5
- prose: 3.7 out of 5

## Streaming

3 turns streamed; first sentence after 8.6 seconds (median).
3 complete, 3 identical to the final text.

## Speed

Turn time: median 19.9 seconds, longest 22.2.

## Cost

- brain (gpt-6-luna): 3 calls, 5143 in, 313 out, about $0.001
- narrator (claude-opus-5-5): 3 calls, 18779 in, 3027 out, about $0.136
- narrator_metadata (gpt-6-luna): 3 calls, 3093 in, 111 out, about $0.000
- revelation_check (gpt-6-luna): 3 calls, 2170 in, 170 out, about $0.000
- Total: about $0.14. Input is counted at full price, so prompt caching makes the real cost lower.
