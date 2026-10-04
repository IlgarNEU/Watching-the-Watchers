#!/usr/bin/env python3
"""
run_pipeline.py - One-command reproduction of the ACR endpoint analysis pipeline.

Examples
--------
  python run_pipeline.py tizen                     # download data + full pipeline for one OS
  python run_pipeline.py tizen webos roku_roku     # several OSes, one after another
  python run_pipeline.py --all                     # every OS with data/parquets/<os>/merged_all.parquet
  python run_pipeline.py tizen --from-step quantify     # resume from a step
  python run_pipeline.py tizen --only periodicity       # run a single step
  python run_pipeline.py tizen --redownload       # re-download even if the parquet is present
  python run_pipeline.py tizen --dry-run           # check inputs and print commands only
  python run_pipeline.py --list-steps              # show the steps and their keys

Every step's full output is written to logs/<timestamp>/<os>/NN_<step>.log
under the project root, and a summary is printed at the end. The exit code
is non-zero if any step failed.
"""

import argparse
import csv
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Set


def _find_scripts_folder() -> Path:
    """The scripts/ folder is the nearest folder (this file's own folder or a
    parent) that contains both filter_endpoints/ and acr_behavior_analysis/,
    so this runner works from scripts/ or from scripts/filter_endpoints/."""
    here = Path(__file__).resolve().parent
    for d in (here, *here.parents):
        if (d / "filter_endpoints").is_dir() and (d / "acr_behavior_analysis").is_dir():
            return d
    sys.exit(f"ERROR: could not find the scripts/ folder (containing filter_endpoints/ and "
             f"acr_behavior_analysis/) at or above {here}")


SCRIPTS_FOLDER = _find_scripts_folder()
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA = PROJECT_ROOT / "data"
LOG_ROOT = PROJECT_ROOT / "logs"


def timing(o: str, name: str) -> Path:
    return DATA / "experiment_timings" / o / name


def parquet(o: str) -> Path:
    return DATA / "parquets" / o / "merged_all.parquet"


def domain_lists(o: str) -> Path:
    return DATA / "domain_list_csvs" / o


def results(o: str, name: str) -> Path:
    return DATA / "filtering_results" / o / name


def individual(o: str) -> Path:
    return DATA / "individual_domain_csvs" / o


def periodicity(o: str, name: str) -> Path:
    return DATA / "periodicity_results" / o / name


REFERENCE_DOMAINS = DATA / "reference" / "reference_domains.csv"
VENV_PYTHON = SCRIPTS_FOLDER / "venv" / "bin" / "python"
VOLUME_SCRIPT = SCRIPTS_FOLDER / "acr_behavior_analysis" / "volume_analysis.py"


GENERATED_DIRS = [
    lambda o: DATA / "domain_list_csvs" / o,
    lambda o: DATA / "ip_to_dns_mappings" / o,
    lambda o: DATA / "filtering_results" / o,
    lambda o: DATA / "individual_domain_csvs" / o,
    lambda o: DATA / "periodicity_results" / o,
]

CROSSOS_NO_MATCH = "No matching domains found"



@dataclass
class Step:
    key: str
    script: str                                  # relative to SCRIPTS_FOLDER
    description: str
    requires: Callable[[str], List[Path]]        # files/dirs the step reads
    produces: Callable[[str], List[Path]]        # files/dirs that must exist afterwards
    args: Callable[[str], List[str]] = lambda o: [o]
    fail_markers: tuple = ()                     # output text that means failure even with exit code 0
    watch_markers: tuple = ()                    # output text passed to the post hook
    post: Optional[Callable[[str, Set[str]], Optional[str]]] = None
    skip_if: Optional[Callable[[str], Optional[str]]] = None   # returns a reason to skip, or None


def crossos_post(o: str, seen: Set[str]) -> Optional[str]:
    """crossOS_filtering_from_list.py writes no file when nothing overlaps the
    reference list. In that case the filtered list equals the unfiltered one,
    so we copy it to let create_the_final_domain_list.py run."""
    if CROSSOS_NO_MATCH in seen:
        src = results(o, "frequent_domains_top.csv")
        dst = results(o, "frequent_domains_top_filtered.csv")
        shutil.copyfile(src, dst)
        return (f"no domain overlapped the reference list; copied {src.name} -> "
                f"{dst.name} (identical content) so the next step can run")
    return None


