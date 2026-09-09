import pandas as pd
import sys
from pathlib import Path

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"

def extract_base_domain(domain):
    parts = domain.strip().split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return domain  

def group_domains(input_file, output_file):
    df = pd.read_csv(input_file)

    if 'domain' not in df.columns:
        raise ValueError("'domain' column not found")

    df['base_domain'] = df['domain'].dropna().apply(extract_base_domain)

    grouped = (
        df.groupby('base_domain')['domain']
        .apply(list)
        .reset_index()
        .rename(columns={'domain': 'subdomains'})
    )
    grouped['subdomain_count'] = grouped['subdomains'].apply(len)
    grouped = grouped.sort_values('subdomain_count', ascending=False)

    grouped.to_csv(output_file, index=False)
    print(f"Grouped {len(df)} domains into {len(grouped)} base domains")
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python group_base_domains.py <folder_name>")
        print("Example: python group_base_domains.py samsung")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    
    # Construct paths
    input_file = DATA_FILTERING_RESULTS_DIR / folder_name / "well-known-services-filtered.csv"
    output_file = DATA_FILTERING_RESULTS_DIR / folder_name / "grouped_by_base.csv"
    
    # Verify input file exists
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    group_domains(input_file, output_file)