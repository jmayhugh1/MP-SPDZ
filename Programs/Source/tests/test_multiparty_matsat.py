"""
Integration tests that directly exercise Programs/Source/matsat_utils.py.

These tests generate tiny MP-SPDZ programs that call
MatSatUtils.solve_matsat(...) directly, compile them, then run multi-party
execution with shamir-party.x.
"""

from __future__ import annotations

import threading
import time

import pytest
from testing_utilities import compile_and_run_matsat_utils_case

_TEST_LOCK = threading.Lock()


@pytest.fixture(autouse=True)
def _serialize_and_time_test(request):
    """
    Serialize tests in this module and print per-test runtime.
    """
    start = time.perf_counter()
    with _TEST_LOCK:
        yield
    elapsed = time.perf_counter() - start
    print(f"[timing] {request.node.name}: {elapsed:.2f}s")


@pytest.mark.integration
def test_matsat_utils_sat_example():
    """
    SAT: (x) AND (x) AND (x), with n=1.
    Q rows use [x, ~x] literal layout.
    """
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_sat_1var",
        q_rows=[[1, 0], [1, 0], [1, 0]],
        n=1,
        num_parties=3,
        port=5021,
    )
    assert is_solved == 1
    assert satisfied is not None
    assert satisfied >= 3.0


@pytest.mark.integration
def test_matsat_utils_unsat_example():
    """
    UNSAT: (x) AND (~x) AND (x), with n=1.
    At most 2 clauses can be satisfied simultaneously.
    """
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_unsat_1var",
        q_rows=[[1, 0], [0, 1], [1, 0]],
        n=1,
        num_parties=3,
        port=5022,
    )
    assert is_solved == 0
    if satisfied is not None:
        assert satisfied <= 2.0


@pytest.mark.integration
def test_matsat_utils_sat_two_var_example():
    """
    SAT over n=2:
      (x1) AND (x2) AND (x1)
    """
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_sat_2var",
        q_rows=[
            [1, 0, 0, 0],  # x1
            [0, 1, 0, 0],  # x2
            [1, 0, 0, 0],  # x1
        ],
        n=2,
        num_parties=3,
        port=5023,
    )
    assert is_solved == 1
    assert satisfied is not None
    assert satisfied >= 3.0


@pytest.mark.integration
def test_matsat_utils_unsat_two_var_conflict_example():
    """
    UNSAT over n=2:
      (x1) AND (~x1) AND (x2) AND (~x2)
    At most two clauses can be satisfied simultaneously.
    """
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_unsat_2var_conflict",
        q_rows=[
            [1, 0, 0, 0],  # x1
            [0, 0, 1, 0],  # ~x1
            [0, 1, 0, 0],  # x2
            [0, 0, 0, 1],  # ~x2
        ],
        n=2,
        num_parties=3,
        port=5024,
    )
    assert is_solved == 0
    if satisfied is not None:
        assert satisfied <= 2.0


@pytest.mark.integration
def test_matsat_utils_sat_example_custom_solver_params():
    """
    SAT case with custom solve_matsat() parameters to ensure test harness knobs work.
    """
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_sat_custom_params",
        q_rows=[[1, 0], [1, 0], [1, 0]],
        n=1,
        num_parties=3,
        port=5025,
        l_value=1.5,
        beta_value=0.4,
        max_try=3,
        max_itr=10,
        print_results=True,
        weighted=False,
    )
    assert is_solved == 1
    assert satisfied is not None


@pytest.mark.integration
def test_matsat_utils_sat_uniqueish_n3():
    """
    SAT, coupled constraints (n=3), intended near-unique assignment:
    x0=0, x1=0, x2=1.
    """
    q_rows = [
        [1, 1, 1, 0, 0, 0],  # (x0 ∨ x1 ∨ x2)
        [0, 0, 0, 1, 1, 0],  # (¬x0 ∨ ¬x1)
        [0, 0, 0, 1, 0, 1],  # (¬x0 ∨ ¬x2)
        [0, 0, 0, 0, 1, 1],  # (¬x1 ∨ ¬x2)
        [0, 1, 0, 1, 0, 0],  # (¬x0 ∨ x1)
        [0, 0, 1, 0, 1, 0],  # (¬x1 ∨ x2)
    ]
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_sat_uniqueish_n3",
        q_rows=q_rows,
        n=3,
        num_parties=3,
        port=5026,
    )
    assert is_solved == 1
    assert satisfied is not None
    assert satisfied >= float(len(q_rows))


