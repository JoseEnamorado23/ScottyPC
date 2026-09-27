"""Punto de entrada: ``python -m pcapp_servidor --datos <carpeta>``.

``freeze_support()`` va primero: en un ejecutable de PyInstaller en Windows,
los procesos de trabajo de PC vuelven a lanzar este ejecutable.
"""

import multiprocessing


def _principal() -> None:
    multiprocessing.freeze_support()
    from pcapp_servidor.arranque import main

    raise SystemExit(main())


if __name__ == "__main__":
    _principal()
