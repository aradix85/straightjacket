# Elvira report: starforged, explorer, 1 turns

Verdict: 1 problem(s) found.

## Problems

- Turn 1: engine or bot error: Error code: 400 - {'error': {'message': "Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported.", 'type': 'invalid_request_error', 'param': 'temperature', 'code': 'unsupported_value'}}

## Coverage

Exercised: save_roundtrip (1).

Not exercised: result:MISS, result:WEAK_HIT, result:STRONG_HIT, match, dialog, combat, npc_introduced, npc_died, clock_fired, location_change, director, burn_offered, burn_taken, correction, chapter_transition, game_over, succession, stream_complete.

## Narration audit

No turns audited.

## Streaming

No turns streamed.

## Speed

No timed turns.

## Cost

- Total: about $0.00. Input is counted at full price, so prompt caching makes the real cost lower.
