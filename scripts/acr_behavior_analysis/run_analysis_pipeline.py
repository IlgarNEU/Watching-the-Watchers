#!/usr/bin/env python3
"""
run_analysis_pipeline.py - One-command reproduction of the ACR behavior analysis.

Runs, for each OS:
  1. python data_processing/download_dataset.py csv <os>                 (per-domain CSVs from Zenodo)
  2. python acr_behavior_analysis/manager_analysis.py <os>               (time-series / CDF analysis)
  3. python acr_behavior_analysis/manager_analysis_labeling.py <os> \
         --script analysis_labeling.py                                    (traffic volume per window)
  4. python acr_behavior_analysis/label_experiments.py <os>              (On/Off labels)

Then once, for every OS whose labeling succeeded:
  5. python acr_behavior_analysis/plot_heatmap.py <os...> --combined     (ACR heatmap figure)

Examples
--------
  python run_analysis_pipeline.py                  # all OSes with precomputed CSVs on Zenodo
  python run_analysis_pipeline.py tizen
  python run_analysis_pipeline.py tizen webos fire
  python run_analysis_pipeline.py tizen --skip-download   # reuse CSVs already on disk
  python run_analysis_pipeline.py --skip-download --skip-analysis   # only volume, labels, heatmap
  python run_analysis_pipeline.py --skip-plot
  python run_analysis_pipeline.py tizen --dry-run

Full output of every step goes to logs/<timestamp>_analysis/<os>/NN_<step>.log
(the heatmap goes to logs/<timestamp>_analysis/_combined/plot_heatmap.log)
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
MANAGER_LABELING_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "manager_analysis_labeling.py"
ANALYSIS_LABELING_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "analysis_labeling.py"
LABELING_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "label_experiments.py"
PLOTTING_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "plot_heatmap.py"
VENV_PYTHON = SCRIPTS_FOLDER / "venv" / "bin" / "python"

# manager_analysis.py and manager_analysis_labeling.py exit 0 even when some
# domains fail; this line reveals it.
MANAGER_FAIL_MARKER = "✗ Failed:"


def individual(o: str) -> Path:
    return DATA / "individual_domain_csvs" / o


def volume_csv(o: str) -> Path:
    return DATA / "volume_results" / o / "traffic_volume.csv"


def labeled_csv(o: str) -> Path:
    return DATA / "volume_results" / o / "traffic_volume_labeled.csv"


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


def check_dependencies(download: bool, plot: bool) -> List[str]:
    needed = ["pandas"] + (["requests"] if download else []) + (["matplotlib"] if plot else [])
    return [m for m in needed if importlib.util.find_spec(m) is None]


def preflight(o: str, download: bool, analysis: bool, labeling: bool) -> List[str]:
    problems = []
    scripts = []
    if download:
        scripts.append(SCRIPTS_FOLDER / DOWNLOAD_SCRIPT)
    if analysis:
        scripts += [SCRIPTS_FOLDER / MANAGER_SCRIPT, ANALYSIS_SCRIPT]
    if labeling:
        scripts += [MANAGER_LABELING_SCRIPT, ANALYSIS_LABELING_SCRIPT, LABELING_SCRIPT]
    for s in scripts:
        if not s.exists():
            problems.append(f"script not found: {rel(s)}")
    for p in (DATA / "experiment_timings" / o / "timing.csv", VENV_PYTHON):
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


def show(argv: List[str]) -> str:
    """Command for display: script paths relative to the scripts folder."""
    out = []
    for a in argv:
        p = Path(a)
        out.append(str(p.relative_to(SCRIPTS_FOLDER)) if p.is_absolute() and
                   SCRIPTS_FOLDER in p.parents else a)
    return " ".join(out)


def check_output(key: str, o: str):
    """Extra checks after a step exits 0. Returns (status, note)."""
    if key == "download_csvs":
        n_csv = len(list(individual(o).glob("*.csv")))
        if n_csv == 0:
            return "FAILED", f"no CSV files in {rel(individual(o))} after download"
        return "OK", f"{n_csv} CSV file(s) in {rel(individual(o))}"
    if key == "traffic_volume":
        if not volume_csv(o).exists():
            return "FAILED", f"{rel(volume_csv(o))} was not written"
        return "OK", rel(volume_csv(o))
    if key == "labeling":
        if not labeled_csv(o).exists():
            return "FAILED", f"{rel(labeled_csv(o))} was not written"
        return "OK", rel(labeled_csv(o))
    return "OK", ""


def main():
    parser = argparse.ArgumentParser(
        description="Download per-domain CSVs, run the ACR behavior analysis, label the "
                    "experiments and plot the heatmap for one or more OSes.")
    parser.add_argument("os_names", nargs="*",
                        help="OS folder name(s), e.g. tizen webos; omit to run all OSes")
    parser.add_argument("--skip-download", action="store_true",
                        help="use the CSVs already in data/individual_domain_csvs/<os>/")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="skip manager_analysis.py (time-series / CDF figures)")
    parser.add_argument("--skip-labeling", action="store_true",
                        help="skip traffic volume + On/Off labeling (implies --skip-plot)")
    parser.add_argument("--skip-plot", action="store_true", help="skip the combined heatmap")
    parser.add_argument("--plot-format", default="pdf", help="heatmap format: pdf, png, svg")
    parser.add_argument("--dry-run", action="store_true", help="check inputs and print commands only")
    parser.add_argument("--quiet", action="store_true", help="write step output only to the log files")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="stop at the first failing OS (by default the remaining OSes still run)")
    args = parser.parse_args()

    oses = args.os_names or dataset_oses("csv")
    if not oses:
        parser.error("no OSes found; give OS name(s) explicitly")
    download = not args.skip_download
    analysis = not args.skip_analysis
    labeling = not args.skip_labeling
    plot = labeling and not args.skip_plot

    missing = check_dependencies(download, plot)
    if missing:
        print(f"ERROR: missing Python packages in {sys.executable}: {', '.join(missing)}")
        return 1
    if plot and not PLOTTING_SCRIPT.exists():
        print(f"ERROR: script not found: {rel(PLOTTING_SCRIPT)} (or use --skip-plot)")
        return 1

    steps = []
    if download:
        steps.append(("download_csvs", lambda o: [DOWNLOAD_SCRIPT, "csv", o], ()))
    if analysis:
        steps.append(("analysis", lambda o: [MANAGER_SCRIPT, o], (MANAGER_FAIL_MARKER,)))
    if labeling:
        steps.append(("traffic_volume",
                      lambda o: [str(MANAGER_LABELING_SCRIPT), o,
                                 "--script", ANALYSIS_LABELING_SCRIPT.name],
                      (MANAGER_FAIL_MARKER,)))
        steps.append(("labeling", lambda o: [str(LABELING_SCRIPT), o], ()))
    if not steps:
        parser.error("all steps are skipped; nothing to do")

    def plot_argv(os_list):
        return [str(PLOTTING_SCRIPT), *os_list, "--combined", "--format", args.plot_format]

    log_dir = LOG_ROOT / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_analysis")
    print("=" * 72)
    print("ACR behavior analysis runner")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Interpreter  : {sys.executable}")
    print(f"  OS(es)       : {', '.join(oses)}")
    print(f"  Steps        : {', '.join([k for k, _, _ in steps] + (['plot_heatmap'] if plot else []))}")
    if not args.dry_run:
        print(f"  Logs         : {rel(log_dir)}")
    print("=" * 72)

    summary, any_failure = [], False
    labeled_oses: List[str] = []

    for o in oses:
        print(f"\n##### {o} #####")
        problems = preflight(o, download, analysis, labeling)
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
                print(f"  python {show(argv(o))}")
            labeled_oses.append(o)
            continue

        (log_dir / o).mkdir(parents=True, exist_ok=True)
        os_failed = False
        for n, (key, argv, markers) in enumerate(steps, 1):
            log_path = log_dir / o / f"{n:02d}_{key}.log"
            print(f"\n[{o}] step {n}/{len(steps)}: {key}")
            print(f"[{o}] $ python {show(argv(o))}")
            t0 = time.time()
            rc, seen = run(argv(o), log_path, args.quiet, markers)

            if rc != 0:
                status, note = "FAILED", f"exit code {rc}"
            elif MANAGER_FAIL_MARKER in seen:
                status, note = "FAILED", "one or more domains failed (see log)"
            else:
                status, note = check_output(key, o)

            dt = time.time() - t0
            summary.append((o, key, status, dt, note))
            print(f"[{o}] {key}: {status} in {fmt_duration(dt)}" + (f" ({note})" if note else ""))
            if status == "FAILED":
                print(f"[{o}] see log: {rel(log_path)}")
                os_failed = any_failure = True
                break
            if key == "labeling":
                labeled_oses.append(o)
        if os_failed and args.stop_on_error:
            break

    # ---- combined heatmap over every OS that was labeled successfully
    if plot and not (any_failure and args.stop_on_error):
        print("\n##### combined heatmap #####")
        if not labeled_oses:
            print("No OS was labeled successfully; skipping the heatmap.")
            summary.append(("(all)", "plot_heatmap", "SKIPPED", 0.0, "no labeled OS"))
        elif args.dry_run:
            print(f"  python {show(plot_argv(labeled_oses))}")
        else:
            (log_dir / "_combined").mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "_combined" / "plot_heatmap.log"
            print(f"$ python {show(plot_argv(labeled_oses))}")
            t0 = time.time()
            rc, _ = run(plot_argv(labeled_oses), log_path, args.quiet)
            dt = time.time() - t0
            if rc == 0:
                status, note = "OK", f"{len(labeled_oses)} OS(es)"
            else:
                status, note = "FAILED", f"exit code {rc}"
                any_failure = True
                print(f"see log: {rel(log_path)}")
            summary.append(("(all)", "plot_heatmap", status, dt, note))
            print(f"plot_heatmap: {status} in {fmt_duration(dt)} ({note})")

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