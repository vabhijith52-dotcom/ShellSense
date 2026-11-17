"""ShellSense entry point."""

import sys

from shellsense.cli import main as cli_main
from shellsense.gui.launcher import launch_desktop


def main() -> None:
    """Entry point for the ShellSense application."""
    if len(sys.argv) > 1:
        cli_main()
    else:
        launch_desktop()


if __name__ == "__main__":
    main()
