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
  "next_fire_at": "2026-07-04T18:33:12Z",
  "cadence_secs": 3600
}
```

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | 4 hex chars, lowercase (`^[a-f0-9]{4}$`). Collision-checked against active tasks at creation; re-draw on collision. Stable forever; not reused after drop (no history). |
| `title` | string | yes | The user-provided message text. Stored verbatim (including whitespace and punctuation). |
| `created_at` | string | yes | ISO 8601 UTC, seconds precision (`YYYY-MM-DDTHH:MM:SSZ`). Set once at creation. |
| `next_fire_at` | string | yes | ISO 8601 UTC. The next absolute time the daemon should fire the alarm. Always advances to the future after the daemon re-arms (`next_fire_at = now + cadence_secs`); may transiently be in the past during daemon downtime, in which case the daemon fires-and-advances on startup. |
| `cadence_secs` | integer | yes | The re-arm interval in seconds (e.g. `3600` for `1h`). Must be an integer `>= 1`. Required, non-null. Every task re-arms on every fire; there is no `once` policy. |

There is no stored `state` field. Sort position in `nt ls` is derived from `next_fire_at` versus the CLI-provided `now`; there is nothing else to persist.

## Transitions

All transitions are driven by the daemon (the only writer to this file):

### Create (CLI sends an `add` request)

New task object:
- `created_at`: now
- `next_fire_at`: the time the user specified, converted to UTC
- `cadence_secs`: the parsed interval in seconds, or the default cadence (3600) if the user omitted `every`

### Fire (daemon's in-memory timer expires, or recovery for past `next_fire_at` on startup)

- Fire the OS notification.
- `next_fire_at`: `now + cadence_secs` (schedule the next nag).

That is the whole rule. There are no per-state branches and no once-vs-repeating fork: every task re-arms on every fire.

### Defer (CLI sends a `defer` request)

- `next_fire_at`: the new time the user specified, converted to UTC.
- If the request includes `cadence_secs`: replace the task's `cadence_secs` with it. Otherwise leave `cadence_secs` unchanged.

### Drop (CLI sends a `drop` request)

The task object is removed from the `tasks` array. No tombstone, no history. `drop` is the only exit; there is no auto-expiration, ever.

## Daemon metadata

The top-level `daemon` object records the currently-running daemon:

- `pid`: the daemon's OS PID, or `null` if no daemon is running.
- `started_at`: ISO 8601 UTC of when the current daemon started, or `null`.

CLI uses `pid` for stale-pid detection: if the file says a daemon is running but no process with that PID exists (and the socket is unresponsive), the CLI spawns a fresh daemon and overwrites this field.

## Migration and recovery rules

- On startup, the daemon reads `tasks.json` and re-arms in-memory timers for every task whose `next_fire_at` is in the future.
- For any task whose `next_fire_at` is in the past (alarm due while the daemon was down): the daemon fires the alarm immediately and advances `next_fire_at` to `now + cadence_secs`.

There are no per-state branches. The daemon is stateless about anything other than `next_fire_at` and `cadence_secs`.

## Unused or future fields

The following are reserved for future use and must not appear in v1:

- `state` (one of `"pending"`, `"overdue"`, `"ackd"`)
- `last_fired_at` (ISO 8601 UTC)
- `ackd_at` (ISO 8601 UTC)
- `repeat_interval_secs` (the v1-pre-revision name for `cadence_secs`)
- `notes` (free-form text)
- `tags` (array of strings)
- `priority` (integer)
- `ephemeral` (boolean)

If a v1 implementation encounters a task with these fields, it must preserve them unchanged (round-trip them through reads and writes) but otherwise ignore them.
