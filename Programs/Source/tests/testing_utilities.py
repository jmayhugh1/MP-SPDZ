from __future__ import annotations

import csv
import inspect
import os
import random
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest


def _detect_test_name() -> str | None:
    """Walk call stack to find the first function starting with 'test_'."""
    for frame_info in inspect.stack():
        if frame_info.function.startswith("test_"):
            return frame_info.function
    return None


REPO_ROOT = Path(__file__).resolve().parents[4]
MP_SPDZ_ROOT = REPO_ROOT / "MP-SPDZ"
PROGRAMS_SOURCE = MP_SPDZ_ROOT / "Programs" / "Source"
SHAMIR_BIN = MP_SPDZ_ROOT / "shamir-party.x"
MP_SPDZ_ENV = {**os.environ, "PYTHONPATH": str(MP_SPDZ_ROOT)}
TRACE_ARTIFACTS_ROOT = PROGRAMS_SOURCE / "tests" / "artifacts"
TRACE_CSV_DIR = TRACE_ARTIFACTS_ROOT / "csv"
TRACE_GRAPHS_DIR = TRACE_ARTIFACTS_ROOT / "graphs"


def _parse_solver_trace(output: str) -> list[dict[str, float | int]]:
    """
    Parse MatSat iteration trace from party output.

    Returns one row per iteration with fields:
      - try_idx
      - iter_idx
      - jsat
      - grad_sq
      - epsilon
      - alpha
      - err
      - unsat_clauses
    """
    try_re = re.compile(r"try_idx\s*=\s*(\d+)")
    iter_re = re.compile(r"iter_idx\s*=\s*(\d+)")
    jsat_re = re.compile(r"jsat\s*=\s*([-+]?\d+(?:\.\d+)?)")
    grad_re = re.compile(r"grad_sq\s*=\s*([-+]?\d+(?:\.\d+)?)")
    eps_re = re.compile(r"epsilon\s*=\s*([-+]?\d+(?:\.\d+)?)")
    alpha_re = re.compile(r"uncapped alpha\s*=\s*([-+]?\d+(?:\.\d+)?)")
    err_re = re.compile(r"err\s*=\s*([-+]?\d+(?:\.\d+)?)")
    unsat_re = re.compile(r"unsat_clauses\s*=\s*(\d+)")

    rows: list[dict[str, float | int]] = []
    current_try = -1
    saw_explicit_try = False
    last_iter: int | None = None
    current_row: dict[str, float | int] | None = None

    for raw_line in output.splitlines():
        line = raw_line.strip()
        m_try = try_re.search(line)
        if m_try:
            current_try = int(m_try.group(1))
            saw_explicit_try = True
            last_iter = None
            continue
        m_iter = iter_re.search(line)
        if m_iter:
            iter_idx = int(m_iter.group(1))
            if not saw_explicit_try:
                if last_iter is None or iter_idx <= last_iter:
                    current_try += 1
            elif last_iter is not None and iter_idx <= last_iter:
                # Fallback in case logs ever stop printing explicit try_idx.
                current_try += 1
            last_iter = iter_idx
            current_row = {"try_idx": current_try, "iter_idx": iter_idx}
            rows.append(current_row)
            continue

        if current_row is None:
            continue

        m_jsat = jsat_re.search(line)
        if m_jsat:
            # jsat can appear twice per iteration; keep the first parsed value.
            current_row.setdefault("jsat", float(m_jsat.group(1)))
            continue

        m_grad = grad_re.search(line)
        if m_grad:
            current_row["grad_sq"] = float(m_grad.group(1))
            continue

        m_eps = eps_re.search(line)
        if m_eps:
            current_row["epsilon"] = float(m_eps.group(1))
            continue

        m_alpha = alpha_re.search(line)
        if m_alpha:
            current_row["alpha"] = float(m_alpha.group(1))
            continue

        m_err = err_re.search(line)
        if m_err:
            current_row["err"] = float(m_err.group(1))
            continue

        m_unsat = unsat_re.search(line)
        if m_unsat:
            current_row["unsat_clauses"] = int(m_unsat.group(1))
            continue

    return rows


