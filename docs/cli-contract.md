# CLI Contract

This document is the binding spec for the `nt` command-line interface. Both the Python (v1) and Go (future) implementations must satisfy this contract exactly so that shell completion, scripts, and user muscle memory transfer between them.

It governs: commands, flags, exit codes, stdout/stderr content, and output formatting.

## Commands

### `nt` (bare)

Equivalent to `nt ls`. See below.

### `nt ls`

Lists active tasks in a single continuous list, sorted by `next_fire_at` ascending (soonest-fire first). There are no sections, no stored states, and no `[STALE]` markers; sort position is the only thing that distinguishes an urgent task from an upcoming one.

If there are no active tasks, print exactly:

```
no active tasks.
```

There are no `--overdue` / `--pending` / `--ackd` filter flags. Filtering is deferred to a post-v1 milestone if it is needed at all.

### `nt <when> ["every <interval>"] "<title>"`

Creates a task whose alarm fires at `<when>` and then re-arms on a cadence. `every <interval>` is optional; when omitted, the cadence defaults to 1h (`3600` seconds) for v1. Configurability of the default cadence is a post-v1 milestone (the `--config` reserved flag is its eventual surface).

Output to stdout, one line:

```
created 'Task x' [a3f2] fires in 30m
```

For absolute times that land >24h away, the relative part uses absolute form:

```
created 'Task x' [a3f2] fires 10 Apr 10:55
```

Because every task has a cadence, the output line does not separately announce "repeats every Nm" — that the alarm re-arms is the model's default behavior, not a special mode.

### `nt defer <ref> <when> ["every <interval>"]`

Reschedules the referenced task: sets its `next_fire_at` to `<when>`, and optionally replaces its cadence. `every <interval>`, if present, replaces `cadence_secs` for the task; if omitted, the existing cadence is preserved.

Output:

```
deferred 'Task x' [a3f2] fires in 30m
```

For absolute times that land >24h away:

```
deferred 'Task x' [a3f2] fires 10 Apr 10:55
```

`defer` is the only way to silence a fired alarm without removing the task: it pushes `next_fire_at` into the future, so the task resumes firing on its cadence from the new time. Acknowledging-into-a-permanent-`ackd` state is gone; once a task is no longer needed, the only exit is `drop`.

### `nt drop <ref>`

Removes the referenced task. Output:

```
dropped 'Task x' [a3f2]
```

`drop` is the only completion verb and the only way a task leaves the system. There is no auto-cleanup, ever; this is now enforced by construction — nothing can accumulate, because there is no state in which a task lingers without a future fire.

### `nt --help` / `nt -h`

Prints usage to stdout, exit 0. Standard for `--version` / `-V` as well.

### Commands intentionally absent from v1

- `nt note` — deferred (post-v1).
- `nt done` — explicitly not provided; use `nt drop`.
- `nt history`, `nt log`, `nt reopen` — explicitly not provided; no history.
- `nt complete <shell>` — shell completion scripts: deferred to a later milestone within v1 lifecycle (not blocking the core).

## Reference resolution (`<ref>`)

Commands that take a `<ref>` (`defer`, `drop`) resolve it in this order:

1. **Hex ID match.** If the ref matches `^[a-f0-9]{4}$`, look it up by task ID. If no task has that ID: exit 1 with stdout empty, stderr `error: no task with id '<ref>'`.
2. **Exact substring match against titles.** If exactly one task's title contains the ref as a substring (case-sensitive): act on that task.
   - If multiple tasks match: in a TTY, render the interactive fuzzy menu (see below); in a non-TTY, exit 1 with stderr `error: multiple tasks match '<ref>':` followed by a one-line-per-match list to stderr.
   - If zero tasks match: exit 1 with stderr `error: no task matches '<ref>'`.

### No-argument behavior

`nt defer` and `nt drop` with no ref argument:

- In a TTY: open the fuzzy menu with the full task list (ranked in canonical `nt ls` order). User selects, presses enter to apply.
- In a non-TTY: print usage to stderr, exit 2.

No silent no-ops. POSIX convention: missing required argument = usage error, exit 2.

### Interactive fuzzy menu (TTY only)

Rendered inline below the command prompt. Behavior:

- Fuzzy-match the typed prefix (and continued typing) against task titles.
- Show all matches ranked by the canonical `nt ls` order (soonest `next_fire_at` first).
- Top match highlighted. Other matches shown faint.
- Tab: list the full candidate set (no filtering by typed prefix).
- First Enter: apply to the highlighted top match. One-line confirmation printed (`dropped 'Task x' [a3f2]`). No "are you sure?" prompt.
- Escape / Ctrl-C: abort, exit 1 with stderr `aborted`.

### Non-interactive (pipe, script, no TTY)

- Resolution via hex ID or exact substring only.
- Ambiguous substring match (more than one task): error with the list.
- No fuzzy menu is rendered. The `--yes` flag is not needed because there is no confirmation step to skip.

## Time syntax

The `<when>` and `<interval>` arguments accept these forms only:

### Intervals (both `<when>` and `every <interval>`)