def parquet_already_present(o: str) -> Optional[str]:
    """Skip the download when a readable merged_all.parquet already exists.
    Reading the footer catches files truncated by an interrupted download."""
    p = parquet(o)
    if not p.is_file():
        return None
    try:
        import pyarrow.parquet as pq
        pq.read_metadata(p)
    except Exception:
        return None
    return f"{rel(p)} already present ({p.stat().st_size / 1024**3:.2f} GB); use --redownload to fetch again"


STEPS: List[Step] = [
    Step(
        key="download",
        script="data_processing/download_dataset.py",
        description="Download the capture parquet for this OS",
        requires=lambda o: [],
        produces=lambda o: [parquet(o)],
        args=lambda o: ["parquets", o],
        skip_if=parquet_already_present,
    ),
    Step(
        key="domains",
        script="filter_endpoints/domain_analysis_by_ip_and_sni.py",
        description="Map contacted IPs to domains (DNS + SNI) for each experiment window",
        requires=lambda o: [parquet(o), timing(o, "timing.csv")],
        produces=lambda o: [DATA / "ip_to_dns_mappings" / o / "ip_to_dns_mapping.csv",
                            domain_lists(o)],
    ),
    Step(
        key="mixed",
        script="filter_endpoints/mixed_domain_analysis_by_ip_and_sni.py",
        description="Same mapping for the mixed-usage windows",
        requires=lambda o: [parquet(o), timing(o, "mixed_timing.csv")],
        produces=lambda o: [domain_lists(o) / "MIXED.csv"],
    ),
    Step(
        key="filter",
        script="filter_endpoints/filter_domains.py",
        description="Remove well-known content/service domains",
        requires=lambda o: [domain_lists(o) / "MIXED.csv"],
        produces=lambda o: [results(o, "well-known-services-filtered.csv")],
    ),
    Step(
        key="group",
        script="filter_endpoints/group_base_domains.py",
        description="Group domains by base domain",
        requires=lambda o: [results(o, "well-known-services-filtered.csv")],
        produces=lambda o: [results(o, "grouped_by_base.csv")],
    ),
    Step(
        key="quantify",
        script="filter_endpoints/quantify_domain_existence.py",
        description="Measure how often each base domain appears in ACR=ON windows",
        requires=lambda o: [timing(o, "timing.csv"), results(o, "grouped_by_base.csv"),
                            domain_lists(o)],
        produces=lambda o: [results(o, "all_domains_summary.csv"),
                            results(o, "frequent_domains_top.csv")],
    ),
    Step(
        key="crossos",
        script="filter_endpoints/crossOS_filtering_from_list.py",
        description="Remove domains that appear in the cross-OS reference list",
        requires=lambda o: [results(o, "frequent_domains_top.csv"), REFERENCE_DOMAINS],
        produces=lambda o: [results(o, "frequent_domains_top_filtered.csv")],
        fail_markers=("✗ Error",),
        watch_markers=(CROSSOS_NO_MATCH,),
        post=crossos_post,
    ),
    Step(
        key="final",
        script="filter_endpoints/create_the_final_domain_list.py",
        description="Expand the surviving base domains back to full domains",
        requires=lambda o: [results(o, "well-known-services-filtered.csv"),
                            results(o, "frequent_domains_top_filtered.csv")],
        produces=lambda o: [results(o, "final_list.csv")],
    ),
    Step(
        key="acrfiles",
        script="acr_behavior_analysis/acrfileCreation.py",
        description="Extract per-domain traffic CSVs from the parquet",
        requires=lambda o: [parquet(o), results(o, "final_list.csv")],
        produces=lambda o: [individual(o)],
    ),
    Step(
        key="volume",
        script="acr_behavior_analysis/manager_volume_analysis.py",
        description="Keep domains whose outgoing bytes exceed incoming bytes",
        requires=lambda o: [timing(o, "timing_ratio.csv"), results(o, "final_list.csv"),
                            individual(o), VOLUME_SCRIPT, VENV_PYTHON],
        produces=lambda o: [results(o, "ratio.csv")],
    ),
    Step(
        key="periodicity",
        script="filter_endpoints/periodicity_analysis.py",
        description="Detect periodic traffic for the remaining domains",
        requires=lambda o: [results(o, "ratio.csv"), individual(o),
                            timing(o, "timing_periodicity.csv")],
        produces=lambda o: [periodicity(o, "summary_all_domains.csv"),
                            periodicity(o, "periodic_domains.csv")],
    ),
]

