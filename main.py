"""Compatibility wrapper for the command-line interface."""

from fiji_automated_analysis.cli import *  # noqa: F401,F403
from fiji_automated_analysis.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
