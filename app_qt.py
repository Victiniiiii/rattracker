"""Qt desktop entry point.

Default: start the GUI. With ``--backend``: run the tracker pipeline, used by
the GUI to spawn itself without shipping a second executable.
"""

import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        from ui.version import read_version
        print(read_version())
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--backend":
        del sys.argv[1]
        from tracker.pipeline import main as pipeline_main
        pipeline_main()
        return 0
    from ui.app import main as app_main
    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
