from __future__ import annotations

import os
import random
import re
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
MP_SPDZ_ROOT = REPO_ROOT / "MP-SPDZ"
PROGRAMS_SOURCE = MP_SPDZ_ROOT / "Programs" / "Source"
SHAMIR_BIN = MP_SPDZ_ROOT / "shamir-party.x"
MP_SPDZ_ENV = {**os.environ, "PYTHONPATH": str(MP_SPDZ_ROOT)}


def write_matsat_utils_program(
    program_name: str,
    q_rows: list[list[int]],
    n: int,
    *,
    l_value: float = 2.0,
    beta_value: float = 0.5,
    max_try: int = 5,
    max_itr: int = 20,
    print_results: bool = True,
    weighted: bool = False,
) -> Path:
    """
    Create a temporary .mpc program that invokes MatSatUtils.solve_matsat directly.
    """
    m = len(q_rows)
    program_path = PROGRAMS_SOURCE / f"{program_name}.mpc"
    program_source = f"""from Compiler.types import sfix, Matrix
from Programs.Source.matsat_utils import MatSatUtils

n = {n}
m = {m}
q_rows = {q_rows}

Q = Matrix(m, 2 * n, sfix)
for i in range(m):
    for j in range(2 * n):
        Q[i][j] = sfix(q_rows[i][j])

u_tilde, u, is_solved, satisfied_clauses = MatSatUtils.solve_matsat(
    Q=Q,
    n=n,
    m=m,
    l={l_value},
    beta=sfix({beta_value}),
    max_try={max_try},
    max_itr={max_itr},
    print_results={print_results},
    weighted={weighted},
)
"""
    program_path.write_text(program_source, encoding="utf-8")
    return program_path


def compile_program(program_name: str) -> None:
    proc = subprocess.run(
        ["python3", "compile.py", program_name],
        cwd=MP_SPDZ_ROOT,
        env=MP_SPDZ_ENV,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Compilation failed for {program_name}:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def run_program(
    program_name: str, num_parties: int, port: int
) -> tuple[int | None, float | None]:
    if not SHAMIR_BIN.exists():
        pytest.skip("shamir-party.x not found; build MP-SPDZ first")

    procs: list[subprocess.Popen] = []
    try:
        for party_id in range(num_parties):
            p = subprocess.Popen(
                [
                    str(SHAMIR_BIN),
                    "-N",
                    str(num_parties),
                    "-p",
                    str(party_id),
                    "-pn",
                    str(port),
                    "-h",
                    "localhost",
                    "-v",
                    program_name,
                ],
                cwd=MP_SPDZ_ROOT,
                env=MP_SPDZ_ENV,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            procs.append(p)
            time.sleep(0.1)

        outs: list[str] = []
        errs: list[str] = []
        for p in procs:
            out, err = p.communicate(timeout=240)
            outs.append(out)
            errs.append(err)

        for p, err in zip(procs, errs):
            if p.returncode != 0:
                if "Operation not permitted" in err or "cannot connect" in err:
                    pytest.skip(
                        f"MP-SPDZ networking not permitted in this environment: {err}"
                    )
                raise RuntimeError(f"Party failed ({p.returncode}): {err}")

        out0 = outs[0]
        solved_match = re.search(r"RESULT_IS_SOLVED=(\d+)", out0)
        sat_match = re.search(
            r"RESULT_SATISFIED_CLAUSES=([-+]?\d+(?:\.\d+)?|NaN)", out0
        )
        is_solved = int(solved_match.group(1)) if solved_match else None
        if sat_match and sat_match.group(1) != "NaN":
            satisfied = float(sat_match.group(1))
        else:
            satisfied = None
        return is_solved, satisfied
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()


def compile_and_run_matsat_utils_case(
    program_name: str,
    q_rows: list[list[int]],
    n: int,
    num_parties: int,
    port: int,
    *,
    l_value: float = 2.0,
    beta_value: float = 0.5,
    max_try: int = 5,
    max_itr: int = 20,
    print_results: bool = True,
    weighted: bool = False,
) -> tuple[int | None, float | None]:
    program_path = write_matsat_utils_program(
        program_name=program_name,
        q_rows=q_rows,
        n=n,
        l_value=l_value,
        beta_value=beta_value,
        max_try=max_try,
        max_itr=max_itr,
        print_results=print_results,
        weighted=weighted,
    )
    try:
        compile_program(program_name)
        return run_program(
            program_name=program_name, num_parties=num_parties, port=port
        )
    finally:
        if program_path.exists():
            program_path.unlink()


def generate_random_q_matrix(
    rows: int,
    columns: int,
    *,
    seed: int | None = None,
    density: float = 0.35,
    ensure_nonempty_rows: bool = True,
) -> list[list[int]]:
    """
    Build a random binary Q matrix with shape (rows, columns).

    Notes:
      - For MatSat usage, columns should be 2*n (even).
      - Values are 0/1.
    """
    if rows < 1:
        raise ValueError("rows must be >= 1")
    if columns < 2:
        raise ValueError("columns must be >= 2")
    if not (0.0 <= density <= 1.0):
        raise ValueError("density must be in [0.0, 1.0]")

    rng = random.Random(seed)
    q_rows: list[list[int]] = []
    for _ in range(rows):
        row = [1 if rng.random() < density else 0 for _ in range(columns)]
        if ensure_nonempty_rows and sum(row) == 0:
            row[rng.randrange(columns)] = 1
        q_rows.append(row)
    return q_rows


def compile_and_run_random_matsat_case(
    program_name: str,
    rows: int,
    columns: int,
    *,
    seed: int | None = None,
    density: float = 0.35,
    ensure_nonempty_rows: bool = True,
    num_parties: int = 3,
    port: int = 5099,
    l_value: float = 2.0,
    beta_value: float = 0.5,
    max_try: int = 5,
    max_itr: int = 20,
    print_results: bool = True,
    weighted: bool = False,
) -> tuple[int | None, float | None]:
    """
    Convenience wrapper to test a random Q matrix by specifying rows/columns.
    """
    if columns % 2 != 0:
        raise ValueError("columns must be even because MatSat expects 2*n literals")
    n = columns // 2
    q_rows = generate_random_q_matrix(
        rows=rows,
        columns=columns,
        seed=seed,
        density=density,
        ensure_nonempty_rows=ensure_nonempty_rows,
    )
    return compile_and_run_matsat_utils_case(
        program_name=program_name,
        q_rows=q_rows,
        n=n,
        num_parties=num_parties,
        port=port,
        l_value=l_value,
        beta_value=beta_value,
        max_try=max_try,
        max_itr=max_itr,
        print_results=print_results,
        weighted=weighted,
    )
