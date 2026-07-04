import subprocess


def test_version(nt_bin: list[str], tmp_home) -> None:
    result = subprocess.run(
        [*nt_bin, "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "nt 0.1.0"
    assert result.stderr == ""
