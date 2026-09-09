import subprocess
import sys
from pathlib import Path
import argparse
import pandas as pd

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"


def run_dns_name_analysis(domain_name, timing_csv, input_path, script_path, venv_python, folder_name):
    """
    Run analysis for a domain across all time periods defined in the CSV.
    """
    df = pd.read_csv(timing_csv)
    print(f"Processing {len(df)} time periods...\n")
    
    for idx, row in df.iterrows():
        run_for_row(idx+1, row, domain_name, input_path, script_path, venv_python, folder_name)
    
    
def run_for_row(index, row, domain_name, input_path, script_path, venv_python, folder_name):
    start_time = str(row["start_time"])
    end_time = str(row["end_time"])
    action_name = str(row["action_name"])

    try:
        subprocess.run(
            [str(venv_python), str(script_path), str(input_path), start_time, end_time, action_name, domain_name, "--device", folder_name],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to process for {action_name}: {e}")
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run analysis across time periods"
    )
    
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., samsung)"
    )
    parser.add_argument(
        "--domain",
        default="216.183.117.80",
        help="Domain name or identifier (default: 216.183.117.80)"
    )
    parser.add_argument(
        "--timing-file",
        default="timing.csv",
        help="Timing CSV filename (default: timing.csv)"
    )
    parser.add_argument(
        "--script",
        default="analyze_traffic.py",
        help="Analysis script filename in scripts folder (default: analyze_traffic.py)"
    )
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    domain_name = args.domain
    
    # Construct paths
    timing_csv = DATA_TIMINGS_DIR / folder_name / args.timing_file
    input_path = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    script_path = SCRIPT_DIR / args.script
    venv_python = SCRIPTS_FOLDER / "venv" / "bin" / "python"
    
    # Verify input files exist
    for path_arg, path_name in [
        (timing_csv, "timing CSV"),
        (input_path, "input directory"),
        (script_path, "analysis script"),
        (venv_python, "venv python")
    ]:
        if not path_arg.exists():
            print(f"ERROR: {path_name} not found: {path_arg}")
            sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Timing CSV: {timing_csv}")
    print(f"Input directory: {input_path}")
    print(f"Analysis script: {script_path}")
    print(f"Domain: '{domain_name}'")
    print(f"Device: {folder_name}")
    print(f"{'='*60}\n")
    
    run_dns_name_analysis(domain_name, timing_csv, input_path, script_path, venv_python, folder_name)
    
    print(f"\n✓ Completed analysis")