STEP_KEYS = [s.key for s in STEPS]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def resolve_step(token: str) -> int:
    """Accept a step key ('quantify') or a 1-based number ('5')."""
    if token.isdigit() and 1 <= int(token) <= len(STEPS):
        return int(token) - 1
    if token in STEP_KEYS:
        return STEP_KEYS.index(token)
    raise SystemExit(f"Unknown step '{token}'. Valid steps: {', '.join(STEP_KEYS)} (or 1-{len(STEPS)})")


def select_steps(args) -> List[Step]:
    if args.only:
        idx = sorted({resolve_step(t) for t in args.only})
        return [STEPS[i] for i in idx]
    start = resolve_step(args.from_step) if args.from_step else 0
    end = resolve_step(args.to_step) if args.to_step else len(STEPS) - 1
    if start > end:
        raise SystemExit("--from-step comes after --to-step")
    return STEPS[start:end + 1]


def discover_oses() -> List[str]:
    """OSes with experiment timings (shipped with the artifact) or an existing parquet."""
    found = set()
    for base in (DATA / "experiment_timings", DATA / "parquets"):
        if base.is_dir():
            found.update(d.name for d in base.iterdir() if d.is_dir())
    return sorted(found)


def count_rows(path: Path) -> Optional[int]:
    if not path.is_file():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def check_dependencies(steps: List[Step]) -> List[str]:
    needed = ["pandas", "numpy", "scipy", "matplotlib"]
    if any(s.key == "download" for s in steps):
        needed.append("requests")
    missing = [m for m in needed if importlib.util.find_spec(m) is None]
    if importlib.util.find_spec("pyarrow") is None and importlib.util.find_spec("fastparquet") is None:
        missing.append("pyarrow (or fastparquet)")
    return missing


def preflight(steps: List[Step], o: str) -> List[str]:
    """Report inputs that are neither present nor produced by an earlier selected step."""
    problems, produced = [], set()
    for s in steps:
        script = SCRIPTS_FOLDER / s.script
        if not script.exists():
            problems.append(f"[{s.key}] script not found: {rel(script)}")
        for r in s.requires(o):
            if r not in produced and not r.exists():
                problems.append(f"[{s.key}] missing input: {rel(r)}")
        produced.update(s.produces(o))
    return problems


