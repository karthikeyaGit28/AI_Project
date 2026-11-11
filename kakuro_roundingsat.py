"""Kakuro decision model executed by the real RoundingSat command-line solver.

Every cell has nine Boolean indicators. Exactly one digit is selected; each run
has its clue sum and at most one occurrence of each digit. No propagation from
the Python solver, solution hint, or generator witness is used.

Official interfaces checked against the RoundingSat master source:
https://gitlab.com/MIAOresearch/software/roundingsat/-/blob/master/InputFormats.md
https://gitlab.com/MIAOresearch/software/roundingsat/-/blob/master/src/Options.hpp
https://gitlab.com/MIAOresearch/software/roundingsat/-/blob/master/src/quit.cpp
https://gitlab.com/MIAOresearch/software/roundingsat/-/blob/master/src/run.cpp
https://gitlab.com/MIAOresearch/software/roundingsat/-/blob/master/src/Stats.cpp
"""

from contextlib import nullcontext
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from generate_and_solve import validate_solution


DEFAULT_BINARY = Path(__file__).resolve().parent / "tools" / "roundingsat" / (
    "roundingsat.exe" if os.name == "nt" else "roundingsat"
)


def ensure_roundingsat_available():
    """Return the executable path without launching or downloading a solver."""
    configured = os.environ.get("ROUNDINGSAT_BIN")
    binary = Path(configured).expanduser() if configured else DEFAULT_BINARY
    binary = binary.resolve()
    if not binary.is_file():
        raise FileNotFoundError(
            f"RoundingSat executable not found: {binary}. Install the official "
            "binary in tools/roundingsat or set ROUNDINGSAT_BIN to its path."
        )
    return binary


@lru_cache(maxsize=8)
def _binary_sha256(path, size, modified_ns):
    # The stat values invalidate the cached fingerprint if the executable changes.
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_inputs(whites, runs, seed, time_limit):
    if not whites or len(set(whites)) != len(whites):
        raise ValueError("whites must contain distinct cells and cannot be empty")
    if any(not isinstance(cell, tuple) or len(cell) != 2 or
           any(type(coordinate) is not int for coordinate in cell) for cell in whites):
        raise ValueError("white cells must be (row, column) integer tuples")
    if type(seed) is not int or not 0 <= seed < 2 ** 31:
        raise ValueError("seed must be an integer from 0 through 2**31 - 1")
    if (isinstance(time_limit, bool) or not isinstance(time_limit, (int, float)) or
            not math.isfinite(time_limit) or time_limit < 0):
        raise ValueError("time_limit must be a finite nonnegative number")
    white_set = set(whites)
    if not runs:
        raise ValueError("runs cannot be empty")
    for run in runs:
        cells = run["cells"]
        if (not 2 <= len(cells) <= 9 or len(set(cells)) != len(cells) or
                not set(cells).issubset(white_set)):
            raise ValueError("each run must contain 2..9 distinct white cells")
        if type(run["sum"]) is not int or run["sum"] <= 0:
            raise ValueError("run sums must be positive integers")


def encode_kakuro_opb(whites, runs):
    """Return a linear OPB model with variables ordered by sorted coordinates.

    For sorted cell index i (zero based), x(9*i+d) means digit d, d in 1..9.
    There are 9*W variables and W+10*R constraints. The negative >= constraints
    implement at-most-one because OPB supports only >= and = comparisons.
    """
    _validate_inputs(whites, runs, 42, 120)
    offsets = {cell: 9 * index for index, cell in enumerate(sorted(whites))}
    lines = [f"* #variable= {9 * len(whites)} #constraint= {len(whites) + 10 * len(runs)}"]
    for cell in sorted(whites):
        offset = offsets[cell]
        lines.append(f"* cell {cell[0]} {cell[1]} variables x{offset + 1}..x{offset + 9}")
        lines.append(" ".join(f"+1 x{offset + digit}" for digit in range(1, 10)) + " = 1;")
    for run in runs:
        lines.append(" ".join(
            f"+{digit} x{offsets[cell] + digit}"
            for cell in run["cells"] for digit in range(1, 10)
        ) + f" = {run['sum']};")
        for digit in range(1, 10):
            lines.append(" ".join(f"-1 x{offsets[cell] + digit}" for cell in run["cells"]) + " >= -1;")
    return "\n".join(lines) + "\n"


