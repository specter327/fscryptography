# Maintenance scripts

These scripts are optional convenience entry points. They use the Python
interpreter that launches them (sys.executable) and propagate the exit status
of the underlying command.

## Install the published package from PyPI

    python scripts/publish/install.py

This runs:

    python -m pip install fscryptography

## Upgrade the published package from PyPI

    python scripts/publish/update.py

This runs:

    python -m pip install --upgrade fscryptography

Run these commands in the virtual environment where the package should be
installed or upgraded. They do not create or activate a virtual environment.
The package must already have been published to PyPI for these commands to
succeed.

## Update a Git checkout

From the repository checkout:

    python scripts/update/github.py

Or specify another checkout:

    python scripts/update/github.py /path/to/fscryptography

The updater requires a Git working tree, a checked-out branch with an upstream,
and a clean working tree. It runs git pull --ff-only; it refuses to update
when local modifications or untracked files are present, when HEAD is detached,
or when no upstream is configured. It never stashes, resets, merges, or discards
local work.

## Selection

- Use publish/install.py for a fresh installation from PyPI.
- Use publish/update.py to upgrade the installed PyPI release.
- Use update/github.py to fast-forward a source checkout from its configured
  Git upstream.

The PyPI scripts and Git updater are independent; neither switches the other
installation method automatically.
