"""PyInstaller entry point for the desktop application."""

import multiprocessing

from wuolah_wout_ads.gui import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
