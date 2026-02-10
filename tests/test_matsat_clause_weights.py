"""
Tests for solve_matsat with varying clause weights.

This module tests the MatSat solver with different clause weight configurations
for 2-3 party scenarios where each party provides one clause.

Run with: uv run pytest tests/test_matsat_clause_weights.py -v -s
"""

import pytest
import subprocess
import tempfile
import sys
from pathlib import Path

# Add the MP-SPDZ directory to the path
mp_spdz_root = Path(__file__).parent.parent
sys.path.insert(0, str(mp_spdz_root))


def compile_and_run_mpc(test_name, clauses, n, m, weights, description):
    """
    Compile and run an MPC program for a specific test case.
    
    Args:
        test_name: Name for the test program
        clauses: List of clauses for the SAT formula
        n: Number of variables
        m: Number of clauses
        weights: List of clause weights
        description: Human-readable description of the test
        
    Returns:
        Tuple of (is_solved, satisfied_clauses) from the MPC execution
    """
    # Create the MPC program content
    mpc_content = f'''"""
{description}
"""
from Compiler.types import sint, sfix, Matrix
from Compiler.library import print_ln, for_range
from Programs.Source.matsat_utils import MatSatUtils

def create_q_matrix(clauses, n, m):
    Q = Matrix(m, 2 * n, sfix)
    
    @for_range(m)
    def _(i):
        @for_range(2 * n)
        def __(j):
            Q[i][j] = sfix(0)
    
    for i, clause in enumerate(clauses):
        for literal in clause:
            if literal > 0:
                Q[i][literal - 1] = sfix(1)
            else:
                Q[i][n + abs(literal) - 1] = sfix(1)
    
    return Q

def create_weight_vector(m, weights):
    w = Matrix(m, 1, sfix)
    for i in range(m):
        w[i][0] = sfix(weights[i])
    return w

# Test parameters
n = {n}
m = {m}
clauses = {clauses}
weights = {weights}

print_ln("=" * 60)
print_ln("{description}")
print_ln("=" * 60)

Q = create_q_matrix(clauses, n, m)
active = create_weight_vector(m, weights)

u_tilde, u, is_solved, satisfied_clauses = MatSatUtils.solve_matsat(
    Q=Q, n=n, m=m, active=active, l=2.0, max_try=5, max_itr=10, weighted=True, print_results=True
)

print_ln("Test completed successfully")
'''
    
    # Write the MPC program to a temporary file
    mpc_file = mp_spdz_root / "Programs" / "Source" / f"{test_name}.mpc"
    with open(mpc_file, 'w') as f:
        f.write(mpc_content)
    
    try:
        # Compile the MPC program
        print(f"\n  Compiling {test_name}...")
        compile_result = subprocess.run(
            ["python3", "compile.py", test_name],
            cwd=mp_spdz_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if compile_result.returncode != 0:
            print(f"  Compilation failed:")
            print(compile_result.stderr)
            pytest.fail(f"Failed to compile {test_name}")
        
        print(f"  Compilation successful")
        
        # Use a unique port for this test to avoid conflicts
        import random
        import time
        
        # Kill any leftover processes from previous runs
        subprocess.run(["pkill", "-f", f"mascot-party.x.*{test_name}"], capture_output=True)
        time.sleep(0.5)  # Give processes time to die
        
        # Run the MPC program with m parties (one per clause)
        print(f"  Running {test_name} with {m} parties...")
        
        # Start all m parties in the background
        parties = []
        for party_id in range(m):
            party_process = subprocess.Popen(
                ["./mascot-party.x", "-N", str(m), "-p", str(party_id), "-h", "localhost", test_name],
                cwd=mp_spdz_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            parties.append(party_process)
            time.sleep(0.1)  # Small delay between starting parties
        
        # Wait for all parties to complete
        outputs = []
        errors = []
        for i, party in enumerate(parties):
            stdout, stderr = party.communicate()
            outputs.append(stdout)
            errors.append(stderr)
        
        # Check if any party failed
        failed = False
        for i, party in enumerate(parties):
            if party.returncode != 0:
                print(f"  Party {i} failed with return code {party.returncode}\"")
                print(f"  Party {i} stderr: {errors[i]}")
                failed = True
        
        if failed:
            pytest.fail(f"Failed to run {test_name}")
        
        # Print the output from party 0 (they should all have the same output)
        print(f"  Output from party 0:")
        for line in outputs[0].split('\n'):
            if line.strip():
                print(f"    {line}")
        
        # Parse the output to extract is_solved and satisfied_clauses
        output = outputs[0]
        is_solved = None
        satisfied = None
        
        for line in output.split('\n'):
            if 'is_solved' in line:
                # Extract the value after 'is_solved ='
                parts = line.split('=')
                if len(parts) > 1:
                    is_solved = int(parts[-1].strip())
            if 'satisfied clauses' in line:
                parts = line.split('=')
                if len(parts) > 1:
                    satisfied = float(parts[-1].strip())
        
        return is_solved, satisfied
        
    finally:
        # Clean up the temporary MPC file
        if mpc_file.exists():
            mpc_file.unlink()


class TestMatSatClauseWeights:
    """Test suite for MatSat with varying clause weights."""

    # ========== 2-Party Tests (2 clauses) ==========

    def test_2p_sat_1(self):
        """Test 2-party SAT with uniform weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_2p_sat_uniform",
            clauses=[[1], [2]],
            n=2,
            m=2,
            weights=[0.1, 0.9],
            description="2-party SAT: (x1) AND (x2), weights=[0.1, 0.9]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_2p_sat_2(self):
        """Test 2-party SAT with heavily biased weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_2p_sat_biased",
            clauses=[[1], [2]],
            n=2,
            m=2,
            weights=[0.9, 0.1],
            description="2-party SAT: (x1) AND (x2), weights=[0.9, 0.1]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_2p_unsat_1(self):
        """Test 2-party UNSAT with uniform weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_2p_unsat_uniform",
            clauses=[[1], [-1]],
            n=1,
            m=2,
            weights=[0.1, 0.9],
            description="2-party UNSAT: (NOT x1) AND (NOT x2), weights=[0.1, 0.9]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_2p_unsat_2(self):
        """Test 2-party UNSAT with heavily biased weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_2p_unsat_biased",
            clauses=[[-1], [-2]],
            n=2,
            m=2,
            weights=[0.9, 0.1],
            description="2-party UNSAT: (NOT x1) AND (NOT x2), weights=[0.9, 0.1]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    # ========== 3-Party Tests (3 clauses) ==========

    def test_3p_sat_1(self):
        """Test 3-party SAT with uniform weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_3p_sat_uniform",
            clauses=[[1], [2], [3]],
            n=3,
            m=3,
            weights=[1/3, 1/3, 1/3],
            description="3-party SAT: (x1) AND (x2) AND (x3), weights=[0.333, 0.333, 0.333]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_3party_satisfiable_descending_weights(self):
        """Test 3-party SAT with heavily biased weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_3p_sat_biased",
            clauses=[[1], [2], [3]],
            n=3,
            m=3,
            weights=[0.8, 0.15, 0.05],
            description="3-party SAT: (x1) AND (x2) AND (x3), weights=[0.8, 0.15, 0.05]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_3p_unsat_1(self):
        """Test 3-party UNSAT with uniform weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_3p_unsat_uniform",
            clauses=[[1], [-1], [2]],
            n=2,
            m=3,
            weights=[.05, .15, .8],
            description="3-party UNSAT: (x1) AND (NOT x1) AND (x2), weights=[0.05, 0.15, 0.8]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

    def test_3p_unsat_2(self):
        """Test 3-party UNSAT with heavily biased weights."""
        is_solved, satisfied = compile_and_run_mpc(
            test_name="test_3p_unsat_biased",
            clauses=[[1], [-1], [2]],
            n=2,
            m=3,
            weights=[0.8, 0.15, 0.05],
            description="3-party UNSAT: (x1) AND (NOT x1) AND (x2), weights=[0.8, 0.15, 0.05]"
        )
        assert is_solved is not None
        print(f"  ✓ Test completed: is_solved={is_solved}, satisfied={satisfied}")