def _write_trace_csv(
    program_name: str, rows: list[dict[str, float | int]], test_name: str | None = None
) -> Path:
    TRACE_CSV_DIR.mkdir(parents=True, exist_ok=True)
    folder_name = (
        test_name if test_name else datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    csv_path = TRACE_CSV_DIR / f"{program_name}_{folder_name}.csv"
    fieldnames = [
        "try_idx",
        "iter_idx",
        "jsat",
        "grad_sq",
        "epsilon",
        "alpha",
        "err",
        "unsat_clauses",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return csv_path


def _plot_trace_by_try(
    csv_path: Path, program_name: str, test_name: str | None = None
) -> list[Path]:
    """
    Read a trace CSV and save one graph per try.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception:
        # Keep tests runnable even if matplotlib isn't installed.
        return []

    rows_by_try: dict[int, list[dict[str, float | int]]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try_idx = int(row["try_idx"])
            rows_by_try.setdefault(try_idx, []).append(
                {
                    "iter_idx": int(row["iter_idx"]),
                    "jsat": float(row["jsat"]) if row["jsat"] else None,
                    "grad_sq": float(row["grad_sq"]) if row["grad_sq"] else None,
                    "alpha": float(row["alpha"]) if row["alpha"] else None,
                    "err": float(row["err"]) if row.get("err") else None,
                    "unsat_clauses": (
                        float(row["unsat_clauses"])
                        if row.get("unsat_clauses")
                        else None
                    ),
                }
            )

    folder_name = (
        test_name if test_name else csv_path.stem.replace(f"{program_name}_", "")
    )
    out_dir = TRACE_GRAPHS_DIR / program_name / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for try_idx, rows in rows_by_try.items():
        rows = sorted(rows, key=lambda r: int(r["iter_idx"]))
        x = [int(r["iter_idx"]) for r in rows]
        jsat = [r["jsat"] for r in rows]
        grad = [r["grad_sq"] for r in rows]
        alpha = [r["alpha"] for r in rows]
        err = [r["err"] for r in rows]
        unsat = [r["unsat_clauses"] for r in rows]

        fig, axes = plt.subplots(5, 1, figsize=(9, 13), sharex=True)
        axes[0].plot(x, jsat, marker="o", markersize=2, linewidth=1)
        axes[0].set_ylabel("jsat")
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(x, grad, marker="o", markersize=2, linewidth=1)
        axes[1].set_ylabel("grad_sq")
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(x, alpha, marker="o", markersize=2, linewidth=1)
        axes[2].set_ylabel("uncapped alpha")
        axes[2].grid(True, alpha=0.3)

        axes[3].plot(x, err, marker="o", markersize=2, linewidth=1)
        axes[3].set_ylabel("err")
        axes[3].grid(True, alpha=0.3)

        axes[4].plot(x, unsat, marker="o", markersize=2, linewidth=1)
        axes[4].set_xlabel("iteration")
        axes[4].set_ylabel("unsat_clauses")
        axes[4].grid(True, alpha=0.3)

        fig.suptitle(f"{program_name} - try {try_idx}")
        fig.tight_layout()
        out_path = out_dir / f"try_{try_idx}.png"
        fig.savefig(out_path, dpi=140)
        plt.close(fig)
        saved.append(out_path)

    return saved


def write_trace_artifacts(
    program_name: str, output: str, test_name: str | None = None
) -> tuple[Path | None, list[Path]]:
    """
    Parse run output and emit CSV + per-try plots.

    If test_name is provided, artifacts are organized under that name;
    otherwise a timestamp-based folder is used.
    """
    rows = _parse_solver_trace(output)
    if not rows:
        return None, []
    csv_path = _write_trace_csv(program_name, rows, test_name=test_name)
    graph_paths = _plot_trace_by_try(csv_path, program_name, test_name=test_name)
    return csv_path, graph_paths


def write_matsat_utils_program(
    program_name: str,
    q_rows: list[list[int]],
    n: int,
    *,
    clause_weights: list[float] | None = None,
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
    if clause_weights is not None and len(clause_weights) != m:
        raise ValueError("clause_weights length must match number of q_rows")
    program_path = PROGRAMS_SOURCE / f"{program_name}.mpc"
    clause_weights_setup = ""
    clause_weights_arg = "None"
    if clause_weights is not None:
        clause_weights_setup = f"""clause_weight_values = {clause_weights}
clause_weights_mat = Matrix(m, 1, sfix)
for i in range(m):
    clause_weights_mat[i][0] = sfix(clause_weight_values[i])

"""
        clause_weights_arg = "clause_weights_mat"
    program_source = f"""from Compiler.types import sfix, Matrix
from Programs.Source.matsat_utils import MatSatUtils

n = {n}
m = {m}
q_rows = {q_rows}

Q = Matrix(m, 2 * n, sfix)
for i in range(m):
    for j in range(2 * n):
        Q[i][j] = sfix(q_rows[i][j])

{clause_weights_setup}

u_tilde, u, is_solved, satisfied_clauses = MatSatUtils.solve_matsat(
    Q=Q,
    n=n,
    m=m,
    clause_weights={clause_weights_arg},
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
    program_name: str, num_parties: int, port: int, *, test_name: str | None = None
) -> tuple[int | None, float | None, list[int] | None]:
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
        csv_path, graph_paths = write_trace_artifacts(
            program_name, out0, test_name=test_name
        )
        if csv_path is not None:
            print(f"trace csv: {csv_path}")
        for graph_path in graph_paths:
            print(f"trace graph: {graph_path}")

        solved_match = re.search(r"RESULT_IS_SOLVED=(\d+)", out0)
        sat_match = re.search(
            r"RESULT_SATISFIED_CLAUSES=([-+]?\d+(?:\.\d+)?|NaN)", out0
        )
        is_solved = int(solved_match.group(1)) if solved_match else None
        if sat_match and sat_match.group(1) != "NaN":
            satisfied = float(sat_match.group(1))
        else:
            satisfied = None
        u_matches = re.findall(r"RESULT_U\[(\d+)\]=(\d+)", out0)
        if u_matches:
            u_by_idx = {int(i): int(v) for i, v in u_matches}
            u_vector = [u_by_idx[i] for i in sorted(u_by_idx.keys())]
        else:
            u_vector = None
        return is_solved, satisfied, u_vector
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
    clause_weights: list[float] | None = None,
    l_value: float = 2.0,
    beta_value: float = 0.5,
    max_try: int = 5,
    max_itr: int = 20,
    print_results: bool = True,
    weighted: bool = False,
    return_u: bool = False,
    test_name: str | None = None,
) -> (
    tuple[int | None, float | None] | tuple[int | None, float | None, list[int] | None]
):
    # Auto-detect test name from call stack if not provided
    if test_name is None:
        test_name = _detect_test_name()

    program_path = write_matsat_utils_program(
        program_name=program_name,
        q_rows=q_rows,
        n=n,
        clause_weights=clause_weights,
        l_value=l_value,
        beta_value=beta_value,
        max_try=max_try,
        max_itr=max_itr,
        print_results=print_results,
        weighted=weighted,
    )
    try:
        compile_program(program_name)
        is_solved, satisfied, u_vector = run_program(
            program_name=program_name,
            num_parties=num_parties,
            port=port,
            test_name=test_name,
        )
        if return_u:
            return is_solved, satisfied, u_vector
        return is_solved, satisfied
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
    clause_weights: list[float] | None = None,
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
        clause_weights=clause_weights,
        l_value=l_value,
        beta_value=beta_value,
        max_try=max_try,
        max_itr=max_itr,
        print_results=print_results,
        weighted=weighted,
    )
