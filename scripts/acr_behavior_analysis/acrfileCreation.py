import pandas as pd
import sys
from pathlib import Path
import argparse

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_PARQUETS_DIR = PROJECT_ROOT / "data" / "parquets"
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"

def analyze_all_domains(parquet_path, domain_list_csv, output_folder, mac=None):
    print("Reading merged parquet...")
    df = pd.read_parquet(parquet_path)
    df.columns = [c.strip().lower() for c in df.columns]
    print(f"Loaded {len(df)} rows")

    required_cols = {"src_ip", "dst_ip", "src_mac", "dst_mac"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        return

    domains = pd.read_csv(domain_list_csv)['domain'].dropna().str.strip().tolist()
    print(f"Processing {len(domains)} domains from {domain_list_csv}\n")

    for domain in domains:
        print(f"Processing '{domain}'...")
        output_csv = output_folder / f"{domain}.csv"

        if output_csv.exists():
            output_csv.unlink()

        acr_ips = set()
        matched_rows = pd.DataFrame()

        # --- DNS matching ---
        if "qry_name" in df.columns:
            acr_dns_df = df[df["qry_name"].str.contains(domain, case=False, na=False)]
            if not acr_dns_df.empty:
                print(f"  Found {len(acr_dns_df)} DNS rows")
                matched_rows = pd.concat([matched_rows, acr_dns_df])
                if "ans_data" in df.columns:
                    for ips in acr_dns_df["ans_data"].dropna():
                        for ip in str(ips).split(","):
                            acr_ips.add(ip.strip())
            else:
                print(f"  No DNS packets found for '{domain}'")
        else:
            print("  Column 'qry_name' not found — skipping DNS matching.")

        # --- SNI matching ---
        if "sni" in df.columns:
            acr_sni_df = df[df["sni"].str.contains(domain, case=False, na=False)]
            if not acr_sni_df.empty:
                print(f"  Found {len(acr_sni_df)} SNI rows")
                matched_rows = pd.concat([matched_rows, acr_sni_df])
                for ip in acr_sni_df["dst_ip"].dropna():
                    acr_ips.add(ip.strip())
            else:
                print(f"  No SNI packets found for '{domain}'")
        else:
            print("  Column 'sni' not found — skipping SNI matching.")

        if matched_rows.empty and not acr_ips:
            print(f"  No matches found for '{domain}' via DNS or SNI.")
            continue

        # --- Related traffic by IP ---
        if acr_ips:
            related_df = df[(df["src_ip"].isin(acr_ips)) | (df["dst_ip"].isin(acr_ips))]
            print(f"  Found {len(related_df)} related rows via {len(acr_ips)} IPs")
            matched_rows = pd.concat([matched_rows, related_df])

        final_df = matched_rows.drop_duplicates()
        final_df.to_csv(output_csv, index=False)
        print(f"  Saved {len(final_df)} rows to {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze network traffic by domain and generate CSVs"
    )
    
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., samsung)"
    )
    parser.add_argument(
        "--domain-file",
        default="frequent_domains_top_filtered.csv",
        help="Domain CSV filename in filtering_results folder (default: Opt-in filter_filtered.csv)"
    )
    parser.add_argument(
        "--mac",
        nargs="+",
        default=["04:e4:b6:74:dd:94"],
        help="MAC address(es) to filter (default: 04:e4:b6:74:dd:94)"
    )
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    domain_filename = args.domain_file
    
    # Construct paths
    parquet_path = DATA_PARQUETS_DIR / folder_name / "merged_all.parquet"
    domain_list_csv = DATA_FILTERING_RESULTS_DIR / folder_name / domain_filename
    output_folder = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    
    # Verify input files exist
    if not parquet_path.exists():
        print(f"Error: Parquet file not found: {parquet_path}")
        sys.exit(1)
    if not domain_list_csv.exists():
        print(f"Error: Domain list file not found: {domain_list_csv}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)
    
    analyze_all_domains(parquet_path, domain_list_csv, output_folder, args.mac)