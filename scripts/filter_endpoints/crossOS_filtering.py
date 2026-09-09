import sys
from pathlib import Path
import pandas as pd
from collections import defaultdict

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"

def filter_common_domains(root_folder, csv_filename):
    file_data = {} 
    domain_count = defaultdict(int) 
    
    print(f"Searching for '{csv_filename}' in subfolders of '{root_folder}'...\n")
    
    for subfolder in root_folder.iterdir():
        if not subfolder.is_dir():
            continue
        
        file_path = subfolder / csv_filename
        
        if not file_path.exists():
            continue
        
        try:
            df = pd.read_csv(file_path)
            
            if 'domain' not in df.columns:
                print(f"⚠️  Warning: 'domain' column not found in {file_path}")
                continue
            
            file_data[file_path] = df
            
            domains = df['domain'].dropna().unique()
            for domain in domains:
                domain_count[domain] += 1
            
            print(f"✓ Found: {subfolder.name}/{csv_filename}")
            print(f"  Rows: {len(df)}, Unique domains: {len(domains)}")
            
        except Exception as e:
            print(f"✗ Error reading {file_path}: {e}")
    
    if not file_data:
        print("No matching CSV files found!")
        return
    
    print(f"\n{'='*60}")
    print(f"Total files found: {len(file_data)}")
    
    common_domains = {domain for domain, count in domain_count.items() if count >= 2}
    
    print(f"Common domains (in ≥2 files): {len(common_domains)}")
    if common_domains:
        print(f"Examples: {list(common_domains)[:5]}")
    
    print(f"{'='*60}\n")
    
    if not common_domains:
        print("No common domains found across files.")
        return
    
    print("Creating filtered files...\n")
    
    for file_path, df in file_data.items():
        filtered_df = df[~df['domain'].isin(common_domains)]
        
        folder_path = file_path.parent
        filename_without_ext = file_path.stem
        file_ext = file_path.suffix
        
        output_filename = f"{filename_without_ext}_filtered{file_ext}"
        output_path = folder_path / output_filename
        
        filtered_df.to_csv(output_path, index=False)
        
        removed_count = len(df) - len(filtered_df)
        subfolder_name = folder_path.name
        print(f"✓ {subfolder_name}/{output_filename}")
        print(f"  Original rows: {len(df)} → Filtered rows: {len(filtered_df)}")
        print(f"  Removed: {removed_count} rows with common domains\n")
    
    print(f"{'='*60}")
    print(f"All filtered files saved to their original folders")
    print(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("Usage: python filter_common_domains.py [csv_filename]")
        print("Example: python filter_common_domains.py")
        print("Example: python filter_common_domains.py 'Opt-in filter.csv'")
        print("\nSearches in: project_root/data/filtering_results/")
        sys.exit(0)
    
    csv_filename = sys.argv[1] if len(sys.argv) > 1 else "frequent_domains_top.csv"
    root_folder = DATA_FILTERING_RESULTS_DIR
    
    # Verify root folder exists
    if not root_folder.exists():
        print(f"Error: Root folder not found: {root_folder}")
        sys.exit(1)
    
    filter_common_domains(root_folder, csv_filename)