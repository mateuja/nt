# py/

Python v1 implementation of `nt`, managed with [`uv`](https://docs.astral.sh/uv/).

## Run the dev version

```
uv sync
uv run nt --version
```

`uv` auto-fetches a standalone CPython 3.14 interpreter on first `uv sync`, so
no system Python install is required.

## Tests

Black-box CLI tests live at the repo root in `tests/` and invoke the `nt`
binary via subprocess. From the repo root:

```
pytest        # uses `uv run --project py/ nt` as the binary
```

Unit tests for Python internals (throwaway post-migration) will live in
`py/tests/` alongside the modules they test, added as each module is
implemented.
