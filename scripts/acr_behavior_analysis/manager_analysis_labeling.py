import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"
DATA_PERIODICITY_RESULTS_DIR = PROJECT_ROOT / "data" / "periodicity_results"
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"
DATA_VOLUME_RESULTS_DIR = PROJECT_ROOT / "data" / "volume_results"

TV_MAC_MAPPING = {
    "tizen": "04:e4:b6:74:dd:94",
    "webos": "00:a1:59:8f:ab:38",
    "roku_roku": "34:5e:08:b1:b3:be",
    "roku_tcl": "c4:8b:66:60:86:02",
    "google": ["58:18:62:30:2f:eb", "4e:cb:9c:2d:bb:89"],
    "fire": ["28:73:f6:20:a6:35", "28:73:f6:20:ba:95"],
    "smartcast": "14:c6:7d:15:31:56",
    "xumo": "b8:41:d9:e4:f8:ed",
    "google_tcl": "48:87:b8:ab:34:37",
}

DEFAULT_DOMAIN_MAPPING = {
    "tizen": "acr-us-prd.samsungcloud.tv",
    "webos": "tkacr",
    "roku_roku": "scribe.logs.roku.com",
    "roku_tcl": "scribe.logs.roku.com",
    "google": "216.183.117.80",
    "fire": "gateway-ink.amazon.com",
    "smartcast": "kinesis.us-west-2.amazonaws.com",
}
GENERIC_DEFAULT_DOMAIN = "acr-us-prd.samsungcloud.tv"

OUTPUT_COLUMNS = [
    "tv_model", "domain", "action_name",
    "start_time", "end_time", "effective_start", "duration_seconds",
    "outgoing_bytes", "outgoing_packets", "outgoing_bytes_per_sec",
    "incoming_bytes", "incoming_packets", "incoming_bytes_per_sec",
    "total_bytes", "total_packets",
    "status",
]


def get_default_domain(folder_name):
    return DEFAULT_DOMAIN_MAPPING.get(folder_name, GENERIC_DEFAULT_DOMAIN)


def _normalize_mac_addresses(mac_input):
    if isinstance(mac_input, str):
        return mac_input
    if isinstance(mac_input, (list, tuple)):
        return ",".join(str(m).strip() for m in mac_input)
    return str(mac_input)


def get_domain_list_path(folder_name, primary_file, fallback_file):
    primary_path = DATA_PERIODICITY_RESULTS_DIR / folder_name / primary_file
    fallback_path = DATA_FILTERING_RESULTS_DIR / folder_name / fallback_file

    if primary_path.exists():
        try:
            if len(pd.read_csv(primary_path)) > 0:
                return primary_path, f"Using primary domain list: {primary_file}"
        except Exception as e:
            print(f"Warning: Could not read {primary_file}: {e}")

    if fallback_path.exists():
        try:
            if len(pd.read_csv(fallback_path)) > 0:
                return fallback_path, f"Primary domain list not found/empty. Using fallback: {fallback_file}"
        except Exception as e:
            print(f"Warning: Could not read {fallback_file}: {e}")

    return None, (
        f"No domain list found for '{folder_name}' "
        f"(tried {primary_path} and {fallback_path}). Falling back to default domain."
    )


def run_for_row(row, domain_name, input_path, script_path, venv_python,
                folder_name, tv_mac, skip_minutes):
    """Run analysis.py for one (domain, window) and return its result as a dict."""
    start_time = str(row["start_time"])
    end_time = str(row["end_time"])
    action_name = str(row["action_name"])

    base = {
        "tv_model": folder_name,
        "domain": domain_name,
        "action_name": action_name,
        "start_time": start_time,
        "end_time": end_time,
    }

    cmd = [
        str(venv_python), str(script_path), str(input_path),
        start_time, end_time, action_name, domain_name, folder_name, tv_mac,
        "--skip-minutes", str(skip_minutes),
    ]

    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Failed to process {domain_name} for {action_name}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        return {**base, "status": "error"}
    except (json.JSONDecodeError, IndexError):
        print(f"\nERROR: Unparseable output for {domain_name} / {action_name}")
        return {**base, "status": "error"}


