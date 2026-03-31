"""PyInstaller runtime hook: fix multiprocessing in frozen builds.

Prevents the 'No such option: -B' error that occurs when Python's
multiprocessing module tries to spawn workers using sys.executable
(which in a PyInstaller build points to the bootloader, not python).
"""
import multiprocessing
multiprocessing.set_start_method("fork", force=True)
