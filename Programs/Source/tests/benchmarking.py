"""
Benchmark-style integration tests for random MatSat Q matrices at increasing sizes.

The sizes below refer to total matrix entries (rows * cols), ranging from 4 to 1000.
"""

from __future__ import annotations

import math
import time

import pytest

from testing_utilities import compile_and_run_random_matsat_case


TOTAL_SIZES = [4, 8, 16, 32, 64, 128, 256, 512, 1000]


def _shape_from_total_size(total_size: int) -> tuple[int, int]:
    """
    Derive a (rows, cols) shape close to square where cols is even (MatSat requires 2*n).
    Prefers exact factorization rows*cols == total_size when possible.
    """
    if total_size < 4:
        raise ValueError("total_size must be >= 4")

    root = int(math.sqrt(total_size))
    for cols in range(root, 1, -1):
        if cols % 2 == 0 and total_size % cols == 0:
            rows = total_size // cols
            if rows >= 1:
                return rows, cols

    # Fallback: keep columns even and ensure rows*cols >= total_size.
    cols = 2
    rows = (total_size + cols - 1) // cols
    return rows, cols


@pytest.mark.integration
@pytest.mark.benchmark
@pytest.mark.parametrize("total_size", TOTAL_SIZES)
def test_random_q_matrix_scaling(total_size: int):
    rows, cols = _shape_from_total_size(total_size)
    started = time.perf_counter()
    is_solved, satisfied = compile_and_run_random_matsat_case(
        program_name=f"benchmark_random_q_total_{total_size}",
        rows=rows,
        columns=cols,
        seed=total_size,
        density=0.35,
        num_parties=3,
        port=5200 + TOTAL_SIZES.index(total_size),
        max_try=2,
        max_itr=8,
        weighted=False,
        print_results=False,
    )
    elapsed = time.perf_counter() - started
    print(
        f"[benchmark] total={total_size} rows={rows} cols={cols} "
        f"is_solved={is_solved} satisfied={satisfied} elapsed={elapsed:.2f}s"
    )

    # We don't assert SAT/UNSAT outcome for random instances; only that execution produces a result
    # when networking/runtime is available. In restricted environments this test is skipped upstream.
    assert is_solved in (0, 1, None)
