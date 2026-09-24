# Elvira report: starforged, explorer, 2 turns

Verdict: no problems found.

## Coverage

Exercised: result:MISS (1), dialog (1), location_change (1), director (2), save_roundtrip (1), stream_complete (2).

Not exercised: result:WEAK_HIT, result:STRONG_HIT, match, combat, npc_introduced, npc_died, clock_fired, burn_offered, burn_taken, correction, chapter_transition, game_over, succession.

## Narration audit

1 turns audited. Overall 6.0 out of 10.
- result_integrity: 3.0 out of 5
- prompt_elements: 4.0 out of 5
- npc_voice: 3.0 out of 5
- player_agency: 5.0 out of 5
- restraint: 2.0 out of 5
- prose: 4.0 out of 5
1 audit(s) failed to produce a verdict.

## Streaming

2 turns streamed; first sentence after 9.6 seconds (median).
2 complete, 2 identical to the final text.

## Speed

Turn time: median 20.1 seconds, longest 21.6.

## Cost

- brain (gpt-6-luna): 2 calls, 3233 in, 241 out, about $0.000
- narrator (claude-opus-5-5): 2 calls, 11443 in, 2182 out, about $0.089
- revelation_check (gpt-6-luna): 2 calls, 1445 in, 121 out, about $0.000
- Total: about $0.09. Input is counted at full price, so prompt caching makes the real cost lower.
