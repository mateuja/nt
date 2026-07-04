# AGENTS.md

This repo is in the **pre-implementation planner state**: the scaffold is in place (`py/`, `go/`, `tests/`) but no business logic is implemented yet — see `docs/` for the binding contracts each feature must satisfy.

## Source of truth

- `docs/cli-contract.md`, `docs/daemon-protocol.md`, `docs/storage-format.md` are **binding contracts**. Both the Python (v1) and Go (future) implementations must satisfy them exactly. When code and a doc disagree, the doc wins; fix the code.
- `DESIGN.md` is the high-level rationale. The `docs/*.md` specs are more precise where they overlap — prefer the specs.

## Pull requests and merging

- **Never merge a PR while any required CI check is failing, pending, or missing.** This is non-negotiable, even if the failure looks flaky or unrelated. Investigate and fix, or wait for the run to finish.
- **Agents never run the merge command.** `gh pr merge` (squash) is run by the user manually. When a PR is ready and all required checks are green, print the exact command for the user and stop — do not execute it.
- The `--admin` override on `gh pr merge` exists for human-only emergencies (e.g. bootstrapping the CI pipeline itself). Agents must never use `--admin`; suggest it to the user only if they explicitly ask how to bypass a protection rule.
- `main` is protected: required status checks are `CI / Build`, `CI / Lint & typecheck`, `CI / Test (ubuntu-latest, py)`, `CI / Test (ubuntu-latest, go)`, `CI / Test (macos-latest, py)`, and `CI / Test (macos-latest, go)` (`strict`, so the PR head must be up to date with `main`), and linear history is required (squash or rebase merges only). Never force-push to `main` or delete it. The `CI / Unit tests (linux)` job is informational (non-required) for now; promote it to required once `py/tests/` and Go unit tests are meaningful.

## Intended layout

```
py/      Python v1 (uv-managed, src/ layout, package `nt`)
go/      Go rewrite (main package at go/, builds to go/bin/nt; satisfies the same docs/ contracts)
tests/   root, black-box CLI tests (pytest, subprocess-driven)
docs/    binding contracts
```

Module responsibilities are fixed: `cli.py` (entry surface — arg parsing, time-parse calls, socket requests, output rendering), `timeparse.py` (pure time-string → UTC, no I/O), `storage.py` (atomic `tasks.json` read/write), `daemon.py` (socket server, in-memory timers, state transitions), `notify.py` (OS notification backends), `protocol.py` (request/response envelopes, no I/O), `display.py` (renders `nt ls` from daemon responses), `fuzzy.py` (TTY ref disambiguation menu — the only module that touches the terminal). Don't invent different splits.

## Developer commands (once scaffolded)

```
cd py && uv sync && uv run nt --version   # install + run dev binary
pytest                                     # from repo root; NT_BIN defaults to uv run --project py/ nt
NT_BIN=./go/bin/nt pytest                  # same tests against the Go binary later
```

```
go -C go build -o bin/nt .                 # build the Go binary to go/bin/nt
NT_BIN=./go/bin/nt uv run --project py/ pytest tests -q   # black-box suite against the Go binary
go -C go test ./...                        # Go unit tests (linux-only in CI)
```

- Python target: **3.14**. Build backend: hatchling.
- **Strict stdlib only.** No `click`, `prompt-toolkit`, `rich`, etc. Every external dep is one more thing to re-port to Go. (Dev tooling — ruff, ty, pre-commit — does not count; it never ships.)
- `py/tests/` holds Python-internal unit tests (throwaway post-migration). Root `tests/` is implementation-agnostic and must survive unchanged against either binary.
- **Dual-binary invariant:** the same root `tests/` suite must pass against **both** the Python and Go binaries on **every matrix OS** (ubuntu-latest and macos-latest). This is enforced by the CI `test` job's `os × binary` matrix. Python and Go unit tests run linux-only in the informational `CI / Unit tests (linux)` job. If the Go binary diverges from a contract, a black-box test fails — that is the intended regression gate, not a bug to work around.

## Tooling commands

Dev tooling lives in the `dev` dependency group of `py/pyproject.toml`; versions are pinned via `py/uv.lock`. Pre-commit hooks (`.pre-commit-config.yaml`) and the CI `lint` job both run from this same environment, so they never drift apart. Run these from the repo root:

```
cd py && uv sync && uv run pre-commit install   # one-time: enable git hooks
uv run --project py/ ruff check                 # lint
uv run --project py/ ruff format                # auto-format
uv run --project py/ ty check --project py .   # typecheck py/ + tests/ (hard CI gate)
uv run --project py/ pre-commit run --all-files # ruff + format + ty + golangci-lint + hygiene, exactly as CI
uv run --project py/ pytest tests -q            # black-box CLI suite (same command CI runs)
go -C go build -o bin/nt .                       # build the Go binary
NT_BIN=./go/bin/nt uv run --project py/ pytest tests -q   # black-box suite against the Go binary
golangci-lint run --config=go/.golangci.yml .   # Go lint (run from go/, or `cd go && golangci-lint run`); config shared with pre-commit/CI
```

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

- The daemon re-arms all timers from `tasks.json` on startup (recovery after downtime/crash). In-memory state is reconstructable from the file — never assume a separate daemon-state file.
- `ack` of a repeating task re-arms the next reminder `repeat_interval_secs` from now; the confirmation line does **not** mention this separately.
- Empty `nt ls` sections are **omitted entirely** (no header printed). If all sections empty, print exactly `no active tasks.`.
