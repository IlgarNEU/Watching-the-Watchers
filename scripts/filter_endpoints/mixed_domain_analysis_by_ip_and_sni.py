"""
Code Description:

    This code is the fourth phase of the pipeline. 
    Once we have merged.parquet file for a smart-TV,
    this script creates ip_to_dns_mapping.csv file. 

    This ip_to_dns_mapping.csv is created using two fields from the network traces: DNS and SNI;
    All IP addresses are first mapped to DNS names, then on the second pass IPs are mapped to SNI names.

    Once the ip_to_dns_mapping.csv file is ready,
    the timing.csv file is read (which contains the timing for each experimental scenario with a smart TV),
    and the list of domains contacted during each experiment is saved as a separate .csv file.
    The unmapped IPs contacted during each experiment is also saved as "_unmapped.csv" file.

    Code usage:
    python3 domain_analysis_by_ip_and_sni.py <folder_name>
    
    For example:
    python3 domain_analysis_by_ip_and_sni.py samsung
"""

import pandas as pd 
import sys
from pathlib import Path

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_PARQUETS_DIR = PROJECT_ROOT / "data" / "parquets"
DATA_IP_DNS_MAPPINGS_DIR = PROJECT_ROOT / "data" / "ip_to_dns_mappings"
DATA_DOMAIN_LISTS_DIR = PROJECT_ROOT / "data" / "domain_list_csvs"

# TV name to local IP mapping
TV_IP_MAPPING = {
    "tizen": "192.168.14.117",
    "webos": "192.168.14.118",
    "roku_roku": "192.168.14.119",
    "roku_tcl": "192.168.14.120",
    "google": "192.168.14.121",
    "fire": "192.168.14.122",
    "smartcast": "192.168.14.123",
    "xumo": "192.168.14.124",
    "google_sony_non_acr": "192.168.14.125",
    "google_hisense": "192.168.14.126",
    "google_tcl": "192.168.14.127",
}

