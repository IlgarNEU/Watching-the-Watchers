import pandas as pd
import sys
from pathlib import Path
import argparse

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_PARQUETS_DIR = PROJECT_ROOT / "data" / "parquets"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"


class AcrTrafficAnalyzer:
    def __init__(self, input_parquet, output_csv):
        self.input_parquet = input_parquet
        self.output_csv = output_csv

    def analyze_acr_traffic(self, target_ips):
        """
        Analyze traffic to/from specific IPs.
        
        Args:
            target_ips: List of IP addresses to search for
        """
        df = pd.read_parquet(self.input_parquet)
        print(f"Read the merged parquet: {len(df)} rows")
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = {"src_ip", "dst_ip", "src_mac", "dst_mac"}
        missing = required_cols - set(df.columns)
        if missing:
            print(f"ERROR: Missing required columns: {missing}")
            return

        # --- Collect all traffic to/from discovered IPs ---
        if target_ips:
            related_df = df[(df["src_ip"].isin(target_ips)) | (df["dst_ip"].isin(target_ips))]
            print(f"Found {len(related_df)} related rows via IP association ({len(target_ips)} IPs)")
            print(f"Target IPs: {target_ips}")
        else:
            print("ERROR: No target IPs provided")
            return

        final_df = related_df.drop_duplicates()
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(self.output_csv, index=False)
        print(f"Saved {len(final_df)} rows to {self.output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze ACR traffic for specific IPs"
    )
    
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., samsung)"
    )
    parser.add_argument(
        "--ips",
        nargs="+",
        default=["216.183.117.80"],
        help="Target IP addresses to search for (default: 216.183.117.80)"
    )
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    target_ips = args.ips
    
    # Generate output filename from IP(s)
    ip_filename = "_".join(target_ips)
    
    # Construct paths
    merged_all_parquet = DATA_PARQUETS_DIR / folder_name / "merged_all.parquet"
    output_csv = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name / f"{ip_filename}.csv"
    
    # Verify input file exists
    if not merged_all_parquet.exists():
        print(f"Error: Parquet file not found: {merged_all_parquet}")
        sys.exit(1)
    
    # Delete existing output file if it exists
    if output_csv.exists():
        output_csv.unlink()
        print(f"Deleted existing file: {output_csv}")
    
    print(f"\n{'='*60}")
    print(f"Parquet file: {merged_all_parquet}")
    print(f"Output CSV: {output_csv}")
    print(f"Target IPs: {target_ips}")
    print(f"{'='*60}\n")
    
    analyzer = AcrTrafficAnalyzer(merged_all_parquet, output_csv)
    analyzer.analyze_acr_traffic(target_ips)