import subprocess
import sys
from pathlib import Path
import argparse
import pandas as pd
import json

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"
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

# Keep for backward compatibility
TV_IP_MAPPING = TV_MAC_MAPPING


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


def run_dns_name_analysis(domain_name, csv_path, input_path, script_path, venv_python, folder_name):
    domain_stats = []
    df = pd.read_csv(csv_path)
    for idx, row in df.iterrows():
        stats = run_for_row(idx+1, row, domain_name, input_path, script_path, venv_python, folder_name)
        if stats:
            domain_stats.append(stats)
    
    return domain_stats
    
    
def run_for_row(index, row, domain_name, input_path, script_path, venv_python, folder_name):
    start_time = str(row["start_time"])
    end_time = str(row["end_time"])
    action_name = str(row["action_name"])
    
    # Get MAC address(es) for this device
    tv_mac = TV_MAC_MAPPING.get(folder_name, "04:e4:b6:74:dd:94")
    
    # Normalize to comma-separated string for subprocess
    tv_mac_str = _normalize_mac_addresses(tv_mac)

    try:
        result = subprocess.run(
            [str(venv_python), str(script_path), str(input_path), start_time, end_time, action_name, domain_name, folder_name, tv_mac_str],
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        try:
            for line in result.stdout.split('\n'):
                if line.strip().startswith('{"domain"'):
                    stats = json.loads(line)
                    return stats
        except (json.JSONDecodeError, ValueError):
            print(f"Warning: Could not parse stats for {domain_name}")
            return None
        
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"ERROR: Failed to analyze {domain_name}")
        print(f"{'='*60}")
        print(f"Command: {' '.join([str(x) for x in e.cmd])}")
        print(f"\nSTDOUT:\n{e.stdout}")
        print(f"\nSTDERR:\n{e.stderr}")
        print(f"{'='*60}\n")
        return None
    
    except subprocess.TimeoutExpired as e:
        print(f"WARNING: Script timed out for {domain_name} after 300 seconds")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run DNS analysis for domains across time periods"
    )
    
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., tizen, webos, roku_roku)"
    )
    parser.add_argument(
        "--timing-file",
        default="timing_ratio.csv",
        help="Timing CSV filename (default: timing_ratio.csv)"
    )
    parser.add_argument(
        "--domain-file",
        default="final_list.csv",
        help="Domain list filename in filtering_results (default: final_list.csv)"
    )
    parser.add_argument(
        "--script",
        default="volume_analysis.py",
        help="Analysis script filename in scripts folder (default: volume_analysis.py)"
    )
    parser.add_argument(
        "--output",
        default="ratio.csv",
        help="Output CSV filename (default: ratio.csv)"
    )
    parser.add_argument(
        "--mac",
        help="Override MAC address(es). Use comma-separated for multiple (e.g., 'aa:bb:cc:dd:ee:ff,11:22:33:44:55:66')"
    )
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    
    # Override MAC if provided via command line
    if args.mac:
        TV_MAC_MAPPING[folder_name] = args.mac
    
    # Construct paths
    timing_csv = DATA_TIMINGS_DIR / folder_name / args.timing_file
    domain_list = DATA_FILTERING_RESULTS_DIR / folder_name / args.domain_file
    input_path = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    script_path = SCRIPT_DIR / args.script
    output_csv = DATA_FILTERING_RESULTS_DIR / folder_name / args.output
    venv_python = SCRIPTS_FOLDER / "venv" / "bin" / "python"
    
    # Verify input files exist
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
    
    # Create output directory if it doesn't exist
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    # Log the MAC address(es) being used
    tv_mac = TV_MAC_MAPPING.get(folder_name, "04:e4:b6:74:dd:94")
    tv_mac_str = _normalize_mac_addresses(tv_mac)
    print(f"\n{'='*60}")
    print(f"Analysis Configuration")
    print(f"{'='*60}")
    print(f"Folder: {folder_name}")
    print(f"MAC Address(es): {tv_mac_str}")
    print(f"Timing File: {timing_csv}")
    print(f"Domain List: {domain_list}")
    print(f"{'='*60}\n")
    
    all_domain_stats = []
    
    dmlist = pd.read_csv(domain_list)
    for idx, rw in dmlist.iterrows():
        domain_name = str(rw["domain"])
        print(f"\n{'='*60}")
        print(f"Processing domain: {domain_name}")
        print(f"{'='*60}")
        
        domain_stats_list = run_dns_name_analysis(domain_name, timing_csv, input_path, script_path, venv_python, folder_name)
        
        if domain_stats_list and len(domain_stats_list) > 0:
            total_outgoing = sum(s.get('outgoing_bytes', 0) for s in domain_stats_list)
            total_incoming = sum(s.get('incoming_bytes', 0) for s in domain_stats_list)
            
            domain_entry = {
                'domain': domain_name,
                'total_outgoing_bytes': total_outgoing,
                'total_incoming_bytes': total_incoming,
                'outgoing_gt_incoming': total_outgoing > total_incoming,
                'num_periods': len(domain_stats_list)
            }
            all_domain_stats.append(domain_entry)
            
            print(f"Domain: {domain_name}")
            print(f"  Total Outgoing: {total_outgoing:,} bytes")
            print(f"  Total Incoming: {total_incoming:,} bytes")
            print(f"  Outgoing > Incoming: {total_outgoing > total_incoming}")
        else:
            print(f"⚠️  Skipped {domain_name} (no stats collected)")
    
    if all_domain_stats:
        stats_df = pd.DataFrame(all_domain_stats)
        filtered_df = stats_df[stats_df['outgoing_gt_incoming']].copy()
        
        output_df = filtered_df[['domain']].reset_index(drop=True)
        
        output_df.to_csv(output_csv, index=False)
        
        print(f"\n{'='*60}")
        print(f"✅ Results Summary")
        print(f"{'='*60}")
        print(f"Total domains analyzed: {len(stats_df)}")
        print(f"Domains with outgoing > incoming: {len(filtered_df)}")
        print(f"\n📊 Output saved to: {output_csv}")
        print(f"\nDomains with outgoing > incoming bytes:")
        for domain in output_df['domain'].tolist():
            print(f"  - {domain}")
    else:
        print("ERROR: No domain statistics collected")
        sys.exit(1)