- `30m`, `2h`, `1d`, `3d` — integer followed by `m`, `h`, or `d`.
- No decimals. No weeks (`w`), no months, no combined forms like `1h30m`.

### Absolute times (only `<when>`)

- `HH:MM` in 24-hour, zero-padded: `14:30`, `09:05`, `00:15`. Today's date is assumed.
- `D Mon HH:MM`: `10 Apr 10:55`. Day-of-month first (no leading zero required), three-letter month name (case-insensitive on input), then time.
- `tomorrow HH:MM`: tomorrow's date at the given time.
- `monday HH:MM` (and `tuesday`...`sunday`): the next occurrence of that weekday at the given time, computed from now. If today is Monday and the user says `monday 9:00`, this is ambiguous — we define it as today if the time hasn't passed, else next week.
- `next monday HH:MM` (and `tuesday`...`sunday`): explicitly the next week's occurrence, skipping today's.

### Explicitly excluded in v1

- am/pm (use 24h).
- Bare `tomorrow` or bare weekday (no time component).
- Natural language: "in a bit", "soon", "end of day", etc.
- Combined intervals (`1h30m`).

### Past-time errors

If an absolute `<when>` parses to a time in the past, exit 1 with stderr:

```
error: 14:30 is in the past (now 15:02)
```

No rollover, no rearm to tomorrow. The user must be explicit (`tomorrow 14:30`).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Runtime error (ref not found, ambiguous ref in non-TTY, past time, daemon unreachable after timeout, etc.) |
| 2 | Usage error (missing required argument, unknown flag, malformed input) |

Parse errors (malformed time syntax, etc.) also exit 2 with a `error: ...` message to stderr.

## Output format — `nt ls`

### List layout

A single continuous list, sorted by `next_fire_at` ascending (soonest-fire first). No section headers, no state-derived zones, no `[STALE]` markers.

```
  a3f2  Standup sync                          in 8m (14:30)
  b7e8  Reply to Mike                          in 1h
  c1d9  Follow up on deploy                   tomorrow 09:00
  d4e7  Re-deploy after merge                 10 Apr 10:55
```

If the list is empty, print exactly `no active tasks.` (no header, no whitespace).

### Column rules

- Two-space indent, then ID left-aligned to width 4, two spaces separator, then title, then status.
- The title column is aligned to the longest title in the whole list (one list, not per-section), so the status column lines up.
- If the list is empty, nothing else is printed beyond `no active tasks.`.

### Status string rules

Every task's status is forward-looking, derived from `next_fire_at` versus the CLI-provided `now`:

| Condition | Status format |
|---|---|
| `next_fire_at` < 60s from `now` | `in Ns` |
| `next_fire_at` < 60m from `now` | `in Nm` |
| `next_fire_at` < 24h from `now` | `in Nh` |
| `next_fire_at` is tomorrow | `tomorrow HH:MM` (HH:MM in local time) |
| `next_fire_at` further than tomorrow | `D Mon HH:MM` (local time) |

There is no `fired Xh ago` form, no `acked Nh ago` form, no `next in Nm` form, and no `[STALE]` marker. Forward-looking only.

### Relative-time formatting

- < 60s: `in Ns`
- < 60m: `in Nm`
- < 24h: `in Nh`
- >= 24h: absolute form (`tomorrow HH:MM`, `D Mon HH:MM`)

Numbers are always integers, rounded down. No decimals anywhere in `nt` output.

If `next_fire_at <= now` (daemon was down and missed a fire): the coordinator is the daemon's startup recovery rule, which fires-and-advances immediately; by the time the CLI runs `nt ls`, such tasks have already been rescheduled into the future. The CLI therefore never needs to render a "past fire" status, and assumes `next_fire_at > now` when rendering.

## Daemon lifecycle from the CLI's perspective

- Every CLI invocation begins by attempting to connect to the daemon socket (`~/.config/nt/daemon.sock`).
- If connection succeeds: send request, read response, render, exit.
- If connection fails:
  1. Clean up stale socket file if present.
  2. Spawn the daemon detached (double-fork or equivalent; the CLI does not wait for the daemon to stay up).
  3. Poll the socket with a timeout (default 2 seconds). If the daemon comes up, proceed. If timeout: exit 1 with stderr `error: daemon failed to start`.
- The CLI never imports or runs daemon logic in-process; it always talks to the daemon via the socket. Even bare `nt ls` goes through the socket.

## Shell completion (future)

A `nt completion <bash|zsh|fish>` command will be added later in v1's lifecycle to print completion scripts. Completion candidates for `<ref>` positions are the hex IDs and title prefixes of currently-active tasks, fetched live from the daemon.

This is not blocking for v1 core functionality.

## Reserved flags

These flags are reserved for future use and must not be repurposed in v1:

- `--json` (machine-readable output for `nt ls`)
- `--yes` / `-y` (no longer needed in current design; reserved against future reintroduction)
- `--verbose` / `-v`
- `--config <path>` (alternate config file; the future surface for the configurable default cadence)
- `--non-interactive` / `-n` (force non-TTY resolution path even in a TTY)

If encountered in v1, these must produce exit 2 with `error: --json is not yet supported` (or equivalent), not silent acceptance.
