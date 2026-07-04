import sys
from nt import __version__


def main() -> int:
    argv = sys.argv[1:]
    if argv in (["--version"], ["-V"]):
        sys.stdout.write(f"nt {__version__}\n")
        return 0
    sys.stderr.write("not implemented yet\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
