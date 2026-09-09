"""
Code Description:

    This code is the first phase of the pipeline. 
    The .pcap files in Mon(IoT)r data servers are named as .pcap1, .pcap2, .pcap3, etc.
    To convert these .pcap files to .csv files, we need to rename all files to .pcap extension in the folder.
    After this code is called, the .pcap files will be renamed as:
    xxxx.pcap1 -> xxxx_1.pcap


    Code usage:
    python3 renamePcapsFromIoTSystem.py <folder_path>

    For example:
    python3 renamePcapsFromIotSystem.py ../data/pcaps/Tizen_OS/
"""

import sys
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_DIR = PROJECT_ROOT / "data" / "pcaps"


class PcapRenamer:
    def __init__(self, folder_path):
        self.folder_path = DATA_DIR / folder_path

        if not self.folder_path.is_dir():
            raise ValueError(f"Directory not found: {self.folder_path}")

    def rename_pcaps(self):
        for filename in os.listdir(self.folder_path):
            old_path = os.path.join(self.folder_path, filename)

            if(os.path.isdir(old_path)):
                continue

            match = re.match(r"^(.*)\.pcap(\d+)$", filename)
            if match:
                base_name = match.group(1)
                number = match.group(2)
                new_filename = f"{base_name}_{number}.pcap"
                new_path = os.path.join(self.folder_path, new_filename)
                print(f"Renaming: {filename} -> {new_filename}")
                os.rename(old_path, new_path)
            
            elif filename.endswith(".pcap"):
                print(f"Keeping: {filename}")
            else:
                print(f"Skipping (not a pcap): {filename}")
        print("Renaming complete.")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "captures"
    renamer = PcapRenamer(folder)
    renamer.rename_pcaps()