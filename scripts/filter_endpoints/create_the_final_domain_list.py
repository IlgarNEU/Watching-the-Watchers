import csv
import sys
from pathlib import Path
import argparse

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"

FULL_DOMAIN_COL = "domain"   # Column name in the full-domains CSV
BASE_DOMAIN_COL = "domain"   # Column name in the base-domains CSV


def load_base_domains(filepath: Path, col: str) -> set[str]:
    """Return a set of base domain strings, lowercased and stripped."""
    bases = set()
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row[col].strip().lower()
            if val:
                bases.add(val)
    return bases


def matches_any_base(domain: str, bases: set[str]) -> bool:
    """
    Return True if `domain` ends with any base domain.
    Handles both:
      - exact match          (example.com  == example.com)
      - subdomain match      (sub.example.com ends with .example.com)
    """
    d = domain.strip().lower()
    for base in bases:
        if d == base or d.endswith("." + base):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Filter full domains by a list of base domains."
    )
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., samsung)"
    )
    parser.add_argument(
        "--full-domains",
        default="well-known-services-filtered.csv",
        help="Full domains CSV filename (default: well-known-services-filtered.csv)"
    )
    parser.add_argument(
        "--base-domains",
        default="Opt-in filter_filtered.csv",
        help="Base domains CSV filename (default: Opt-in filter_filtered.csv)"
    )
    parser.add_argument(
        "--output",
        default="final_list.csv",
        help="Output CSV filename (default: final_list.csv)"
    )
    args = parser.parse_args()
    
    folder_name = args.folder_name
    
    # Construct paths
    full_domains_path = DATA_FILTERING_RESULTS_DIR / folder_name / args.full_domains
    base_domains_path = DATA_FILTERING_RESULTS_DIR / folder_name / args.base_domains
    output_path = DATA_FILTERING_RESULTS_DIR / folder_name / args.output
    
    # Verify input files exist
    if not full_domains_path.exists():
        sys.exit(f"ERROR: Full domains file not found: {full_domains_path}")
    
    if not base_domains_path.exists():
        sys.exit(f"ERROR: Base domains file not found: {base_domains_path}")
    
    # Load base domains
    try:
        bases = load_base_domains(base_domains_path, BASE_DOMAIN_COL)
    except KeyError:
        sys.exit(f"ERROR: Column '{BASE_DOMAIN_COL}' not found in '{base_domains_path}'")

    print(f"Loaded {len(bases)} base domain(s).")
    print(f"Full domains: {full_domains_path}")
    print(f"Base domains: {base_domains_path}")
    print(f"Output: {output_path}\n")

    # Stream full-domains CSV, writing matches to output
    matched = 0
    try:
        with (
            open(full_domains_path, newline="", encoding="utf-8") as infile,
            open(output_path, "w", newline="", encoding="utf-8") as outfile,
        ):
            reader = csv.DictReader(infile)
            if FULL_DOMAIN_COL not in (reader.fieldnames or []):
                sys.exit(f"ERROR: Column '{FULL_DOMAIN_COL}' not found in '{full_domains_path}'")

            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                if matches_any_base(row[FULL_DOMAIN_COL], bases):
                    writer.writerow(row)
                    matched += 1

    except FileNotFoundError as e:
        sys.exit(f"ERROR: {e}")

    print(f"✓ Matched {matched} row(s)")
    print(f"✓ Written to '{output_path}'")


if __name__ == "__main__":
    main()