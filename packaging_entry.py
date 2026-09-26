"""PyInstaller entry point for the standalone command."""

import multiprocessing

from wuolah_wout_ads.cli import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