def write_results(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).reindex(columns=OUTPUT_COLUMNS).to_csv(output_path, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute traffic volume per domain per experiment window and save to CSV"
    )
    parser.add_argument("folder_name", help="TV model folder name (e.g., tizen, google, fire)")
    parser.add_argument("--timing-file", default="timing.csv")
    parser.add_argument("--domain-file", default="periodic_domains.csv")
    parser.add_argument("--fallback-domain-file", default="ratio.csv")
    parser.add_argument("--script", default="analysis.py")
    parser.add_argument("--mac", default=None,
                        help="Override TV MAC address(es), comma-separated for multiple")
    parser.add_argument("--skip-minutes", type=float, default=5.0,
                        help="Minutes to skip at the start of each window (default: 5)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: data/volume_results/<folder>/traffic_volume.csv)")
    args = parser.parse_args()

    folder_name = args.folder_name

    if args.mac:
        tv_mac = args.mac
        print(f"Using custom TV MAC(s): {tv_mac}")
    elif folder_name in TV_MAC_MAPPING:
        tv_mac = _normalize_mac_addresses(TV_MAC_MAPPING[folder_name])
        print(f"Using TV MAC(s) for '{folder_name}': {tv_mac}")
    else:
        tv_mac = "04:e4:b6:74:dd:94"
        print(f"Warning: TV model '{folder_name}' not found in mapping. Using default MAC.")

    domain_list, domain_list_note = get_domain_list_path(
        folder_name, args.domain_file, args.fallback_domain_file
    )
    print(domain_list_note)

    timing_csv = DATA_TIMINGS_DIR / folder_name / args.timing_file
    input_path = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    script_path = SCRIPT_DIR / args.script
    venv_python = SCRIPTS_FOLDER / "venv" / "bin" / "python"
    output_path = Path(args.output) if args.output else \
        DATA_VOLUME_RESULTS_DIR / folder_name / "traffic_volume.csv"

    required_paths = [
        (timing_csv, "timing CSV"),
        (input_path, "input domain CSVs directory"),
        (script_path, "analysis script"),
        (venv_python, "venv python"),
    ]
    if domain_list is not None:
        required_paths.append((domain_list, "domain list"))

    for path_arg, path_name in required_paths:
        if not path_arg.exists():
            print(f"ERROR: {path_name} not found: {path_arg}")
            sys.exit(1)

    if domain_list is not None:
        domains = [str(d) for d in pd.read_csv(domain_list)["domain"]]
    else:
        domains = [get_default_domain(folder_name)]

    timings = pd.read_csv(timing_csv)

    print(f"\n{'=' * 60}")
    print(f"Domains from:  {domain_list if domain_list is not None else '(default domain)'}")
    print(f"Timing file:   {timing_csv} ({len(timings)} windows)")
    print(f"Input dir:     {input_path}")
    print(f"TV MAC(s):     {tv_mac}")
    print(f"Skip minutes:  {args.skip_minutes}")
    print(f"Output CSV:    {output_path}")
    print(f"{'=' * 60}\n")

    all_rows = []
    successful = failed = 0
    total = len(domains)

    for i, domain_name in enumerate(domains, start=1):
        print(f"[{i}/{total}] {domain_name}...", end=" ", flush=True)
        rows = [
            run_for_row(row, domain_name, input_path, script_path, venv_python,
                        folder_name, tv_mac, args.skip_minutes)
            for _, row in timings.iterrows()
        ]
        all_rows.extend(rows)
        write_results(all_rows, output_path)  # save progress after each domain

        if any(r.get("status") == "error" for r in rows):
            print("✗")
            failed += 1
        else:
            print("✓")
            successful += 1

    print(f"\n{'=' * 60}")
    print(f"✓ Completed: {successful}/{total} domain(s) processed successfully")
    if failed:
        print(f"✗ Failed: {failed} domain(s) (see 'status' column)")
    print(f"Results written to: {output_path}")
    print(f"{'=' * 60}")