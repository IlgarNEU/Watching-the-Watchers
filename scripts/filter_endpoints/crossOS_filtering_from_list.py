import sys
from pathlib import Path
import pandas as pd

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"
DATA_REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

def filter_against_reference(target_folder, csv_filename, reference_file_path):
    """
    Filter entries from a CSV file in target_folder by removing rows that 
    exist in the reference file.
    
    Args:
        target_folder: Path to folder containing the CSV file to filter
        csv_filename: Name of the CSV file to filter (e.g., "Opt-in filter.csv")
        reference_file_path: Path to the reference CSV file to compare against
    """
    
    # Validate inputs
    if not target_folder.is_dir():
        print(f"✗ Error: Target folder '{target_folder}' does not exist")
        return
    
    if not reference_file_path.is_file():
        print(f"✗ Error: Reference file '{reference_file_path}' does not exist")
        return
    
    target_file_path = target_folder / csv_filename
    
    if not target_file_path.is_file():
        print(f"✗ Error: CSV file '{csv_filename}' not found in '{target_folder}'")
        return
    
    print(f"Processing comparison...")
    print(f"Target folder: {target_folder}")
    print(f"Target file: {csv_filename}")
    print(f"Reference file: {reference_file_path}\n")
    
    try:
        # Read both files
        target_df = pd.read_csv(target_file_path)
        reference_df = pd.read_csv(reference_file_path)
        
        print(f"✓ Loaded target file: {len(target_df)} rows")
        print(f"✓ Loaded reference file: {len(reference_df)} rows\n")
        
        # Validate required column
        if 'domain' not in target_df.columns:
            print(f"✗ Error: 'domain' column not found in target file")
            return
        
        if 'domain' not in reference_df.columns:
            print(f"✗ Error: 'domain' column not found in reference file")
            return
        
        # Get unique domains from reference file
        reference_domains = set(reference_df['domain'].dropna().unique())
        print(f"Reference domains: {len(reference_domains)} unique domains")
        if len(reference_domains) > 0:
            print(f"Examples: {list(reference_domains)[:5]}\n")
        
        # Filter: remove rows where domain exists in reference file
        filtered_df = target_df[~target_df['domain'].isin(reference_domains)]
        
        removed_count = len(target_df) - len(filtered_df)
        
        print(f"{'='*60}")
        print(f"Filtering results:")
        print(f"  Original rows: {len(target_df)}")
        print(f"  Filtered rows: {len(filtered_df)}")
        print(f"  Removed: {removed_count} rows (found in reference file)")
        print(f"{'='*60}\n")
        
        if removed_count == 0:
            print("⚠️  No matching domains found. No file created.")
            return
        
        # Save filtered file
        filename_without_ext = target_file_path.stem
        file_ext = target_file_path.suffix
        output_filename = f"{filename_without_ext}_filtered{file_ext}"
        output_path = target_folder / output_filename
        
        filtered_df.to_csv(output_path, index=False)
        
        print(f"✓ Saved filtered file: {output_filename}")
        print(f"  Location: {output_path}")
        
    except Exception as e:
        print(f"✗ Error processing files: {e}")
        return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_reference.py <folder_name> [csv_filename] [reference_file]")
        print("Example: python filter_reference.py samsung 'Opt-in filter.csv'")
        print("Example: python filter_reference.py samsung 'Opt-in filter.csv' ../reference/domains.csv")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    csv_filename = sys.argv[2] if len(sys.argv) > 2 else "frequent_domains_top.csv"
    
    # Default reference file location
    default_reference = DATA_REFERENCE_DIR / "reference_domains.csv"
    reference_file_path = Path(sys.argv[3]) if len(sys.argv) > 3 else default_reference
    
    # Construct target folder path
    target_folder = DATA_FILTERING_RESULTS_DIR / folder_name
    
    # If reference file is relative, make it absolute from project root
    if not reference_file_path.is_absolute():
        reference_file_path = PROJECT_ROOT / reference_file_path
    
    filter_against_reference(target_folder, csv_filename, reference_file_path)