@pytest.mark.integration
def test_matsat_utils_unsat_equiv_chain_xor_n3():
    """
    UNSAT, equivalence chain + XOR contradiction (n=3).
    """
    q_rows = [
        [0, 1, 0, 1, 0, 0],  # ¬x0 ∨ x1
        [1, 0, 0, 0, 1, 0],  # x0 ∨ ¬x1
        [0, 0, 1, 0, 1, 0],  # ¬x1 ∨ x2
        [0, 1, 0, 0, 0, 1],  # x1 ∨ ¬x2
        [1, 0, 1, 0, 0, 0],  # x0 ∨ x2
        [0, 0, 0, 1, 0, 1],  # ¬x0 ∨ ¬x2
    ]
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_unsat_equiv_chain_xor_n3",
        q_rows=q_rows,
        n=3,
        num_parties=3,
        port=5027,
    )
    assert is_solved == 0
    if satisfied is not None:
        assert satisfied < float(len(q_rows))


@pytest.mark.integration
def test_matsat_utils_unsat_php_3_into_2_n6():
    """
    UNSAT pigeonhole principle: 3 pigeons into 2 holes (n=6).
    """
    q_rows = [
        [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # p0 in some hole
        [0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],  # p1 in some hole
        [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0],  # p2 in some hole
        [0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0],  # ¬p0h0 ∨ ¬p1h0
        [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],  # ¬p0h0 ∨ ¬p2h0
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0],  # ¬p1h0 ∨ ¬p2h0
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0],  # ¬p0h1 ∨ ¬p1h1
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],  # ¬p0h1 ∨ ¬p2h1
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],  # ¬p1h1 ∨ ¬p2h1
    ]
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_unsat_php_3_into_2_n6",
        q_rows=q_rows,
        n=6,
        num_parties=3,
        port=5028,
    )
    assert is_solved == 0
    if satisfied is not None:
        assert satisfied < float(len(q_rows))


@pytest.mark.integration
def test_matsat_utils_sat_implication_cycle_pin_n4():
    """
    SAT implication cycle with pin (x0) forcing all true (n=4).
    """
    q_rows = [
        [0, 1, 0, 0, 1, 0, 0, 0],  # ¬x0 ∨ x1
        [0, 0, 1, 0, 0, 1, 0, 0],  # ¬x1 ∨ x2
        [0, 0, 0, 1, 0, 0, 1, 0],  # ¬x2 ∨ x3
        [1, 0, 0, 0, 0, 0, 0, 1],  # ¬x3 ∨ x0
        [1, 0, 0, 0, 0, 0, 0, 0],  # x0
    ]
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_sat_implication_cycle_pin_n4",
        q_rows=q_rows,
        n=4,
        num_parties=3,
        port=5029,
    )
    assert is_solved == 1
    assert satisfied is not None
    assert satisfied >= float(len(q_rows))


@pytest.mark.integration
def test_matsat_utils_unsat_competing_cardinality_n4():
    """
    UNSAT with competing global cardinality constraints (n=4).
    """
    q_rows = [
        [1, 1, 1, 1, 0, 0, 0, 0],  # x0∨x1∨x2∨x3
        [0, 0, 0, 0, 1, 1, 0, 0],  # ¬x0∨¬x1
        [0, 0, 0, 0, 1, 0, 1, 0],  # ¬x0∨¬x2
        [0, 0, 0, 0, 1, 0, 0, 1],  # ¬x0∨¬x3
        [0, 0, 0, 0, 0, 1, 1, 0],  # ¬x1∨¬x2
        [0, 0, 0, 0, 0, 1, 0, 1],  # ¬x1∨¬x3
        [0, 0, 0, 0, 0, 0, 1, 1],  # ¬x2∨¬x3
        [1, 1, 0, 0, 0, 0, 0, 0],  # x0∨x1
        [0, 0, 1, 1, 0, 0, 0, 0],  # x2∨x3
        [1, 0, 1, 0, 0, 0, 0, 0],  # x0∨x2
    ]
    is_solved, satisfied = compile_and_run_matsat_utils_case(
        program_name="test_matsat_utils_unsat_competing_cardinality_n4",
        q_rows=q_rows,
        n=4,
        num_parties=3,
        port=5030,
    )
    assert is_solved == 0
    if satisfied is not None:
        assert satisfied < float(len(q_rows))