def run_step(step: Step, o: str, log_path: Path, quiet: bool):
    cmd = [sys.executable, "-u", str(SCRIPTS_FOLDER / step.script), *step.args(o)]
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
    markers = step.fail_markers + step.watch_markers
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
                for m in markers:
                    if m in line:
                        seen.add(m)
            rc = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            raise
        log.write(f"\n# exit code: {rc}\n")
    return rc, seen


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Run the full ACR endpoint analysis pipeline for one or more TV OSes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Steps: " + ", ".join(f"{i}={k}" for i, k in enumerate(STEP_KEYS, 1)),
    )
    parser.add_argument("os_names", nargs="*", help="OS folder name(s), e.g. tizen webos")
    parser.add_argument("--all", action="store_true",
                        help="run every OS found in data/experiment_timings/ or data/parquets/")
    parser.add_argument("--redownload", action="store_true",
                        help="download the parquet even if a valid one is already present")
    parser.add_argument("--from-step", metavar="STEP", help="start at this step (key or number)")
    parser.add_argument("--to-step", metavar="STEP", help="stop after this step (key or number)")
    parser.add_argument("--only", nargs="+", metavar="STEP", help="run only these step(s)")
    parser.add_argument("--fresh", action="store_true",
                        help="delete previously generated outputs for the OS before a full run")
    parser.add_argument("--dry-run", action="store_true", help="check inputs and print commands only")
    parser.add_argument("--quiet", action="store_true", help="write step output only to the log files")
    parser.add_argument("--keep-going", action="store_true",
                        help="if an OS fails, continue with the next OS instead of stopping")
    parser.add_argument("--list-steps", action="store_true", help="list the pipeline steps and exit")
    args = parser.parse_args()

    if args.list_steps:
        for i, s in enumerate(STEPS, 1):
            print(f"{i:2d}. {s.key:<12} {s.script}\n    {s.description}")
        return 0

    oses = discover_oses() if args.all else args.os_names
    if not oses:
        parser.error("give at least one OS name, or use --all")

    steps = select_steps(args)
    if args.fresh and steps[0].key not in ("download", "domains"):
        parser.error("--fresh deletes all generated outputs, so it can only be used for a full run "
                     "(starting at 'download' or 'domains')")

    missing_deps = check_dependencies(steps)
    if missing_deps:
        print(f"ERROR: missing Python packages in {sys.executable}: {', '.join(missing_deps)}")
        return 1

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = LOG_ROOT / run_id
    print("=" * 72)
    print("ACR pipeline runner")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Interpreter  : {sys.executable}")
    print(f"  OS(es)       : {', '.join(oses)}")
    print(f"  Steps        : {', '.join(s.key for s in steps)}")
    if not args.dry_run:
        print(f"  Logs         : {rel(log_dir)}")
    print("=" * 72)

    summary = []          # (os, step, status, seconds, note)
    any_failure = False

    for o in oses:
        print(f"\n##### {o} #####")
        problems = preflight(steps, o)
        if problems:
            print("Pre-flight check failed:")
            for p in problems:
                print(f"  - {p}")
            summary.append((o, "preflight", "FAILED", 0.0, f"{len(problems)} missing input(s)"))
            any_failure = True
            if args.keep_going:
                continue
            break

        if args.dry_run:
            print("Pre-flight check passed. Commands that would run (cwd = scripts folder):")
            for s in steps:
                reason = None if args.redownload or not s.skip_if else s.skip_if(o)
                tag = f"   # skipped: {reason}" if reason else ""
                print(f"  python {s.script} {' '.join(s.args(o))}{tag}")
            continue

        if args.fresh:
            for d in (f(o) for f in GENERATED_DIRS):
                if d.exists():
                    shutil.rmtree(d)
                    print(f"  removed {rel(d)}")

        os_log_dir = log_dir / o
        os_log_dir.mkdir(parents=True, exist_ok=True)
        os_failed = False

        for s in steps:
            n = STEP_KEYS.index(s.key) + 1
            log_path = os_log_dir / f"{n:02d}_{s.key}.log"
            print(f"\n[{o}] step {n}/{len(STEPS)}: {s.key} - {s.description}")
            reason = None if args.redownload or not s.skip_if else s.skip_if(o)
            if reason:
                print(f"[{o}] {s.key}: SKIPPED ({reason})")
                summary.append((o, s.key, "SKIPPED", 0.0, reason))
                continue
            print(f"[{o}] $ python {s.script} {' '.join(s.args(o))}")

            t0 = time.time()
            rc, seen = run_step(s, o, log_path, args.quiet)
            notes = []

            if rc == 0 and s.post:
                note = s.post(o, seen)
                if note:
                    notes.append(note)

            status = "OK"
            if rc != 0:
                status = "FAILED"
                notes.append(f"exit code {rc}")
            elif any(m in seen for m in s.fail_markers):
                status = "FAILED"
                notes.append("script reported an error")
            else:
                for p in s.produces(o):
                    if not p.exists():
                        status = "FAILED"
                        notes.append(f"expected output missing: {rel(p)}")
                    elif p.is_file() and p.stat().st_mtime < t0:
                        notes.append(f"reused existing {p.name} (not rewritten this run)")

            dt = time.time() - t0
            summary.append((o, s.key, status, dt, "; ".join(notes)))
            print(f"[{o}] {s.key}: {status} in {fmt_duration(dt)}"
                  + (f" ({'; '.join(notes)})" if notes else ""))

            if status == "FAILED":
                print(f"[{o}] see log: {rel(log_path)}")
                os_failed = any_failure = True
                break

        if os_failed and not args.keep_going:
            break

    # ---------------- summary ----------------
    if args.dry_run:
        return 1 if any_failure else 0

    print("\n" + "=" * 72)
    print("Summary")
    print("=" * 72)
    for o, key, status, dt, note in summary:
        print(f"  {o:<22} {key:<12} {status:<7} {fmt_duration(dt):>9}  {note}")

    print("\nResult files:")
    for o in oses:
        outs = [("final_list.csv", results(o, "final_list.csv")),
                ("ratio.csv", results(o, "ratio.csv")),
                ("periodic_domains.csv", periodicity(o, "periodic_domains.csv"))]
        counts = [(name, count_rows(p)) for name, p in outs]
        shown = ", ".join(f"{name}: {c} domain(s)" for name, c in counts if c is not None)
        print(f"  {o:<22} {shown or 'no results yet'}")

    print(f"\nLogs: {rel(log_dir)}")
    return 1 if any_failure else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)