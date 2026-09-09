import sys
import subprocess
from pathlib import Path
import os

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_DIR = PROJECT_ROOT / "data" / "pcaps"
CSV_DIR = PROJECT_ROOT / "data" / "csvs"
PYTHON_PATH = SCRIPTS_FOLDER / "venv" / "bin" / "python"
SCRIPT_PATH = SCRIPT_DIR / "SniTsharkPcapToCsv.py"


def run_pcap_to_csv(folder_name):
    input_folder = DATA_DIR / folder_name
    csv_folder = CSV_DIR / folder_name
    
    # Verify paths exist
    if not input_folder.is_dir():
        print(f"Folder not found: {input_folder}")
        sys.exit(1)
    
    # Create CSV output folder if it doesn't exist
    csv_folder.mkdir(parents=True, exist_ok=True)

    print(f"Scanning folder: {input_folder}")

    for filename in os.listdir(input_folder):
        if not filename.endswith(".pcap"):
            continue

        pcap_path = input_folder / filename
        base_name = filename.rsplit(".", 1)[0]
        csv_path = csv_folder / f"{base_name}.csv"

        print(f"Processing: {filename}")

        try:
            subprocess.run([str(PYTHON_PATH), str(SCRIPT_PATH), str(pcap_path), str(csv_path)], check=True)
            print(f"Done: {csv_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error while processing {filename}: {e}")
        except Exception as e:
            print(f"Unexpected error for {filename}: {e}")
    
    print("All files processed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runSniPcapToCsv.py <folder_name>")
        print("Example: python runSniPcapToCsv.py samsung")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    run_pcap_to_csv(folder_name)