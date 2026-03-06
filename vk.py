"""Compatibility wrapper for the old launcher name."""

from signal_app import main


if __name__ == "__main__":
    raise SystemExit(main())
