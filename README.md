# nt

A minimalist CLI memory aid for in-flight work. Tracks things you're waiting
on — CI runs, replies, deployments — so they don't fall off your radar between
context switches. Not a planning tool, not a backlog, not a Jira-in-the-terminal.

## Status

Pre-implementation. The Python v1 (`py/`) is being scaffolded; the Go rewrite
(`go/`) is a future placeholder. No functionality yet.

## See

- [`DESIGN.md`](DESIGN.md) — high-level design rationale.
- [`docs/cli-contract.md`](docs/cli-contract.md) — CLI surface, exit codes, output format.
- [`docs/daemon-protocol.md`](docs/daemon-protocol.md) — IPC between the CLI and the daemon.
- [`docs/storage-format.md`](docs/storage-format.md) — `tasks.json` schema and write rules.

These four files are the binding specs; both implementations must satisfy them
exactly. When code and a doc disagree, the doc wins.

## Quickstart (once scaffolded)

```
cd py && uv sync && uv run nt --version
pytest        # from repo root
```