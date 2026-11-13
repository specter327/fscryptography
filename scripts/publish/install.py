#!/usr/bin/env python3
"""Install the published fscryptography distribution from PyPI."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [sys.executable, "-m", "pip", "install", "fscryptography"]
    print("Installing fscryptography from PyPI using:", sys.executable, flush=True)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
