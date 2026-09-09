"""
Code Description:

    This code is the third phase of the pipeline. 
    Once all .pcap files are converted to .csv format with necessary fields extracted,
    the .csv files are grouped by day, merged into per-day .parquet files.
    Then the .per-day parquet files are merged into one large merged.parquet file.
    
    The reason for step-by-step processing is that the number of .csv files is large and
    the time required to merge them into one large .parquet file grows as the .csv files are processed.
    In this step-by-step version, smaller number of .csv files are processed in groups.


    Code usage:
    python3 mergeCsvs.py <folder_name>
    
    For example:
    python3 mergeCsvs.py samsung
"""
import sys
import pandas as pd
import re
from pathlib import Path
from collections import defaultdict

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_CSVS_DIR = PROJECT_ROOT / "data" / "csvs"
DATA_PARQUETS_DIR = PROJECT_ROOT / "data" / "parquets"


class CSVFolderMerger:
    def __init__(self, folder_name):
        self.input_folder = DATA_CSVS_DIR / folder_name
        self.output_folder = DATA_PARQUETS_DIR / folder_name
        
        # Verify input folder exists
        if not self.input_folder.is_dir():
            print(f"Error: Input folder not found: {self.input_folder}")
            sys.exit(1)
        
        # Create output folder if it doesn't exist
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def sort_key(self, filename):
        match_with_num = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2}\.\d{2}\.\d{2})_[\d.]+_(\d+)\.csv$', filename)
        match_no_num   = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2}\.\d{2}\.\d{2})_[\d.]+\.csv$', filename)

        if match_with_num:
            return (match_with_num.group(1), match_with_num.group(2), int(match_with_num.group(3)))
        elif match_no_num:
            return (match_no_num.group(1), match_no_num.group(2), 0)
        else:
            return ('9999-99-99', '99.99.99', 999)

    def fix_types(self, df):
        mixed_type_cols = ['rcode', 'qry_type', 'ans_type', 'ans_ttl', 'ans_data', 'ans_name']
        for col in mixed_type_cols:
            if col in df.columns:
                df[col] = df[col].astype(str)
        return df

    def group_by_day(self, csv_files):
        groups = defaultdict(list)
        for f in csv_files:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', f)
            if match:
                groups[match.group(1)].append(f)
        return groups

    def merge(self):
        csv_files = [f.name for f in self.input_folder.glob('*.csv')]
        if not csv_files:
            print(f"No CSV files found in {self.input_folder}")
            return

        csv_files.sort(key=self.sort_key)
        day_groups = self.group_by_day(csv_files)

        all_dfs = []

        for day, files in sorted(day_groups.items()):
            print(f"\nProcessing day: {day} ({len(files)} files)")
            day_df = pd.DataFrame()

            for file in files:
                file_path = self.input_folder / file
                print(f"  Merging: {file}")
                try:
                    df = pd.read_csv(file_path, low_memory=False)
                    day_df = pd.concat([day_df, df], ignore_index=True)
                except Exception as e:
                    print(f"  Error reading {file}: {e}")

            day_df = self.fix_types(day_df)

            day_output = self.output_folder / f"{day}.parquet"
            if day_output.exists():
                day_output.unlink()
            day_df.to_parquet(day_output, index=False)
            print(f"  Saved: {day_output}")

            all_dfs.append(day_df)

        print("\nMerging all days...")
        merged_df = pd.concat(all_dfs, ignore_index=True)
        merged_output = self.output_folder / "merged_all.parquet"
        if merged_output.exists():
            merged_output.unlink()
        merged_df.to_parquet(merged_output, index=False)
        print(f"Saved full merged: {merged_output}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mergeCsvs.py <folder_name>")
        print("Example: python mergeCsvs.py samsung")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    merger = CSVFolderMerger(folder_name)
    merger.merge()