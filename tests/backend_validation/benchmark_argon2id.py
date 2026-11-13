#!/usr/bin/env python3
"""Reproducible, opt-in Argon2id performance benchmark for fscryptography.

This is a development tool, not production key-management code. It uses a
fixed, non-secret benchmark password and salt and never writes derived keys.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError, version
from threading import Barrier
from typing import Any

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw

BENCHMARK_PASSWORD = b"fscryptography-argon2id-benchmark-only"
BENCHMARK_SALT = bytes.fromhex("8f4c2a1d9b7e6035a1c8d4f0276be951")
OUTPUT_KEY_LENGTH = 32


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def percentile(values: list[float], percentile_value: float) -> float:
    """Nearest-rank percentile, returned in seconds."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile_value * len(ordered)) - 1)]


def derive(memory_cost: int, time_cost: int, parallelism: int) -> bytes:
    return hash_secret_raw(
        secret=BENCHMARK_PASSWORD,
        salt=BENCHMARK_SALT,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=OUTPUT_KEY_LENGTH,
        type=Type.ID,
        version=ARGON2_VERSION,
    )


def run_batch(
    workers: int, memory_cost: int, time_cost: int, parallelism: int
) -> tuple[list[float], float]:
    """Run one synchronized batch and return per-call and wall-clock times."""
    barrier = Barrier(workers)

    def task() -> float:
        barrier.wait()
        started = time.perf_counter()
        result = derive(memory_cost, time_cost, parallelism)
        elapsed = time.perf_counter() - started
        if len(result) != OUTPUT_KEY_LENGTH:
            raise RuntimeError("Argon2id returned an unexpected output length")
        return elapsed

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(task) for _ in range(workers)]
        durations = [future.result() for future in futures]
    return durations, time.perf_counter() - started


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    estimated_mib = args.memory_cost_kib / 1024 * max(args.concurrency)
    if estimated_mib > args.max_memory_mib:
        raise SystemExit(
            "Refusing benchmark: estimated Argon2 memory for the highest "
            f"concurrency is {estimated_mib:.1f} MiB, above the configured "
            f"budget of {args.max_memory_mib:.1f} MiB. Reduce --concurrency "
            "or explicitly raise --max-memory-mib after checking available RAM."
        )

    if args.memory_cost_kib == 65536 and args.time_cost == 3 and args.parallelism == 1:
        profile_label = "proposed-production-profile"
    else:
        profile_label = "custom-profile-not-production"

    # Warm-up is performed at concurrency 1 and is excluded from statistics.
    for _ in range(args.warmup):
        derive(args.memory_cost_kib, args.time_cost, args.parallelism)

    measurements: list[dict[str, Any]] = []
    for workers in args.concurrency:
        per_call_seconds: list[float] = []
        batch_wall_seconds: list[float] = []
        for _ in range(args.iterations):
            durations, wall = run_batch(
                workers,
                args.memory_cost_kib,
                args.time_cost,
                args.parallelism,
            )
            per_call_seconds.extend(durations)
            batch_wall_seconds.append(wall)

        measurements.append(
            {
                "concurrency": workers,
                "batches": args.iterations,
                "calls": len(per_call_seconds),
                "per_call_seconds": {
                    "median": statistics.median(per_call_seconds),
                    "p95": percentile(per_call_seconds, 0.95),
                    "min": min(per_call_seconds),
                    "max": max(per_call_seconds),
                },
                "batch_wall_seconds": {
                    "median": statistics.median(batch_wall_seconds),
                    "p95": percentile(batch_wall_seconds, 0.95),
                },
            }
        )

    return {
        "benchmark": "fscryptography-argon2id",
        "profile_label": profile_label,
        "argon2id": {
            "version": ARGON2_VERSION,
            "memory_cost_kib": args.memory_cost_kib,
            "time_cost": args.time_cost,
            "parallelism": args.parallelism,
            "output_length_bytes": OUTPUT_KEY_LENGTH,
            "salt_length_bytes": len(BENCHMARK_SALT),
        },
        "execution": {
            "warmup_calls": args.warmup,
            "iterations_per_concurrency": args.iterations,
            "concurrency_levels": args.concurrency,
            "estimated_argon2_memory_mib_at_max_concurrency": estimated_mib,
            "configured_memory_budget_mib": args.max_memory_mib,
            "measurement": "perf_counter; per-call latency and synchronized batch wall time",
        },
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "logical_cpu_count": os.cpu_count(),
            "argon2_cffi": package_version("argon2-cffi"),
        },
        "results": measurements,
        "limitations": [
            "The memory estimate is Argon2's configured working memory multiplied by concurrency; it excludes process and library overhead.",
            "No portable per-run peak-RSS measurement is claimed.",
            "Results depend on thermal state, power mode, background load, and memory bandwidth.",
            "The fixed password and salt are benchmark-only and must never be reused for production key derivation.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Argon2id latency and controlled concurrent throughput."
    )
    parser.add_argument("--memory-cost-kib", type=int, default=65536)
    parser.add_argument("--time-cost", type=int, default=3)
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument(
        "--concurrency",
        type=int,
        nargs="+",
        default=[1, 2],
        help="Concurrent derivations per batch (default: 1 2).",
    )
    parser.add_argument(
        "--max-memory-mib",
        type=float,
        default=256.0,
        help="Explicit budget for estimated Argon2 working memory (default: 256 MiB).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional path to write the complete JSON report.",
    )
    args = parser.parse_args()

    if args.memory_cost_kib < 8 or args.time_cost < 1 or args.parallelism < 1:
        parser.error("Argon2 parameters must be positive (memory_cost_kib >= 8).")
    if args.iterations < 1 or args.warmup < 0:
        parser.error("--iterations must be >= 1 and --warmup must be >= 0.")
    if not args.concurrency or any(value < 1 for value in args.concurrency):
        parser.error("Every --concurrency value must be >= 1.")
    if len(set(args.concurrency)) != len(args.concurrency):
        parser.error("--concurrency values must be unique.")
    if args.max_memory_mib <= 0:
        parser.error("--max-memory-mib must be > 0.")
    return args


def main() -> int:
    args = parse_args()
    report = run_benchmark(args)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