class IPToDNSMapper:
    def __init__(self, parquet_file):
        self.parquet_file = parquet_file
        self.df = None
        self.ip_to_domains = {}

    def load_data(self):
        self.df = pd.read_parquet(self.parquet_file)
        self.df['est_time_parsed'] = pd.to_datetime(
            self.df['est_time'], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce"
        )
        print(f"Loaded {len(self.df)} rows")
        print(f"Available columns: {list(self.df.columns)}")

    def build_ip_to_dns_mapping(self):
        """One-time pass over all DNS rows to build IP → domain mapping."""
        dns_rows = self.df[
            self.df['ans_data'].notna() & (self.df['ans_data'] != '') &
            self.df['ans_name'].notna() & (self.df['ans_name'] != '')
        ]

        for _, row in dns_rows.iterrows():
            ans_ips = {ip.strip() for ip in str(row['ans_data']).split(',')}
            first_name = str(row['ans_name']).split(',')[0].strip()
            for ip in ans_ips:
                if ip:
                    self.ip_to_domains.setdefault(ip, set()).add(first_name)

        print(f"Built mapping for {len(self.ip_to_domains)} unique IPs")

    def build_ip_to_sni_mapping(self):
        """One-time pass over all SNI rows to build IP → SNI domain mapping."""
        # FIX: Check if 'sni' column exists before processing
        if 'sni' not in self.df.columns:
            print("Warning: 'sni' column not found in parquet data. Skipping SNI mapping.")
            print(f"Available columns are: {list(self.df.columns)}")
            return
        
        sni_rows = self.df[self.df['sni'].notna() & (self.df['sni'] != '')]

        count_before = len(self.ip_to_domains)
        for _, row in sni_rows.iterrows():
            ip = str(row['dst_ip']).strip()
            sni = str(row['sni']).strip()
            if ip and sni:
                self.ip_to_domains.setdefault(ip, set()).add(sni)

        added = sum(1 for v in self.ip_to_domains.values()) - count_before
        print(f"SNI mapping processed {len(sni_rows)} SNI rows")

    def get_domains_for_window(self, start_time, end_time, output_file=None, tv_local_ip="192.168.14.114"):
        start_t = pd.to_datetime(start_time, format="%Y-%m-%d %H:%M:%S")
        end_t   = pd.to_datetime(end_time,   format="%Y-%m-%d %H:%M:%S")

        windowed = self.df[
            (self.df['est_time_parsed'] >= start_t) &
            (self.df['est_time_parsed'] <= end_t)
        ]

        traffic = windowed[
            windowed['ans_name'].isna() & windowed['qry_name'].isna()
        ]

        contacted_ips = set()
        for entry in traffic['dst_ip'].dropna().unique():
            for ip in str(entry).split(','):
                ip = ip.strip()
                if ip and ip != tv_local_ip:
                    contacted_ips.add(ip)

        print(f"Found {len(contacted_ips)} unique destination IPs in window")

        domains = set()
        unmapped = set()
        for ip in contacted_ips:
            if ip in self.ip_to_domains:
                domains.update(self.ip_to_domains[ip])
            else:
                unmapped.add(ip)

        print(f"Resolved {len(domains)} domains, {len(unmapped)} IPs had no DNS record")

        if output_file:
            pd.DataFrame(sorted(domains), columns=['domain']).to_csv(output_file, index=False)
            print(f"Saved domains to {output_file}")

            unmapped_file = str(output_file).replace('.csv', '_unmapped.csv')
            pd.DataFrame(sorted(unmapped), columns=['ip']).to_csv(unmapped_file, index=False)
            print(f"Saved {len(unmapped)} unmapped IPs to {unmapped_file}")

        return domains, unmapped

    def save_mapping(self, output_file):
        """Optionally persist the mapping so you don't rebuild it next run."""
        rows = [
            {"ip": ip, "domain": domain}
            for ip, domains in self.ip_to_domains.items()
            for domain in sorted(domains)
        ]
        pd.DataFrame(rows).to_csv(output_file, index=False)
        print(f"Saved mapping to {output_file}")

    def load_mapping(self, mapping_file):
        """Load a previously saved mapping instead of rebuilding."""
        df = pd.read_csv(mapping_file)
        for _, row in df.iterrows():
            self.ip_to_domains.setdefault(row['ip'], set()).add(row['domain'])
        print(f"Loaded mapping for {len(self.ip_to_domains)} unique IPs")

    def setup(self, mapping_file):
        """Load parquet and either load existing mapping or build a new one."""
        self.load_data()
        if mapping_file.exists():
            self.load_mapping(mapping_file)
        else:
            self.build_ip_to_dns_mapping()
            self.save_mapping(mapping_file)
        self.build_ip_to_sni_mapping()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python domain_analysis_by_ip_and_sni.py <folder_name>")
        print("Example: python domain_analysis_by_ip_and_sni.py tizen")
        print(f"\nSupported TV models: {', '.join(TV_IP_MAPPING.keys())}")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    
    # Get TV IP from mapping, or use provided IP as override
    if len(sys.argv) > 2:
        tv_local_ip = sys.argv[2]
        print(f"Using custom TV IP: {tv_local_ip}")
    elif folder_name in TV_IP_MAPPING:
        tv_local_ip = TV_IP_MAPPING[folder_name]
        print(f"Using TV IP for '{folder_name}': {tv_local_ip}")
    else:
        print(f"Warning: TV model '{folder_name}' not found in mapping. Using default IP.")
        tv_local_ip = "192.168.14.114"
    
    # Construct paths
    timing_csv = DATA_TIMINGS_DIR / folder_name / "mixed_timing.csv"
    merged_parquet = DATA_PARQUETS_DIR / folder_name / "merged_all.parquet"
    ip_dns_mapping = DATA_IP_DNS_MAPPINGS_DIR / folder_name / "ip_to_dns_mapping.csv"
    output_dir = DATA_DOMAIN_LISTS_DIR / folder_name
    
    # Verify input files exist
    if not timing_csv.exists():
        print(f"Error: Timing file not found: {timing_csv}")
        sys.exit(1)
    if not merged_parquet.exists():
        print(f"Error: Parquet file not found: {merged_parquet}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create mapping directory if it doesn't exist
    ip_dns_mapping.parent.mkdir(parents=True, exist_ok=True)

    mapper = IPToDNSMapper(merged_parquet)
    mapper.setup(ip_dns_mapping)

    df = pd.read_csv(timing_csv)
    for idx, row in df.iterrows():
        action_name = str(row["action_name"])
        start_time  = str(row["start_time"])
        end_time    = str(row["end_time"])
        output_file = output_dir / f"{action_name}.csv"
        domains, unmapped = mapper.get_domains_for_window(
            start_time, end_time, output_file, tv_local_ip=tv_local_ip
        )