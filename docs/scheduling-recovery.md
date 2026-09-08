# Scheduling explanations and missed-block recovery

Phase 6 extends the existing authenticated solve operation. It does not add a
second scheduler or mutate the saved week during a solve.

## Missed occurrences

A locked `TimeBlock` may contain `missed_days`, a unique subset of its `days`.
The solver excludes only those weekday occurrences from locked occupancy. The
block and its other occurrences remain in the saved week, so a miss can be
restored after a reload. Flexible blocks cannot contain missed days.

The browser offers **Mark missed** after a solve when a user opens a locked
occurrence. It sends the current blocks and the previous placement back to the
server, applies the returned trace, then saves the added missed day through the
normal revision-checked `PUT /api/week` path.

## Solve request

`POST /api/solve` keeps its existing `{ "blocks": [...] }` body. Recovery adds
an optional object:

```json
{
  "blocks": [],
  "recover": {
    "missed_block_id": "school",
    "missed_day": 0,
    "previous_placed": []
  }
}
```

The missed id and day must identify one occurrence of a locked block. Previous
placement ids must be unique. Invalid recovery requests return 422.

## Solve trace

The trace adds `explanations`. Each explanation identifies a block and carries
student-facing text authored by `backend/explain.py`. It may also carry a
reason code or deadline slack:

```json
{
  "block_id": "homework",
  "message": "Limited room: scheduled to finish 2h before the deadline.",
  "reason": null,
  "slack_min": 120,
  "slack_status": "tight"
}
```

Slack is the elapsed time from a placed flexible block's end to its deadline.
Zero through 60 minutes is `danger`, 61 through 180 minutes is `tight`, and
more than 180 minutes is `ok`. Tasks without a deadline have no slack entry.
A task placed outside its preferred energy window receives an
`ENERGY_MISMATCH` explanation.

Recovery compares flexible placements by block id and `(day, start)`. A changed
move contains `from_day`, `from_start`, `to_day`, and `to_start`, using null for
an unplaced side. Cross-day moves therefore remain distinct even when the clock
time is unchanged. The reason is `RESHUFFLE_AFTER_MISS` unless the new result is
unplaced, in which case its placement-failure reason remains authoritative.

The browser displays the explanation text, highlights the corresponding grid
block or unplaced task when selected, paints deadline slack badges, and lists
the before/after placement changes. Missed occurrences remain listed with a
restore action even after reloading and solving again.
