#!/usr/bin/env python3
import gdown
import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_DIR = PROJECT_ROOT / "data/pcaps"
RESULTS_DIR = PROJECT_ROOT / "results"


DATA_DIR.mkdir(exist_ok=True, parents=True)


TV_FOLDERS = {
    "samsung": {
        "folder_id": "1hEOLSOdXgRcR6E_QZqwVMWVyG_xsBYDK?dmr=1&ec=wgc-drive-hero-goto",
        "description": "Samsung TV datasets"
    },
    "lg": {
        "folder_id": "REPLACE_WITH_LG_FOLDER_ID",
        "description": "LG TV datasets"
    },
    "sony": {
        "folder_id": "REPLACE_WITH_SONY_FOLDER_ID",
        "description": "Sony TV datasets"
    },
    
}


def download_tv_datasets(tv_brand):
    if tv_brand.lower() not in TV_FOLDERS:
        print(f"\n✗ ERROR: Unknown TV brand '{tv_brand}'")
        print(f"\nAvailable TV brands:")
        for brand in sorted(TV_FOLDERS.keys()):
            print(f"  - {brand}")
        sys.exit(1)
    
    tv_info = TV_FOLDERS[tv_brand.lower()]
    folder_id = tv_info["folder_id"]
    description = tv_info["description"]
    
    # Check if folder ID is configured
    if folder_id == f"REPLACE_WITH_{tv_brand.upper()}_FOLDER_ID" or \
       folder_id.startswith("REPLACE_WITH"):
        print(f"\n✗ ERROR: Folder ID not configured for '{tv_brand}'")
        print(f"\nPlease update TV_FOLDERS dict with Google Drive folder ID:")
        print(f"  1. Go to Google Drive")
        print(f"  2. Right-click {tv_brand} folder → Share")
        print(f"  3. Copy link: https://drive.google.com/drive/folders/FOLDER_ID")
        print(f"  4. Extract FOLDER_ID and update this script")
        sys.exit(1)
    
    tv_data_dir = DATA_DIR / tv_brand.lower()
    tv_data_dir.mkdir(exist_ok=True, parents=True)
    
    print("=" * 70)
    print(f"Downloading {description}")
    print("=" * 70)
    print(f"\nBrand: {tv_brand.lower()}")
    print(f"Folder ID: {folder_id}")
    print(f"Output: {tv_data_dir}")
    print("\nStarting download...")
    print("(This may take a while for large datasets...)\n")
    
    try:
        gdown.download_folder(
            f"https://drive.google.com/drive/folders/{folder_id}",
            output=str(tv_data_dir),
            quiet=False,
            use_cookies=False
        )
        
        print("\n" + "=" * 70)
        print(f"✓ Download completed successfully for {tv_brand}!")
        print("=" * 70)
        
        all_items = list(tv_data_dir.rglob("*"))
        files = [f for f in all_items if f.is_file()]
        folders = [f for f in all_items if f.is_dir()]
        total_size = sum(f.stat().st_size for f in files)
        total_size_gb = total_size / (1024**3)
        
        print(f"\nDownload Summary for {tv_brand}:")
        print(f"  Subfolders: {len(folders)}")
        print(f"  Files: {len(files)}")
        print(f"  Total size: {total_size_gb:.2f} GB")
        print(f"  Location: {tv_data_dir}")
        
        print(f"\nFolder structure (first level):")
        try:
            items = sorted(tv_data_dir.iterdir())[:10]
            for item in items:
                if item.is_dir():
                    print(f"  📁 {item.name}/")
                else:
                    print(f"  📄 {item.name}")
            if len(list(tv_data_dir.iterdir())) > 10:
                print(f"  ... and {len(list(tv_data_dir.iterdir())) - 10} more items")
        except Exception as e:
            print(f"  (Could not display structure: {e})")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Download failed!")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print(f"1. Check {tv_brand} folder is public (Share → Anyone with link)")
        print(f"2. Check FOLDER_ID is correct: {folder_id}")
        print("3. Check internet connection")
        print("4. For very large folders, download may time out")
        return False


def list_available_brands():
    """List all available TV brands."""
    print("\nAvailable TV brands:")
    print("-" * 40)
    for brand, info in sorted(TV_FOLDERS.items()):
        folder_id = info["folder_id"]
        configured = "✓" if not folder_id.startswith("REPLACE_WITH") else "✗"
        print(f"{configured} {brand:15} - {info['description']}")
    print("-" * 40)


def main():
    parser = argparse.ArgumentParser(
        description="Download Google Drive datasets for a specific TV brand",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "tv_brand",
        nargs="?",
        help="TV brand to download (e.g., samsung, lg, sony)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available TV brands"
    )
    
    args = parser.parse_args()
    
    # If --list flag, show available brands
    if args.list:
        list_available_brands()
        return 0
    
    # If no brand specified, show help
    if not args.tv_brand:
        parser.print_help()
        list_available_brands()
        return 1
    
    # Download for specified brand
    success = download_tv_datasets(args.tv_brand)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())