#!/usr/bin/env python3
"""
run_processing_pipeline.py

Runs the full dataset pipeline end-to-end for a given data type + TV brand:

  1. download_dataset.py            <data_type> <tv_brand>
  2. renamePcapsFromIotSystem.py    <tv_brand>
  3. runSniPcapToCsv.py             <tv_brand>
  4. mergeCsvs.py                   <tv_brand>

Usage:
  python run_pipeline.py <data_type> <tv_brand>
  python run_pipeline.py pcaps test_pcaps

Options:
  --skip-download     Skip step 1 (use if data is already downloaded)
  --from-step N       Start from step N (1=download, 2=rename, 3=pcap->csv, 4=merge)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


STEPS = [
    ("Download dataset",        "download_dataset.py",             lambda dt, brand: [dt, brand]),
    ("Rename pcaps",             "renamePcapsFromIotSystem.py",      lambda dt, brand: [brand]),
    ("Convert pcaps to CSV",     "runSniPcapToCsv.py",               lambda dt, brand: [brand]),
    ("Merge CSVs to parquet",    "mergeCsvs.py",                     lambda dt, brand: [brand]),
]


def run_step(step_name, script_name, args):
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path), *args]

    print("\n" + "=" * 70)
    print(f"STEP: {step_name}")
    print(f"CMD:  {' '.join(cmd)}")
    print("=" * 70 + "\n")

    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n✗ Step '{step_name}' failed (exit code {result.returncode}, {elapsed:.1f}s)")
        return False

    print(f"\n✓ Step '{step_name}' completed in {elapsed:.1f}s")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Run the full pcap -> csv -> parquet pipeline for a given TV brand",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("data_type", help="Data type to download (e.g. pcaps)")
    parser.add_argument("tv_brand", help="TV brand / folder name (e.g. test_pcaps, samsung)")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip the download step (data already present locally)"
    )
    parser.add_argument(
        "--from-step", type=int, default=1, choices=[1, 2, 3, 4],
        help="Start from step N (1=download, 2=rename, 3=pcap->csv, 4=merge)"
    )
    args = parser.parse_args()

    steps_to_run = STEPS[args.from_step - 1:]
    if args.skip_download:
        steps_to_run = [s for s in steps_to_run if s[1] != "download_dataset.py"]

    if not steps_to_run:
        print("Nothing to run (check --from-step / --skip-download).")
        sys.exit(1)

    overall_start = time.time()

    for step_name, script_name, arg_builder in steps_to_run:
        ok = run_step(step_name, script_name, arg_builder(args.data_type, args.tv_brand))
        if not ok:
            print("\nPipeline aborted — fix the error above and re-run.")
            print(f"Tip: resume with --from-step to skip completed steps.")
            sys.exit(1)

    total = time.time() - overall_start
    print("\n" + "#" * 70)
    print(f"✓ Pipeline completed successfully for '{args.tv_brand}' in {total / 60:.1f} min")
    print("#" * 70)


if __name__ == "__main__":
    main()