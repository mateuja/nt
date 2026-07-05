# `nt` — Design Decisions

## Purpose

A minimalist CLI memory aid for in-flight work. Tracks things you're waiting on (CI, replies, deployments) so you don't forget them. Explicitly **not** a planning tool, not a Jira-in-the-terminal, not a backlog organizer.

## Core model

- Every task has a cadence and re-arms after every fire. No cadence, no task.
- A task lingers only between fires; there is no "acked" state in which a task sits silently until the user notices. Once you no longer need it, `drop` is the only exit.
- The tool only ever shows active tasks. History is not stored.

## Commands

| Command | Behavior |
|---|---|
| `nt <when> ["every <interval>"] "<title>"` | Create task. Cadence defaults to 1h if `every` omitted. |
| `nt` / `nt ls` | List active tasks, soonest-fire first (bare `nt` = `nt ls`). |
| `nt defer <ref> <when> ["every <interval>"]` | Reschedule (and optionally re-cadence) a task. The only way to silence a fired alarm short of `drop`. |
| `nt drop <ref>` | Remove the task (the only "completion" verb). |
| `nt note <ref> "<text>"` | Deferred to post-v1. |

## Alarms

- **Every task has a cadence.** The alarm fires at the scheduled time, the daemon re-arms `next_fire_at = now + cadence_secs`, and the task continues until the user `drop`s it. There is no `once` policy.
- **Default cadence:** 1h for v1. `every <interval>` overrides it per-task at creation or via `defer`.
- **Auto-dismiss:** never. Not for default-cadence tasks, not for any cadence.
- **No `ackd` state, no auto-snooze, no `[STALE]` marker.** The list is a forward-looking schedule sorted by `next_fire_at`; a task can no more "sit forgotten" than it can sit acked — it is either re-arming on its cadence or it has been dropped. The tool cannot become a backlog by construction.
- **Notification delivery:** OS-respecting (libnotify on Linux, Notification Center on macOS). No sound.
- **Lazy-start daemon.** Every CLI invocation talks to `~/.config/nt/daemon.sock` (spawning the daemon detached on first miss). The daemon owns all timers and writes. See `docs/daemon-protocol.md`.

## Task lifecycle

- **No stored state.** A task has `next_fire_at` and `cadence_secs`; the rest is derived. `nt ls` sorts by `next_fire_at` ascending, which is all the urgency signal the tool needs.
- **`done` vs `drop`:** merged into `drop` only. No semantic distinction, no history either way.
- **No auto-cleanup, ever.** Tasks only leave via explicit `drop` — and this rule is now enforced by construction: there is no state in which an un-dropped task can linger silently, so nothing can accumulate.

## Time syntax (v1)

Supports:
- **Interval:** `30m`, `2h`, `1d`, `3d`. No decimals.
- **Absolute time today:** `14:30`, `09:05` (24h, HH:MM).
- **Date + time:** `10 Apr 10:55` (day MonthName HH:MM).
- **Relative day keywords:** `tomorrow 9:00`, `monday 9:00`, `next monday 9:00`. Time component required — no bare `tomorrow` or bare weekday.

Excludes: am/pm (use 24h), bare weekday without time, vague relative phrases like "in a bit."

**Past absolute times error out** (e.g. `error: 14:30 is in the past (now 15:02)`). No rollover, no silent magic.

## `nt ls` output — a single sorted list

Sorted by `next_fire_at` ascending. Soonest-fire first; the most urgent task is at the top by virtue of position, not a stored state. No section headers, no `[STALE]` marker, no ASCII tables — clean visual separators between rows only.

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
- **`nt drop` / `nt defer` with no args:** usage error to stderr, exit 2 (POSIX convention). No silent no-ops.

## Shelf completion

Every mutation command prints one line confirming what it did (which task, which ID). Brief, no prompt, just visible feedback so the user catches mistakes.

## Storage

- **Location:** `~/.config/nt/` (XDG-friendly, likely in dotfiles backups).
- **Format:** single text file. Specifics decided at implementation time.
- **No syncing in v1.** Single-machine.
- **No history.** `drop` is final from the tool's perspective.

## Filters

There are no filter flags in v1. The `nt ls` listing is a single sorted list; selection-by-state is meaninglesssince there is no stored state to select on. `--overdue` / `--pending` / `--ackd` (and the v0 `--stale` idea) are all dropped along with the state model they were predicated on.

## Explicit non-goals (v1)

- Ephemeral tasks / auto-dismiss.
- Configurability of the default cadence (`--config` reserved; post-v1).
- Notes/context attached to tasks (post-v1).
- Tags / contexts / projects / priorities / estimates.
- History view, logs, retrospectives.
- Sync across machines.
