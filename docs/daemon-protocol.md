# Daemon Protocol

This document is the binding spec for the IPC between the `nt` CLI and the `nt` daemon. Both the Python (v1) and Go (future) implementations of the daemon must speak this protocol so that any CLI can drive any daemon.

## Transport

- **Socket type:** `AF_UNIX`, `SOCK_STREAM`.
- **Socket path:** `$XDG_CONFIG_HOME/nt/daemon.sock`, or `~/.config/nt/daemon.sock` if `XDG_CONFIG_HOME` is unset.
- **Permissions:** socket file is created with mode `0600` (owner-only). Only the owning user can connect.
- **Connection model:** one connection per CLI invocation. Open socket, send one request, read one response, close. The daemon handles many concurrent connections by accepting sequentially (no multiplexing required at v1 scale).

## Framing

- **Encoding:** UTF-8 JSON.
- **Framing:** newline-delimited. Each request is a single JSON object terminated by `\n`; each response is a single JSON object terminated by `\n`.
- **Max message size:** 64 KiB. Messages larger than this are a protocol error.
- **Request lifecycle:** exactly one request per connection, exactly one response per request. Pipelining is not supported in v1.

## Request envelope

Every request is a JSON object with this shape:

```json
{
  "type": "add",
  /* type-specific fields */
}
```

The `type` field is required and selects the handler. Unknown `type` values produce an error response.

## Response envelope

Every response is a JSON object with one of these two shapes:

**Success:**

```json
{
  "ok": true,
  /* type-specific fields */
}
```

**Error:**

```json
{
  "ok": false,
  "error": "human-readable message",
  "code": "not_found" | "ambiguous" | "usage" | "internal" | "past_time" | "parse"
}
```

Error codes are stable and part of the contract; the CLI may branch on them. The `error` string is free-form and intended for display to the user via stderr.

## Message types

### `ping`

Health check. No type-specific fields.

Request:
```json
{ "type": "ping" }
```

Response (success):
```json
{ "ok": true, "pid": 12345, "uptime_secs": 312 }
```

Used by the CLI to detect whether a daemon is already running before attempting to spawn one.

### `add`

Create a new task. The CLI parses the user's `<when>` and `<interval>` strings into absolute UTC and a seconds count before sending; the daemon does not parse time strings.

Request:
```json
{
  "type": "add",
  "title": "Task x",
  "next_fire_at": "2026-07-04T18:33:12Z",
  "repeat_interval_secs": null,
  "created_at": "2026-07-04T18:03:12Z"
}
```

Fields:
- `title` (string, required, non-empty after trim).
- `next_fire_at` (ISO 8601 UTC string, required). Must be in the future; if not, the daemon returns a `past_time` error. (The CLI pre-validates, but the daemon re-validates.)
- `repeat_interval_secs` (integer >= 1, or `null`). `null` means the `once` policy.
- `created_at` (ISO 8601 UTC string, required). Set by the CLI to the current time; the daemon does not override it. (Sending the timestamp from the CLI keeps the daemon stateless about wall-clock time beyond what it needs for scheduling.)

Response (success):
```json
{ "ok": true, "id": "a3f2" }
```

The daemon assigns the `id` (4-char hex, collision-checked against active tasks).

### `ack`

Acknowledge a task by reference. The daemon resolves the ref against its in-memory task list (the single source of truth); the CLI does not perform ref resolution.

Request:
```json
{ "type": "ack", "ref": "a3f2" }
```

Fields:
- `ref` (string, required). Either a 4-char hex ID or a substring to match against titles.

Resolution rules (executed by the daemon):
1. If `ref` matches `^[a-f0-9]{4}$`: look up by ID. If no match: `not_found` error.
2. Else: substring-match against all active task titles. If exactly one match: act on it. If multiple: `ambiguous` error with the list of matches in the response. If zero: `not_found` error.

Response (success):
```json
{ "ok": true, "task": { /* full task object */ } }
```

The response includes the full task object (post-ack state) so the CLI can render the confirmation line without a separate round-trip.

Response (ambiguous):
```json
{
  "ok": false,
  "code": "ambiguous",
  "error": "multiple tasks match 'pr':",
  "matches": [
    { "id": "a3f2", "title": "PR review from Sara", "state": "overdue" },
    { "id": "b7e8", "title": "Reply to Mike on PR", "state": "pending" }
  ]
}
```

