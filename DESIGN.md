# `nt` — Design Decisions

## Purpose

A minimalist CLI memory aid for in-flight work. Tracks things you're waiting on (CI, replies, deployments) so you don't forget them. Explicitly **not** a planning tool, not a Jira-in-the-terminal, not a backlog organizer.

## Core model

- Every task has an alarm. No alarm, no task.
- A task without an upcoming alarm and not done is a contradiction.
- The tool only ever shows not-done tasks. History is not stored.

## Commands

| Command | Behavior |
|---|---|
| `nt <when> "<title>"` | Create task with alarm. |
| `nt <when> every <interval> "<title>"` | Same, with repeat policy until acked. |
| `nt` / `nt ls` | List not-done tasks (bare `nt` = `nt ls`). |
| `nt ls --overdue` / `--pending` / `--ackd` | Filter the list. Flags compose. |
| `nt ack <ref>` | Silence current alarm; task stays not-done. |
| `nt drop <ref>` | Remove the task (the only "completion" verb). |
| `nt note <ref> "<text>"` | Deferred to post-v1. |

## Alarms

- **Default repeat policy:** `once`. Fires once, then sits as "fired" until acked.
- **Repeat policy:** declared upfront via `every <interval>`. Re-fires at that cadence until acked.
- **Auto-dismiss:** never. Not for default tasks, not for ephemeral (ephemerals were dropped from v1).
- **Auto-snooze of ignored `once` alarms:** no. They sit visibly in the Overdue section; visibility is the nag.
- **Notification delivery:** OS-respecting (libnotify on Linux, Notification Center on macOS). No sound.
- **No background daemon in v1.** Staleness sweep runs as part of every `nt` invocation; no out-of-band reminders.

## Task lifecycle

- **States:** pending (alarm not yet fired), overdue (fired, not acked), acked (ackd, not dropped).
- **Stale:** subset of overdue; surfaced via ordering in the Overdue section (oldest first), not a separate state or flag for v1.
- **`done` vs `drop`:** merged into `drop` only. No semantic distinction, no history either way.
- **No auto-cleanup, ever.** Tasks only leave via explicit `drop`.

## Time syntax (v1)

Supports:
- **Interval:** `30m`, `2h`, `1d`, `3d`. No decimals.
- **Absolute time today:** `14:30`, `09:05` (24h, HH:MM).
- **Date + time:** `10 Apr 10:55` (day MonthName HH:MM).
- **Relative day keywords:** `tomorrow 9:00`, `monday 9:00`, `next monday 9:00`. Time component required — no bare `tomorrow` or bare weekday.

Excludes: am/pm (use 24h), bare weekday without time, vague relative phrases like "in a bit."

**Past absolute times error out** (e.g. `error: 14:30 is in the past (now 15:02)`). No rollover, no silent magic.

## `nt ls` output — three sections, in this order

1. **OVERDUE** — oldest first (most forgotten at top).
2. **PENDING** — soonest next-fire first.
3. **ACKED, NOT DONE** — most-recently-acked first.

Stale tasks appear in the OVERDUE section with an age marker. No ASCII tables — clean visual separators.

## Task references (IDs/resolution)

- **No numeric IDs.** Positional IDs were rejected (filter-dependent, cache-error-prone).
- **No ephemeral per-invocation numbering** (cache concerns).
- **No random adjective-noun names** (aesthetic objection).
- **4-char hex IDs,** lowercase, assigned at creation, collision-checked (re-draw), stable forever. Not reused after drop (no history, so reuse bookkeeping is moot).
- **Ref resolution order:**
  1. Ref matches hex ID regex `^[a-f0-9]{4}$` → look up by ID. Error if not found.
  2. Else exact substring match against titles. One match → apply. Multiple → interactive fuzzy menu (TTY) or error (non-interactive). Zero → error.
- **Interactive ref UX (TTY):** fuzzy-search inline highlight; tab lists candidates ranked by `nt ls` order; first enter selects top match; one-line output confirms what was acted on (`dropped 'PR review' [a3f2]`).
- **Non-interactive (pipe/script):** exact substring only; error on zero or multiple matches.
- **`nt drop` / `nt ack` with no args:** usage error to stderr, exit 2 (POSIX convention). No silent no-ops.

## Shelf completion

Every mutation command prints one line confirming what it did (which task, which ID). Brief, no prompt, just visible feedback so the user catches mistakes.

## Storage

- **Location:** `~/.config/nt/` (XDG-friendly, likely in dotfiles backups).
- **Format:** single text file. Specifics decided at implementation time.
- **No syncing in v1.** Single-machine.
- **No history.** `drop` is final from the tool's perspective.

## Filters confirmed

`--overdue` (fired, not acked), `--pending` (alarm not yet fired), `--ackd` (acked, not dropped). `--stale` dropped from v1 as redundant with Overdue ordering.

## Explicit non-goals (v1)

- Ephemeral tasks / auto-dismiss.
- Recurring/standing tasks (use cron / OS-level reminders).
- Notes/context attached to tasks (post-v1).
- Tags / contexts / projects / priorities / estimates.
- History view, logs, retrospectives.
- Sync across machines.
- Background daemon.