def _native_status(stdout, required=True):
    statuses = re.findall(r"^s\s+(.+?)\s*$", stdout, re.MULTILINE)
    allowed = {"SATISFIABLE", "UNSATISFIABLE", "UNKNOWN", "TIMELIMIT"}
    if len(statuses) != 1 or statuses[0] not in allowed:
        if required:
            raise RuntimeError(f"RoundingSat returned missing, conflicting, or unsupported status: {statuses}")
        return None
    return statuses[0]


def _decode_model(stdout, whites):
    count = 9 * len(whites)
    assignments = {}
    for line in stdout.splitlines():
        if not line.startswith("v ") and line != "v":
            continue
        for token in line.split()[1:]:
            match = re.fullmatch(r"(-?)x([1-9][0-9]*)", token)
            if not match:
                raise RuntimeError(f"RoundingSat returned malformed model literal: {token!r}")
            variable = int(match.group(2))
            if not 1 <= variable <= count or variable in assignments:
                raise RuntimeError("RoundingSat returned duplicate or out-of-range model variables")
            assignments[variable] = not bool(match.group(1))
    if len(assignments) != count:
        raise RuntimeError(f"RoundingSat returned incomplete model: {len(assignments)}/{count} variables")
    candidate = {}
    for index, cell in enumerate(sorted(whites)):
        selected = [digit for digit in range(1, 10) if assignments[9 * index + digit]]
        if len(selected) != 1:
            raise RuntimeError("RoundingSat model violates exactly-one-digit constraints")
        candidate[cell] = selected[0]
    return candidate


def _native_statistics(stdout):
    values = {}
    for name in ("decisions", "conflicts", "propagations", "restarts"):
        matches = re.findall(rf"^c {name}\s+(\d+)\s*$", stdout, re.MULTILINE)
        values[f"native_{name}"] = int(matches[-1]) if matches else None
    match = re.search(r"^c cpu time\s+([0-9.eE+-]+)\s+s\s*$", stdout, re.MULTILINE)
    values["native_time_seconds"] = float(match.group(1)) if match else None
    match = re.search(r"^c (RoundingSat\s+.+?)\s*$", stdout, re.MULTILINE)
    values["solver_version"] = match.group(1) if match else None
    match = re.search(r"^c commit\s+(.+?)\s*$", stdout, re.MULTILINE)
    values["solver_commit"] = match.group(1) if match else None
    match = re.search(r"^c LP calls\s+(\d+)\s*$", stdout, re.MULTILINE)
    values["native_lp_calls"] = int(match.group(1)) if match else None
    # A nonzero count proves LP was used; zero does not reveal compile-time support.
    values["lp_used"] = bool(values["native_lp_calls"]) if match else None
    return values


def _check_returncode(returncode, native_status):
    # Current upstream returns 0 for normal SAT and UNSAT, 4 for its time limit.
    # Conventional SAT competition codes are also supported when consistent.
    allowed = {"SATISFIABLE": {0, 10}, "UNSATISFIABLE": {0, 20},
               "UNKNOWN": {0}, "TIMELIMIT": {0, 4}}
    if returncode not in allowed[native_status]:
        raise RuntimeError(f"RoundingSat exit code {returncode} contradicts status {native_status}")


def _as_text(output):
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else (output or "")


