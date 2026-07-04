# CLI Contract

This document is the binding spec for the `nt` command-line interface. Both the Python (v1) and Go (future) implementations must satisfy this contract exactly so that shell completion, scripts, and user muscle memory transfer between them.

It governs: commands, flags, exit codes, stdout/stderr content, and output formatting.

## Commands

### `nt` (bare)

Equivalent to `nt ls`. See below.

### `nt ls`

Lists not-done tasks grouped into three sections, in this fixed order:

1. `OVERDUE` — tasks whose state is `overdue`. Sorted by `last_fired_at` ascending (oldest-fired first).
2. `PENDING` — tasks whose state is `pending`. Sorted by `next_fire_at` ascending (soonest-fire first).
3. `ACKED, NOT DONE` — tasks whose state is `ackd`. Sorted by `ackd_at` descending (most recently acked first).

Empty sections are omitted entirely (no header printed for a section with no tasks in it).

If all sections are empty (no active tasks), print exactly:

```
no active tasks.
```

### `nt ls --overdue` / `--pending` / `--ackd`

Filters the listing to a subset of sections. Multiple flags combine as a union; sections still appear in the canonical order (OVERDUE, PENDING, ACKED). If no flag is given, all three sections are eligible to appear (subject to omission-when-empty rule).

### `nt <when> "<title>"`

Creates a task with a one-shot alarm at the given time. Output to stdout, one line:

```
created 'Task x' [a3f2] fires in 30m
```

For absolute times that land >24h away, the relative part uses absolute form:

```
created 'Task x' [a3f2] fires 10 Apr 10:55
```

### `nt <when> every <interval> "<title>"`

Creates a task with a repeating alarm. Output:

```
created 'Task x' [a3f2] fires in 30m, repeats every 10m until acked
```

### `nt ack <ref>`

Silences the alarm for the referenced task. Output:

```
acked 'Task x' [a3f2]
```

For repeating tasks, acking also re-arms the next reminder `repeat_interval_secs` from now; this is not separately announced in the output.

### `nt drop <ref>`

Removes the referenced task. Output:

```
dropped 'Task x' [a3f2]
```

### `nt --help` / `nt -h`

Prints usage to stdout, exit 0. Standard for `--version` / `-V` as well.

### Commands intentionally absent from v1

- `nt note` — deferred (post-v1).
- `nt done` — explicitly not provided; use `nt drop`.
- `nt history`, `nt log`, `nt reopen` — explicitly not provided; no history.
- `nt complete <shell>` — shell completion scripts: deferred to a later milestone within v1 lifecycle (not blocking the core).

## Reference resolution (`<ref>`)

Commands that take a `<ref>` (`ack`, `drop`) resolve it in this order:

1. **Hex ID match.** If the ref matches `^[a-f0-9]{4}$`, look it up by task ID. If no task has that ID: exit 1 with stdout empty, stderr `error: no task with id '<ref>'`.
2. **Exact substring match against titles.** If exactly one task's title contains the ref as a substring (case-sensitive): act on that task.
   - If multiple tasks match: in a TTY, render the interactive fuzzy menu (see below); in a non-TTY, exit 1 with stderr `error: multiple tasks match '<ref>':` followed by a one-line-per-match list to stderr.
   - If zero tasks match: exit 1 with stderr `error: no task matches '<ref>'`.

### No-argument behavior

`nt ack` and `nt drop` with no ref argument:

- In a TTY: open the fuzzy menu with the full task list (ranked in canonical `nt ls` order). User selects, presses enter to apply.
- In a non-TTY: print usage to stderr, exit 2.

No silent no-ops. POSIX convention: missing required argument = usage error, exit 2.

### Interactive fuzzy menu (TTY only)

Rendered inline below the command prompt. Behavior:

- Fuzzy-match the typed prefix (and continued typing) against task titles.
- Show all matches ranked by the canonical `nt ls` order (overdue oldest-first, then pending soonest-first, then ackd most-recent-first).
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

### Section layout

```
OVERDUE
  a3f2  Task waiting on PR review from Sara   fired 47m ago
  b7e8  Check the deployment log              fired 12m ago

PENDING
  c1d9  Standup sync                          in 8m (14:30)
  d4e7  Reply to Mike                          in 1h
  f2a5  Follow up on deploy                   tomorrow 09:00

ACKED, NOT DONE
  e9b3  Re-deploy after merge                 acked 15m ago
```

### Column rules

- ID left-aligned to width 4, two spaces separator, then title, then status.
- Within a section, the title column is aligned to the longest title in that section (so the status column lines up). Across sections, alignment is independent (each section re-aligns).
- Section headers are uppercase, no leading whitespace. Tasks are indented two spaces relative to the header.

### Status string rules

Status strings depend on state:

| State | Status format |
|---|---|
| `pending` (next fire < 24h away) | `in Nh` or `in Nm` (rounded down to the largest unit that fits) |
| `pending` (next fire >= 24h away) | `tomorrow HH:MM` (if tomorrow) or `D Mon HH:MM` (if further) |
| `overdue` (one-shot) | `fired Nh ago` or `fired Nm ago` (relative only; absolute is not useful here) |
| `overdue` (repeating, nag pending) | `fired Nh ago, next in Nm` |
| `ackd` (one-shot) | `acked Nh ago` |
| `ackd` (repeating, next reminder pending) | `acked Nh ago, next in Nm` |

### Stale marker

A task whose state is `overdue` and whose `last_fired_at` is older than the staleness threshold (default: 24 hours) gets a `[STALE]` marker prepended to its status:

```
  a3f2  Old forgotten thing [STALE]   fired 2d ago
```

The threshold is fixed at 24h for v1; configurability is deferred.

### Relative-time formatting

- < 60s: `in Ns` / `Ns ago` (rare; mostly for very short test intervals)
- < 60m: `in Nm` / `Nm ago`
- < 24h: `in Nh` / `Nh ago`
- >= 24h: absolute form (`tomorrow HH:MM`, `D Mon HH:MM`)

Numbers are always integers, rounded down. No decimals anywhere in `nt` output.

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
- `--config <path>` (alternate config file)
- `--non-interactive` / `-n` (force non-TTY resolution path even in a TTY)

If encountered in v1, these must produce exit 2 with `error: --json is not yet supported` (or equivalent), not silent acceptance.