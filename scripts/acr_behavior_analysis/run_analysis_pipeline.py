#!/usr/bin/env python3
"""
run_analysis_pipeline.py - One-command reproduction of the ACR behavior analysis.

Runs, for each OS:
  1. python data_processing/download_dataset.py csv <os>      (per-domain CSVs from Zenodo)
  2. python acr_behavior_analysis/manager_analysis.py <os>

Place this file anywhere inside `scripts/` (e.g. `scripts/acr_behavior_analysis/`);
it locates the `scripts/` folder on its own and can be run from any directory.

Examples
--------
  python run_analysis_pipeline.py                  # all OSes with precomputed CSVs on Zenodo
  python run_analysis_pipeline.py tizen
  python run_analysis_pipeline.py tizen webos fire
  python run_analysis_pipeline.py tizen --skip-download   # reuse CSVs already on disk
  python run_analysis_pipeline.py tizen --dry-run

Full output of every step goes to logs/<timestamp>_analysis/<os>/NN_<step>.log
under the project root. The exit code is non-zero if any step failed.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set


def _find_scripts_folder() -> Path:
    here = Path(__file__).resolve().parent
    for d in (here, *here.parents):
        if (d / "data_processing").is_dir() and (d / "acr_behavior_analysis").is_dir():
            return d
    sys.exit(f"ERROR: could not find the scripts/ folder (containing data_processing/ and "
             f"acr_behavior_analysis/) at or above {here}")


SCRIPTS_FOLDER = _find_scripts_folder()
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA = PROJECT_ROOT / "data"
LOG_ROOT = PROJECT_ROOT / "logs"

DOWNLOAD_SCRIPT = "data_processing/download_dataset.py"
MANAGER_SCRIPT = "acr_behavior_analysis/manager_analysis.py"
ANALYSIS_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "analysis.py"
VENV_PYTHON = SCRIPTS_FOLDER / "venv" / "bin" / "python"

# manager_analysis.py exits 0 even when some domains fail; this line reveals it.
MANAGER_FAIL_MARKER = "✗ Failed:"


def individual(o: str) -> Path:
    return DATA / "individual_domain_csvs" / o


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def dataset_oses(data_type: str) -> List[str]:
    """OS names listed for `data_type` in DATA_FOLDERS of download_dataset.py, in the
    order defined there. Parsed without importing, so `requests` is not needed."""
    import ast
    src = SCRIPTS_FOLDER / "data_processing" / "download_dataset.py"
    try:
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "DATA_FOLDERS" for t in node.targets):
                return list(ast.literal_eval(node.value).get(data_type, {}))
    except (OSError, SyntaxError, ValueError):
        pass
    # Fallback: every OS that has experiment timings.
    base = DATA / "experiment_timings"
    return sorted(d.name for d in base.iterdir() if d.is_dir()) if base.is_dir() else []


def check_dependencies(download: bool) -> List[str]:
    needed = ["pandas"] + (["requests"] if download else [])
    return [m for m in needed if importlib.util.find_spec(m) is None]


def preflight(o: str, download: bool) -> List[str]:
    problems = []
    scripts = [MANAGER_SCRIPT] + ([DOWNLOAD_SCRIPT] if download else [])
    for s in scripts:
        if not (SCRIPTS_FOLDER / s).exists():
            problems.append(f"script not found: {rel(SCRIPTS_FOLDER / s)}")
    for p in (DATA / "experiment_timings" / o / "timing.csv", ANALYSIS_SCRIPT, VENV_PYTHON):
        if not p.exists():
            problems.append(f"missing input: {rel(p)}")
    if not download and not any(individual(o).glob("*.csv")):
        problems.append(f"no CSVs in {rel(individual(o))} (run without --skip-download)")
    return problems


def run(cmd_args: List[str], log_path: Path, quiet: bool, markers=()):
    cmd = [sys.executable, "-u", *cmd_args]
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
    seen: Set[str] = set()
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(cmd)}\n# cwd: {SCRIPTS_FOLDER}\n# started: {datetime.now().isoformat()}\n\n")
        log.flush()
        proc = subprocess.Popen(cmd, cwd=SCRIPTS_FOLDER, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1)
        try:
            for line in proc.stdout:
                log.write(line)
                if not quiet:
                    sys.stdout.write("    " + line)
                seen.update(m for m in markers if m in line)
            rc = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            raise
        log.write(f"\n# exit code: {rc}\n")
    return rc, seen


def main():
    parser = argparse.ArgumentParser(
        description="Download per-domain CSVs and run the ACR behavior analysis for one or more OSes.")
    parser.add_argument("os_names", nargs="*",
                        help="OS folder name(s), e.g. tizen webos; omit to run all OSes")
    parser.add_argument("--skip-download", action="store_true",
                        help="use the CSVs already in data/individual_domain_csvs/<os>/")
    parser.add_argument("--dry-run", action="store_true", help="check inputs and print commands only")
    parser.add_argument("--quiet", action="store_true", help="write step output only to the log files")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="stop at the first failing OS (by default the remaining OSes still run)")
    args = parser.parse_args()

    oses = args.os_names or dataset_oses("csv")
    if not oses:
        parser.error("no OSes found; give OS name(s) explicitly")
    download = not args.skip_download

    missing = check_dependencies(download)
    if missing:
        print(f"ERROR: missing Python packages in {sys.executable}: {', '.join(missing)}")
        return 1

    steps = ([("download_csvs", lambda o: [DOWNLOAD_SCRIPT, "csv", o], ())] if download else []) + \
            [("analysis", lambda o: [MANAGER_SCRIPT, o], (MANAGER_FAIL_MARKER,))]

    log_dir = LOG_ROOT / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_analysis")
    print("=" * 72)
    print("ACR behavior analysis runner")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Interpreter  : {sys.executable}")
    print(f"  OS(es)       : {', '.join(oses)}")
    print(f"  Steps        : {', '.join(k for k, _, _ in steps)}")
    if not args.dry_run:
        print(f"  Logs         : {rel(log_dir)}")
    print("=" * 72)

    summary, any_failure = [], False
    for o in oses:
        print(f"\n##### {o} #####")
        problems = preflight(o, download)
        if problems:
            print("Pre-flight check failed:")
            for p in problems:
                print(f"  - {p}")
            summary.append((o, "preflight", "FAILED", 0.0, f"{len(problems)} problem(s)"))
            any_failure = True
            if not args.stop_on_error:
                continue
            break

        if args.dry_run:
            print("Pre-flight check passed. Commands that would run (cwd = scripts folder):")
            for _, argv, _ in steps:
                print(f"  python {' '.join(argv(o))}")
            continue

        (log_dir / o).mkdir(parents=True, exist_ok=True)
        os_failed = False
        for n, (key, argv, markers) in enumerate(steps, 1):
            log_path = log_dir / o / f"{n:02d}_{key}.log"
            print(f"\n[{o}] step {n}/{len(steps)}: {key}")
            print(f"[{o}] $ python {' '.join(argv(o))}")
            t0 = time.time()
            rc, seen = run(argv(o), log_path, args.quiet, markers)

            status, note = "OK", ""
            if rc != 0:
                status, note = "FAILED", f"exit code {rc}"
            elif MANAGER_FAIL_MARKER in seen:
                status, note = "FAILED", "one or more domains failed (see log)"
            elif key == "download_csvs":
                n_csv = len(list(individual(o).glob("*.csv")))
                if n_csv == 0:
                    status, note = "FAILED", f"no CSV files in {rel(individual(o))} after download"
                else:
                    note = f"{n_csv} CSV file(s) in {rel(individual(o))}"

            dt = time.time() - t0
            summary.append((o, key, status, dt, note))
            print(f"[{o}] {key}: {status} in {fmt_duration(dt)}" + (f" ({note})" if note else ""))
            if status == "FAILED":
                print(f"[{o}] see log: {rel(log_path)}")
                os_failed = any_failure = True
                break
        if os_failed and args.stop_on_error:
            break

    if not args.dry_run:
        print("\n" + "=" * 72 + "\nSummary\n" + "=" * 72)
        for o, key, status, dt, note in summary:
            print(f"  {o:<22} {key:<14} {status:<7} {fmt_duration(dt):>9}  {note}")
        print(f"\nLogs: {rel(log_dir)}")
    return 1 if any_failure else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)