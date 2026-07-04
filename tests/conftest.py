import os
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_nt_bin() -> list[str]:
    env = os.environ.get("NT_BIN")
    if env:
        return env.split()
    return ["uv", "run", "--project", str(REPO_ROOT / "py"), "nt"]


@pytest.fixture
def nt_bin() -> list[str]:
    return _resolve_nt_bin()


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    xdg_config = home / ".config"
    xdg_config.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    yield home
    shutil.rmtree(home, ignore_errors=True)
