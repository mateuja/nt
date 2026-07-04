# AGENTS.md

This repo is in the **pre-implementation planner state**: only `DESIGN.md` and `docs/` exist; no `py/`, `go/`, or `tests/` yet. Implementation is planned in `.github/prompts/initial-commit.md` and `docs/scaffold.md` (those prompts are gitignored, not part of the tracked repo).

## Source of truth

- `docs/cli-contract.md`, `docs/daemon-protocol.md`, `docs/storage-format.md` are **binding contracts**. Both the Python (v1) and Go (future) implementations must satisfy them exactly. When code and a doc disagree, the doc wins; fix the code.
- `DESIGN.md` is the high-level rationale. The `docs/*.md` specs are more precise where they overlap — prefer the specs.

## Intended layout

```
py/      Python v1 (uv-managed, src/ layout, package `nt`)
go/      future Go rewrite (empty for now)
tests/   root, black-box CLI tests (pytest, subprocess-driven)
docs/    binding contracts
```

Module responsibilities are fixed by `docs/scaffold.md` (`cli.py`, `timeparse.py`, `storage.py`, `daemon.py`, `notify.py`, `protocol.py`, `display.py`, `fuzzy.py`). Don't invent different splits.

## Developer commands (once scaffolded)

```
cd py && uv sync && uv run nt --version   # install + run dev binary
pytest                                     # from repo root; NT_BIN defaults to uv run --project py/ nt
NT_BIN=./go/bin/nt pytest                  # same tests against the Go binary later
```

- Python target: **3.13**. Build backend: hatchling.
- **Strict stdlib only.** No `click`, `prompt-toolkit`, `rich`, etc. Every external dep is one more thing to re-port to Go.
- `py/tests/` holds Python-internal unit tests (throwaway post-migration). Root `tests/` is implementation-agnostic and must survive unchanged against either binary.

## Black-box test rules (root `tests/`)

- Tests invoke the `nt` binary via `subprocess.run`; never `import` Python code.
- `conftest.py` provides `nt_bin` (resolves `$NT_BIN` → `uv run --project py/ nt`) and `tmp_home` (sets `HOME` and `XDG_CONFIG_HOME` to a temp dir per test).
- Assert on exit code, stdout, stderr, and `tasks.json` contents. No direct module imports.

## Hard constraints from the contracts

- **Exit codes:** `0` success, `1` runtime error, `2` usage error (POSIX). Missing required arg for `ack`/`drop` → exit 2, never a silent no-op.
- **Times:** stored/transmitted as ISO 8601 **UTC** with `Z`. The CLI does all local→UTC and UTC→local conversion; the daemon is stateless about wall-clock display time (the CLI sends `now` in `list` requests).
- **Storage:** `~/.config/nt/tasks.json` (or `$XDG_CONFIG_HOME/nt/`), permissions `0600`, atomic writes (temp file + `rename`, never in place). The daemon is the **only** writer; concurrent CLI requests are serialized by the daemon's accept loop, so no file locking.
- **Task IDs:** 4 lowercase hex chars (`^[a-f0-9]{4}$`), collision-checked at creation (re-draw on collision), stable forever, not reused after drop.
- **State:** `pending` | `overdue` | `ackd`. Stored explicitly, not derived.
- **No history.** `drop` removes the task outright — no tombstone, no logs.
- **Ref resolution order:** (1) exact 4-hex-ID match → lookup, error `not_found` if missing; (2) case-sensitive substring match against titles → one match acts, multiple → TTY fuzzy menu / non-TTY `ambiguous` error, zero → `not_found`.
- **Time syntax** is fixed and narrow: `30m`/`2h`/`1d` intervals, `HH:MM` (24h), `D Mon HH:MM`, `tomorrow HH:MM`, `weekday HH:MM`, `next weekday HH:MM`. No am/pm, no bare weekday/tomorrow, no combined intervals (`1h30m`), no natural language. Past absolute times exit 1 (no rollover).
- **Reserved flags** (`--json`, `--yes`/`-y`, `--verbose`/`-v`, `--config`, `--non-interactive`/`-n`): if encountered in v1, exit 2 with `error: <flag> is not yet supported` — never silent acceptance.
- **Daemon lazy-start:** every CLI invocation connects to `~/.config/nt/daemon.sock`; on failure it cleans the stale socket, spawns the daemon detached, polls up to 2 s. Even bare `nt ls` goes through the socket; no in-process daemon path.

## Gotchas

- `.github/prompts/` is gitignored — those plans are conveniences, not tracked. Don't treat them as authoritative contracts; the tracked `docs/` are.
- The daemon re-arms all timers from `tasks.json` on startup (recovery after downtime/crash). In-memory state is reconstructable from the file — never assume a separate daemon-state file.
- `ack` of a repeating task re-arms the next reminder `repeat_interval_secs` from now; the confirmation line does **not** mention this separately.
- Empty `nt ls` sections are **omitted entirely** (no header printed). If all sections empty, print exactly `no active tasks.`.

## Planning artifacts

When you produce a multi-step plan or work breakdown for this repo, save it as
`.github/prompts/<feature>.md` (see the existing `initial-commit.md` and
`scaffold.md` for format). The directory is gitignored on purpose — plans are
conveniences, not tracked contracts.