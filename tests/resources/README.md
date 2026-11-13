# Real filesystem resources

This directory is reserved for the real-resource demonstration in
[../real_resources.py](../real_resources.py).

Run it from the repository root after installing the project:

```bash
python -m pip install -e ".[test]"
python tests/real_resources.py
```

Each invocation creates a new `run-<UTC timestamp>-<random id>/` directory.
The script never reuses or overwrites a previous run and deliberately retains
its generated files so that encrypted resources, restored resources, and
transaction journals can be inspected after execution.

The demonstration performs real filesystem mutations. Run it only in a
development checkout with sufficient free disk space. It does not operate on
personal files or directories outside this dedicated resource workspace.

The script uses assertions and emits a detailed trace for every successful
operation. A non-zero exit or failed assertion indicates a failed
demonstration; a successful run is evidence for the scenarios exercised, not
a substitute for an independent security audit or exhaustive platform test.
