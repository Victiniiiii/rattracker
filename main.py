#!/usr/bin/env python3
"""Entry point for the tracker.

Kept at the repository root so it can be compiled by Nuitka and run directly:

    python main.py --video input/1.mp4
    python -m tracker --video input/1.mp4
"""

from tracker.pipeline import main

if __name__ == "__main__":
    main()