In a TTY, the CLI renders the fuzzy menu from `matches` and re-sends an `ack` request with the chosen hex ID. In a non-TTY, the CLI prints the error and exits 1.

### `drop`

Remove a task. Same request/response shape as `ack`.

Request:
```json
{ "type": "drop", "ref": "a3f2" }
```

Response (success):
```json
{ "ok": true, "task": { /* full task object as it was before drop */ } }
```

### `list`

Request a filtered list of tasks. Used by `nt ls`.

Request:
```json
{
  "type": "list",
  "filters": ["overdue", "pending", "ackd"],
  "now": "2026-07-04T18:03:12Z"
}
```

Fields:
- `filters` (array of strings, optional; default = all three). Allowed values: `"overdue"`, `"pending"`, `"ackd"`. Unknown values: `usage` error.
- `now` (ISO 8601 UTC string, required). The CLI sends its current wall-clock time; the daemon uses this to compute relative-time status strings (`"fired 47m ago"`, etc.) and to determine staleness. Rationale: keeps the daemon stateless about display time, and lets the CLI render consistently across any clock skew.

Response (success):
```json
{
  "ok": true,
  "sections": [
    {
      "name": "OVERDUE",
      "tasks": [ /* full task objects with computed `status` and `stale` fields */ ]
    },
    {
      "name": "PENDING",
      "tasks": [ ... ]
    },
    {
      "name": "ACKED, NOT DONE",
      "tasks": [ ... ]
    }
  ]
}
```

Each task object in the response is augmented with two additional display-only fields that the daemon computes:

```json
{
  "id": "a3f2",
  "title": "...",
  "created_at": "...",
  "state": "overdue",
  "next_fire_at": "...",
  "last_fired_at": "...",
  "ackd_at": null,
  "repeat_interval_secs": null,
  "status": "fired 47m ago",
  "stale": false
}
```

Tasks are pre-sorted by the daemon in the canonical order for each section:
- OVERDUE: by `last_fired_at` ascending.
- PENDING: by `next_fire_at` ascending.
- ACKED: by `ackd_at` descending.

Empty sections are included in the response with an empty `tasks` array; the CLI decides whether to print them (per the CLI contract, empty sections are omitted from output).

### `shutdown`

Request the daemon to exit cleanly. Used for debugging / manual cleanup; not part of normal CLI flow.

Request:
```json
{ "type": "shutdown" }
```

Response (success):
```json
{ "ok": true }
```

The daemon deletes the socket file on exit.

## Daemon lifecycle

### Startup

1. Daemon process is spawned detached by the CLI on first invocation (the CLI detects an unresponsive socket and forks the daemon).
2. Daemon on startup:
   - Creates the socket file at the canonical path.
   - Reads `tasks.json`.
   - Re-arms in-memory timers for all tasks needing them (see Recovery rules below).
   - Updates `tasks.json:daemon` with its `pid` and `started_at`.
   - Begins accepting connections.
3. If the socket file already exists but is unresponsive (stale socket): the CLI removes it before spawning. The daemon, on startup, also removes any pre-existing socket file at its path before binding (defensive).
4. If the daemon cannot acquire the socket (permissions, missing parent directory): it exits with a non-zero code; the CLI's wait-for-socket poll times out and reports `error: daemon failed to start`.

### Runtime

- The daemon is the only writer to `tasks.json`. Concurrent CLI requests are serialized by the daemon's accept loop; no file locking is required.
- On any state change (fire, ack, drop, add), the daemon writes `tasks.json` atomically (temp file + rename) *after* updating its in-memory state, before sending the response. This ensures the file always reflects a consistent state.
- The daemon holds in-memory timers (one per task that has a future `next_fire_at` and is not `ackd` for one-shot tasks). When a timer fires, the daemon sends the OS notification and updates the task's state and fields in memory and on disk.

### Notification delivery

- Linux: shell out to `notify-send` (libnotify). If `notify-send` is not on PATH, fall back to writing the message to stdout prefixed with `[nt]` (visible if the daemon is run in foreground; invisible in detached mode — acceptable degradation for missing-system-dependency case).
- macOS: shell out to `osascript -e 'display notification "..." with title "nt" sound name ""'`. No sound, as per the design decisions.
- The notification title is `nt`. The body is the task title.
- Notification failure (e.g. `notify-send` returns non-zero) is logged to the daemon's stderr but does not change task state. The alarm still counts as fired; the state transition still occurs.

