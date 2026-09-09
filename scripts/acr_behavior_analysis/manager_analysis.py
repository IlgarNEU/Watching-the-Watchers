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
DATA_PERIODICITY_RESULTS_DIR = PROJECT_ROOT / "data" / "periodicity_results"
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"

# TV name to MAC address mapping
# Format: Single MAC as string, or multiple MACs as list
TV_MAC_MAPPING = {
    "tizen": "04:e4:b6:74:dd:94",
    "webos": "00:a1:59:8f:ab:38",
    "roku_roku": "34:5e:08:b1:b3:be",
    "roku_tcl": "c4:8b:66:60:86:02",
    "google": ["58:18:62:30:2f:eb", "4e:cb:9c:2d:bb:89"],
    "fire": ["28:73:f6:20:a6:35", "28:73:f6:20:b6:95"],
    "smartcast": "14:c6:7d:15:31:56",
    "xumo": "b8:41:d9:e4:f8:ed",
    "google_tcl": "48:87:b8:ab:34:37",
    
    # Example: Device with multiple MACs
    # "samsung": ["04:e4:b6:74:dd:94", "a8:5e:60:12:34:56"],
}


def _normalize_mac_addresses(mac_input):
    """
    Convert MAC input to comma-separated string for subprocess.
    
    Args:
        mac_input: Single MAC string or list of MAC strings
        
    Returns:
        Comma-separated string of MACs
    """
    if isinstance(mac_input, str):
        return mac_input
    elif isinstance(mac_input, (list, tuple)):
        return ','.join(str(m).strip() for m in mac_input)
    else:
        return str(mac_input)


def get_domain_list_path(folder_name, primary_file, fallback_file):
    """
    Try to use primary file first, fall back to fallback file if primary doesn't exist or is empty.
    Returns the path to use and a description of which file was selected.
    """
    primary_path = DATA_PERIODICITY_RESULTS_DIR / folder_name / primary_file
    fallback_path = DATA_FILTERING_RESULTS_DIR / folder_name / fallback_file
    
    # Check primary file
    if primary_path.exists():
        try:
            df = pd.read_csv(primary_path)
            if len(df) > 0:
                return primary_path, f"Using primary domain list: {primary_file}"
        except Exception as e:
            print(f"Warning: Could not read {primary_file}: {e}")
    
    # Fall back to fallback file
    if fallback_path.exists():
        try:
            df = pd.read_csv(fallback_path)
            if len(df) > 0:
                return fallback_path, f"Primary domain list not found/empty. Using fallback: {fallback_file}"
        except Exception as e:
            print(f"Warning: Could not read {fallback_file}: {e}")
    
    # Neither file exists or both are empty
    raise FileNotFoundError(
        f"No valid domain list found. "
        f"Tried: {primary_path} and {fallback_path}"
    )


def run_dns_name_analysis(domain_name, csv_path, input_path, script_path, venv_python, folder_name, tv_mac):
    """
    Run analysis for a domain across all time periods defined in the CSV.
    """
    df = pd.read_csv(csv_path)
    for idx, row in df.iterrows():
        run_for_row(idx+1, row, domain_name, input_path, script_path, venv_python, folder_name, tv_mac)
    
    
def run_for_row(index, row, domain_name, input_path, script_path, venv_python, folder_name, tv_mac):
    start_time = str(row["start_time"])
    end_time = str(row["end_time"])
    action_name = str(row["action_name"])

    try:
        subprocess.run(
            [str(venv_python), str(script_path), str(input_path), start_time, end_time, action_name, domain_name, folder_name, tv_mac],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Failed to process {domain_name} for {action_name}")
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run analysis for domains across time periods"
    )
    
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., tizen, google, fire)"
    )
    parser.add_argument(
        "--timing-file",
        default="timing.csv",
        help="Timing CSV filename (default: timing.csv)"
    )
    parser.add_argument(
        "--domain-file",
        default="periodic_domains.csv",
        help="Domain list filename in periodicity_results (default: periodic_domains.csv)"
    )
    parser.add_argument(
        "--fallback-domain-file",
        default="ratio.csv",
        help="Fallback domain list filename in filtering_results (default: ratio.csv)"
    )
    parser.add_argument(
        "--script",
        default="analysis.py",
        help="Analysis script filename in scripts folder (default: analysis.py)"
    )
    parser.add_argument(
        "--mac",
        default=None,
        help="Override TV MAC address(es). Use comma-separated for multiple (e.g., 'aa:bb:cc:dd:ee:ff,11:22:33:44:55:66')"
    )
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    
    # Get TV MAC from mapping, or use provided override
    if args.mac:
        tv_mac = args.mac
        print(f"Using custom TV MAC(s): {tv_mac}")
    elif folder_name in TV_MAC_MAPPING:
        tv_mac_raw = TV_MAC_MAPPING[folder_name]
        tv_mac = _normalize_mac_addresses(tv_mac_raw)
        print(f"Using TV MAC(s) for '{folder_name}': {tv_mac}")
    else:
        tv_mac = "04:e4:b6:74:dd:94"
        print(f"Warning: TV model '{folder_name}' not found in mapping. Using default MAC.")
    
    # Get domain list with fallback
    try:
        domain_list, domain_list_note = get_domain_list_path(
            folder_name, 
            args.domain_file, 
            args.fallback_domain_file
        )
        print(domain_list_note)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    # Construct paths
    timing_csv = DATA_TIMINGS_DIR / folder_name / args.timing_file
    input_path = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    script_path = SCRIPT_DIR / args.script
    venv_python = SCRIPTS_FOLDER / "venv" / "bin" / "python"
    
    # Validate input files exist
    for path_arg, path_name in [
        (timing_csv, "timing CSV"),
        (domain_list, "domain list"),
        (input_path, "input domain CSVs directory"),
        (script_path, "analysis script"),
        (venv_python, "venv python")
    ]:
        if not path_arg.exists():
            print(f"ERROR: {path_name} not found: {path_arg}")
            sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Processing domains from: {domain_list}")
    print(f"Timing file: {timing_csv}")
    print(f"Input directory: {input_path}")
    print(f"Script: {script_path}")
    print(f"TV MAC(s): {tv_mac}")
    print(f"{'='*60}\n")
    
    dmlist = pd.read_csv(domain_list)
    total = len(dmlist)
    successful = 0
    failed = 0
    
    for idx, rw in dmlist.iterrows():
        domain_name = str(rw["domain"])
        print(f"[{idx+1}/{total}] Processing domain: {domain_name}...", end=" ", flush=True)
        try:
            run_dns_name_analysis(domain_name, timing_csv, input_path, script_path, venv_python, folder_name, tv_mac)
            print("✓")
            successful += 1
        except Exception as e:
            print(f"✗")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"✓ Completed: {successful}/{total} domain(s) processed successfully")
    if failed > 0:
        print(f"✗ Failed: {failed} domain(s)")
    print(f"{'='*60}")