# Storage Format

The persistent state of `nt` lives in a single file: `~/.config/nt/tasks.json`.

This document is the binding spec for both the Python (v1) and Go (future) implementations. Both must read and write this format identically so that state survives switching implementations.

## File location

- Path: `$XDG_CONFIG_HOME/nt/tasks.json`, or `~/.config/nt/tasks.json` if `XDG_CONFIG_HOME` is unset.
- Permissions: `0600` (owner read/write only).
- Atomic writes: write to a temp file in the same directory, then `rename` over the target. Never write in place.

## Top-level schema

```json
{
  "version": 1,
  "tasks": [ /* array of Task objects, possibly empty */ ],
  "daemon": {
    "pid": 12345,
    "started_at": "2026-07-04T18:00:00Z"
  }
}
```

- `version`: integer. Schema version. Current version is `1`. Bump if the format changes in a backwards-incompatible way.
- `tasks`: array of Task objects (see below). Order is unspecified; sort in the CLI when displaying.
- `daemon`: metadata about the currently-running daemon, or `{"pid": null, "started_at": null}` if none. Used for stale-pid detection.

## Task object schema

```json
{
  "id": "a3f2",
  "title": "Task x",
  "created_at": "2026-07-04T18:03:12Z",
  "state": "pending",
  "next_fire_at": "2026-07-04T18:33:12Z",
  "last_fired_at": null,
  "ackd_at": null,
  "repeat_interval_secs": null
}
```

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | 4 hex chars, lowercase (`^[a-f0-9]{4}$`). Collision-checked against active tasks at creation; re-draw on collision. Stable forever; not reused after drop (no history). |
| `title` | string | yes | The user-provided message text. Stored verbatim (including whitespace and punctuation). |
| `created_at` | string | yes | ISO 8601 UTC, seconds precision (`YYYY-MM-DDTHH:MM:SSZ`). Set once at creation. |
| `state` | string | yes | One of `"pending"`, `"overdue"`, `"ackd"`. Explicitly stored, not derived (see State transitions below). |
| `next_fire_at` | string | yes | ISO 8601 UTC. The next absolute time the daemon should fire the alarm. May be in the past (for one-shot tasks that already fired once and are now `overdue` or `ackd`); the meaning depends on `state`. |
| `last_fired_at` | string \| null | yes | ISO 8601 UTC or `null`. The last time the daemon fired the alarm. Used to render "fired 47m ago" in the CLI listing. |
| `ackd_at` | string \| null | yes | ISO 8601 UTC or `null`. Set when the user runs `nt ack`. |
| `repeat_interval_secs` | integer \| null | yes | `null` for the `once` policy; otherwise the repeat interval in seconds (e.g. `600` for `10m`). The daemon uses this to re-arm after fire and after ack. |

### State values

| State | Meaning |
|---|---|
| `pending` | Alarm has not yet fired in the current cycle. `next_fire_at` is in the future. |
| `overdue` | Alarm fired at least once and the user has not acked it. For one-shot tasks, `next_fire_at` is in the past (the time it fired). For repeating tasks, `next_fire_at` is in the future (the next nag). |
| `ackd` | User silenced the alarm via `nt ack`. For one-shot tasks, no future fires. For repeating tasks, `next_fire_at` is `ackd_at + repeat_interval_secs` (the next reminder from ack time). |

## State transitions

All transitions are driven by the daemon (which is the only writer to this file):

### Create (CLI sends an `add` request)

New task object:
- `state`: `"pending"`
- `created_at`: now
- `next_fire_at`: the time the user specified, converted to UTC
- `last_fired_at`: `null`
- `ackd_at`: `null`
- `repeat_interval_secs`: `null` for `once`, or the parsed interval in seconds

### Fire (daemon's in-memory timer expires)

- `state`: → `"overdue"`
- `last_fired_at`: now
- If `repeat_interval_secs == null`: `next_fire_at` is unchanged (it's in the past; signals "done firing").
- If `repeat_interval_secs != null`: `next_fire_at` = now + `repeat_interval_secs` (schedules the next nag; state stays `"overdue"` until acked).

### Ack (CLI sends an `ack` request)

- `state`: → `"ackd"`
- `ackd_at`: now
- If `repeat_interval_secs != null`: `next_fire_at` = now + `repeat_interval_secs` (next reminder from ack time).
- If `repeat_interval_secs == null`: `next_fire_at` is unchanged (no future fires).

The acked task remains in the file until the user runs `nt drop`. There is no auto-expiration.

### Drop (CLI sends a `drop` request)

The task object is removed from the `tasks` array. No tombstone, no history.

## Daemon metadata

The top-level `daemon` object records the currently-running daemon:

- `pid`: the daemon's OS PID, or `null` if no daemon is running.
- `started_at`: ISO 8601 UTC of when the current daemon started, or `null`.

CLI uses `pid` for stale-pid detection: if the file says a daemon is running but no process with that PID exists (and the socket is unresponsive), the CLI spawns a fresh daemon and overwrites this field.

## Migration and recovery rules

- On startup, the daemon reads `tasks.json` and re-arms in-memory timers for any task whose `state` is `pending` and `next_fire_at` is in the future.
- For any task whose `state` is `pending` but `next_fire_at` is in the past (alarm due while daemon was down): the daemon fires the alarm immediately and transitions to `overdue` as if the timer had just expired.
- For any task whose `state` is `overdue` (alarm already fired, never acked): the daemon re-arms the next nag timer if `repeat_interval_secs != null`, otherwise does nothing (the one-shot already fired).
- For any task whose `state` is `ackd`: the daemon re-arms the next reminder timer if `repeat_interval_secs != null`, otherwise does nothing.

## Unused or future fields

The following are reserved for future use and must not appear in v1:

- `notes` (free-form text)
- `tags` (array of strings)
- `priority` (integer)
- `ephemeral` (boolean)

If a v1 implementation encounters a task with these fields, it must preserve them unchanged (round-trip them through reads and writes) but otherwise ignore them.