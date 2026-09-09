import pandas as pd
import sys
from pathlib import Path

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_DOMAIN_LISTS_DIR = PROJECT_ROOT / "data" / "domain_list_csvs"
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"

KEYWORDS = [
    "googlevideo",
    "facebook",
    "netflix",
    "nflx",
    "tubi",
    "youtube",
    "pluto",
    "amagi",
    "doubleclick",
    "ytimg",
    "apple",
    "yt3",
    "haystack",
    "gstatic",
    "arpa",
    "googleusercontent",
]

def filter_domains(input_file, output_file, keywords):
    df = pd.read_csv(input_file)

    if 'domain' not in df.columns:
        raise ValueError("'domain' column not found in the CSV")

    pattern = '|'.join(keywords)
    mask = df['domain'].str.contains(pattern, case=False, na=False)

    filtered = df[~mask]

    removed = len(df) - len(filtered)
    print(f"Removed {removed} rows, {len(filtered)} remaining")

    filtered.to_csv(output_file, index=False)
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_domains.py <folder_name>")
        print("Example: python filter_domains.py samsung")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    
    # Construct paths
    input_file = DATA_DOMAIN_LISTS_DIR / folder_name / "MIXED.csv"
    output_file = DATA_FILTERING_RESULTS_DIR / folder_name / "well-known-services-filtered.csv"
    
    # Verify input file exists
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    filter_domains(input_file, output_file, KEYWORDS)