### Clock and timezones

- The daemon stores and transmits all times in UTC (ISO 8601 with `Z`).
- The CLI is responsible for converting user input (local time, "tomorrow", weekday names) to UTC before sending requests.
- The CLI is responsible for converting UTC times to local time in display output. The `list` response's `status` field is pre-computed by the daemon using the `now` field from the request; the daemon is given the CLI's wall clock and uses it for relative formatting.

### Recovery on startup (after downtime)

When the daemon starts and reads `tasks.json`, for each task:

- If `state == "pending"` and `next_fire_at <= now`: the alarm was due while the daemon was down. Fire it immediately (send notification), transition to `overdue`, set `last_fired_at = now`. Apply the repeating-task re-arm rule if applicable.
- If `state == "pending"` and `next_fire_at > now`: schedule an in-memory timer.
- If `state == "overdue"`: no immediate action. If `repeat_interval_secs != null`, schedule the next nag timer at `next_fire_at` (which is in the future for repeating tasks).
- If `state == "ackd"`: no immediate action. If `repeat_interval_secs != null`, schedule the next reminder timer at `next_fire_at`.

### Crash recovery

- If the daemon crashes, the CLI's next invocation detects the unresponsive socket, cleans up, and spawns a fresh daemon. The fresh daemon's startup recovery (above) handles any alarms that were due while the previous daemon was down.
- Process state (in-memory timers) is always reconstructable from `tasks.json`. There is no separate daemon-state file.

### Snapshot vs. in-memory truth

- `tasks.json` is the persistent snapshot. The daemon's in-memory task list is the live truth during operation.
- On every mutation, the daemon updates in-memory state first, then writes the file. The file is always a consistent point-in-time representation.
- On startup, the file is the truth (in-memory state is rebuilt from it). During operation, in-memory state is the truth (the file is kept in sync).

## Versioning

- The protocol has no explicit version field in v1. The single `tasks.json` `version` field (currently `1`) implicitly versions both the file format and the daemon protocol; they evolve together.
- If the protocol needs to change in a backwards-incompatible way, the file `version` will be bumped and both sides will negotiate via the `ping` response (extended with a `protocol_version` field in that future version).

## Security

- The socket is created with mode `0600`; only the owning OS user can connect.
- The CLI and daemon communicate only locally; there is no remote access surface.
- No authentication, tokens, or encryption are used. Filesystem permissions are the security boundary.
- The daemon refuses connections from processes owned by a different OS user; the kernel enforces this via the socket file permissions.

## Examples (full round-trips)

### Create a one-shot task

CLI → daemon:
```json
{"type":"add","title":"Task x","next_fire_at":"2026-07-04T18:33:12Z","repeat_interval_secs":null,"created_at":"2026-07-04T18:03:12Z"}
```

Daemon → CLI:
```json
{"ok":true,"id":"a3f2"}
```

### List with no filters (default)

CLI → daemon:
```json
{"type":"list","filters":["overdue","pending","ackd"],"now":"2026-07-04T18:03:12Z"}
```

Daemon → CLI (abbreviated):
```json
{"ok":true,"sections":[{"name":"OVERDUE","tasks":[{"id":"a3f2","title":"Task x","state":"overdue","next_fire_at":"2026-07-04T18:33:12Z","last_fired_at":"2026-07-04T18:33:12Z","ackd_at":null,"repeat_interval_secs":null,"status":"fired 30m ago","stale":false}]},{"name":"PENDING","tasks":[]},{"name":"ACKED, NOT DONE","tasks":[]}]}
```

### Ambiguous ack in a non-TTY

CLI → daemon:
```json
{"type":"ack","ref":"pr"}
```

Daemon → CLI:
```json
{"ok":false,"code":"ambiguous","error":"multiple tasks match 'pr':","matches":[{"id":"a3f2","title":"PR review from Sara","state":"overdue"},{"id":"b7e8","title":"Reply to Mike on PR","state":"pending"}]}
```

The CLI (in non-TTY mode) prints the error to stderr and exits 1. In a TTY, the CLI renders the fuzzy menu from `matches` and sends a follow-up `ack` request with the selected hex ID.