def roundingsat_search(whites, runs, seed=42, time_limit=120, artifact_dir=None):
    """Solve using RoundingSat with a total wall-clock budget in seconds.

    Timing includes OPB encoding, working-directory creation, OPB file I/O,
    process startup, native search and assignment decoding. Binary discovery and
    fingerprinting, independent Kakuro validation, report/log writes and cleanup
    are excluded. ``search_time_seconds`` is process startup/search plus decode,
    while native_time_seconds preserves the solver's own "cpu time" statistic.
    On Windows upstream uses clock()/CLOCKS_PER_SEC with integer division, so
    this statistic has whole-second resolution and is not a precise CPU timer.

    Current RoundingSat has no seed option: seed is recorded but not applied.
    LP ratio 1 is its documented default and is passed explicitly. A hard
    subprocess wall timeout kills and reaps the actual native process; exceeding
    the total budget is UNKNOWN, never evidence of infeasibility.
    """
    _validate_inputs(whites, runs, seed, time_limit)
    binary = ensure_roundingsat_available()
    info = binary.stat()
    fingerprint = _binary_sha256(str(binary), info.st_size, info.st_mtime_ns)
    stats = {
        "status": "UNKNOWN", "native_status": None, "branches": None,
        "backtracking_count": None, "conflicts": None, "nodes_visited": None,
        "execution_time_seconds": 0.0, "preprocessing_time_seconds": 0.0,
        "model_build_time_seconds": 0.0, "search_time_seconds": 0.0,
        "domain_reduction_percent": None, "binary_sha256": fingerprint,
        "binary_path": str(binary), "seed_requested": seed, "seed_applied": False,
        "lp_ratio": 1, "native_returncode": None, "timed_out": False,
        "native_time_label": "cpu time (upstream label; coarse clock() on Windows)",
        "timeout_reason": None, "opb_variables": 9 * len(whites),
        "opb_constraints": len(whites) + 10 * len(runs),
        **_native_statistics(""),
    }
    candidate = None
    stdout = stderr = ""
    command = []
    error = None
    started = time.perf_counter()
    deadline = started + time_limit
    context = nullcontext(str(Path(artifact_dir).resolve())) if artifact_dir is not None else tempfile.TemporaryDirectory(prefix="kakuro_roundingsat_")
    with context as directory:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        opb_path = directory / "kakuro.opb"
        opb_path.write_text(encode_kakuro_opb(whites, runs), encoding="ascii")
        model_finished = time.perf_counter()
        remaining = deadline - model_finished
        if remaining <= 0:
            stats.update(timed_out=True, timeout_reason="wall_time_limit_before_launch")
        else:
            command = [str(binary), str(opb_path), "--print-sol=1", "--verbosity=1",
                       "--lp=1", f"--time-limit={remaining:.9f}"]
            try:
                process = subprocess.run(
                    command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=remaining, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                stdout, stderr = process.stdout, process.stderr
                stats["native_returncode"] = process.returncode
                stats["native_status"] = _native_status(stdout)
                _check_returncode(process.returncode, stats["native_status"])
                if stats["native_status"] == "SATISFIABLE":
                    candidate = _decode_model(stdout, whites)
                    stats["status"] = "SOLVED"
                elif stats["native_status"] == "UNSATISFIABLE":
                    if re.search(r"^v(?:\s|$)", stdout, re.MULTILINE):
                        raise RuntimeError("RoundingSat returned a model with UNSATISFIABLE status")
                    stats["status"] = "INFEASIBLE"
                elif stats["native_status"] == "TIMELIMIT":
                    stats.update(timed_out=True, timeout_reason="native_time_limit")
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = _as_text(exc.stdout), _as_text(exc.stderr)
                stats.update(timed_out=True, timeout_reason="native_process_wall_time_limit",
                             native_status=_native_status(stdout, required=False))
            except (OSError, RuntimeError) as exc:
                error = exc
        finished = time.perf_counter()
        if finished > deadline and error is None:
            candidate = None
            stats.update(status="UNKNOWN", timed_out=True,
                         timeout_reason=stats["timeout_reason"] or "wall_time_limit_after_decode")
        stats.update(
            execution_time_seconds=finished - started,
            preprocessing_time_seconds=model_finished - started,
            model_build_time_seconds=model_finished - started,
            search_time_seconds=finished - model_finished,
            **_native_statistics(stdout),
        )
        # Recheck original rules independently of the encoding and model parser.
        if candidate is not None and not validate_solution(candidate, whites, runs):
            error = RuntimeError("RoundingSat returned an assignment that failed Kakuro validation")
        if artifact_dir is not None:
            (directory / "stdout.txt").write_text(stdout, encoding="utf-8")
            (directory / "stderr.txt").write_text(stderr, encoding="utf-8")
            (directory / "command.json").write_text(json.dumps({
                "argv": command, "returncode": stats["native_returncode"],
                "timed_out": stats["timed_out"], "timeout_reason": stats["timeout_reason"],
                "binary_sha256": fingerprint, "error": str(error) if error else None,
                "seed_requested": seed, "seed_applied": False, "lp_ratio": 1,
            }, indent=2) + "\n", encoding="utf-8")
        if error is not None:
            raise error
    return candidate, stats
