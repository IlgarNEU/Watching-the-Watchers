#!/usr/bin/env python3
import requests
import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
RESULTS_DIR = PROJECT_ROOT / "results"

DATA_TYPE_DIRS = {
    "pcaps": "data/pcaps",
    "parquets": "data/parquets",
    "csv": "data/individual_domain_csvs",
}

# Replace Google Drive folder IDs with Zenodo record IDs
DATA_FOLDERS = {
    "pcaps": {
        "test_pcaps": {
            "record_id": "22695930",
            "description": "small size pcaps datasets"
        },
    },
    "parquets": {
        "tizen": {
            "record_id": "22698084",
            "description": "Tizen parquets datasets"
        },
        "webos": {
            "record_id": "22698120",
            "description": "WebOS parquets datasets"
        },
        "roku_roku": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Roku (Roku) parquets datasets"
        },
        "roku_tcl": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Roku (TCL) parquets datasets"
        },
        "google": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Google TV parquets datasets"
        },
        "fire": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Fire TV parquets datasets"
        },
        "smartcast": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "SmartCast parquets datasets"
        },
        "xumo": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "XUMO parquets datasets"
        },
        "google_sony_non_acr": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Google (Sony Non-ACR) parquets datasets"
        },
        "google_hisense": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Google (Hisense) parquets datasets"
        },
        "google_tcl": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Google (TCL) parquets datasets"
        },
    },
    "csv": {
        "tizen": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Tizen csv datasets"
        },
        "webos": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "WebOS csv datasets"
        },
        "roku_roku": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Roku (Roku) csv datasets"
        },
        "roku_tcl": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Roku (TCL) csv datasets"
        },
        "google": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Google TV csv datasets"
        },
        "fire": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "Fire TV csv datasets"
        },
        "smartcast": {
            "record_id": "REPLACE_WITH_ZENODO_RECORD_ID",
            "description": "SmartCast csv datasets"
        }
    },
}

# Zenodo API endpoint
ZENODO_API_URL = "https://zenodo.org/api/records"


def normalize_sources(record_id_field):
    """Normalize record_id field to list of source dicts."""
    if isinstance(record_id_field, str):
        return [{"id": record_id_field, "label": None}]

    if isinstance(record_id_field, list):
        sources = []
        for i, entry in enumerate(record_id_field, start=1):
            if isinstance(entry, str):
                sources.append({"id": entry, "label": f"source_{i}"})
            elif isinstance(entry, dict):
                sources.append({
                    "id": entry["id"],
                    "label": entry.get("label", f"source_{i}")
                })
            else:
                raise ValueError(f"Invalid record_id entry: {entry!r}")
        return sources

    raise ValueError(f"Invalid record_id field: {record_id_field!r}")


def is_configured(record_id_field):
    """Check if record ID is configured (not placeholder)."""
    sources = normalize_sources(record_id_field)
    return all(not s["id"].startswith("REPLACE_WITH") for s in sources)


def download_file(file_url, output_path, filename):
    """Download a single file from Zenodo."""
    try:
        print(f"  Downloading {filename}...", end=" ", flush=True)
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Get file size
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        print(f"✓ ({total_size / (1024**2):.2f} MB)")
        return True
        
    except Exception as e:
        print(f"✗")
        print(f"    Error downloading {filename}: {e}")
        return False


def download_from_zenodo(record_id, output_dir):
    """Download all files from a Zenodo record."""
    try:
        # Fetch record metadata
        print(f"  Fetching metadata from Zenodo (record {record_id})...", flush=True)
        response = requests.get(f"{ZENODO_API_URL}/{record_id}", timeout=10)
        response.raise_for_status()
        record = response.json()
        
        files = record.get('files', [])
        if not files:
            print(f"  ⚠ No files found in record {record_id}")
            return True
        
        print(f"  Found {len(files)} file(s)\n")
        
        # Create output directory
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Download each file
        all_success = True
        for file_info in files:
            file_url = file_info['links']['self']
            filename = file_info['key']
            output_path = output_dir / filename
            
            success = download_file(file_url, output_path, filename)
            if not success:
                all_success = False
        
        return all_success
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Failed to fetch record metadata!")
        print(f"  Error: {e}")
        print(f"\n  Troubleshooting:")
        print(f"  1. Check Record ID is correct: {record_id}")
        print(f"  2. Verify record is public: https://zenodo.org/record/{record_id}")
        print(f"  3. Check internet connection")
        return False


def download_tv_datasets(tv_brand, data_type):
    """Download datasets for a specific TV brand and data type."""
    if data_type.lower() not in DATA_FOLDERS:
        print(f"\n✗ ERROR: Unknown data type '{data_type}'")
        print(f"\nAvailable data types:")
        for dtype in sorted(DATA_FOLDERS.keys()):
            print(f"  - {dtype}")
        sys.exit(1)

    if tv_brand.lower() not in DATA_FOLDERS[data_type.lower()]:
        print(f"\n✗ ERROR: Unknown TV brand '{tv_brand}' for data type '{data_type}'")
        print(f"\nAvailable TV brands for '{data_type}':")
        for brand in sorted(DATA_FOLDERS[data_type.lower()].keys()):
            print(f"  - {brand}")
        sys.exit(1)

    tv_info = DATA_FOLDERS[data_type.lower()][tv_brand.lower()]
    description = tv_info["description"]

    # Check if record ID(s) are configured
    if not is_configured(tv_info["record_id"]):
        print(f"\n✗ ERROR: Zenodo Record ID not configured for '{tv_brand}' ({data_type})")
        print(f"\nPlease update DATA_FOLDERS dict with Zenodo record ID(s):")
        print(f"  1. Go to Zenodo: https://zenodo.org")
        print(f"  2. Find your {tv_brand} {data_type} dataset")
        print(f"  3. Copy the record ID from URL: https://zenodo.org/record/RECORD_ID")
        print(f"  4. Update this script with the record ID(s)")
        sys.exit(1)

    sources = normalize_sources(tv_info["record_id"])
    multi_source = len(sources) > 1

    # Get the data directory based on data type
    data_dir = PROJECT_ROOT / DATA_TYPE_DIRS[data_type]
    tv_data_dir = data_dir / tv_brand.lower()
    tv_data_dir.mkdir(exist_ok=True, parents=True)

    print("=" * 70)
    print(f"Downloading {description}")
    print("=" * 70)
    print(f"\nData Type: {data_type}")
    print(f"Brand: {tv_brand.lower()}")
    if multi_source:
        print(f"Sources: {len(sources)} Zenodo records (merging into one folder)")
    else:
        print(f"Zenodo Record ID: {sources[0]['id']}")
    print(f"Output: {tv_data_dir}")
    print("\nStarting download...")
    print("(This may take a while for large datasets...)\n")

    any_failure = False

    for i, source in enumerate(sources, start=1):
        record_id = source["id"]

        if multi_source:
            print(f"--- Source {i}/{len(sources)}: {source['label']} (Record {record_id}) ---")

        success = download_from_zenodo(record_id, tv_data_dir)
        
        if not success:
            any_failure = True

    if any_failure:
        print("\n" + "=" * 70)
        print(f"✗ One or more sources failed for {tv_brand}")
        print("=" * 70)
        return False

    print("\n" + "=" * 70)
    print(f"✓ Download completed successfully for {tv_brand}!")
    print("=" * 70)

    # Calculate and display download summary
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


def list_available_options():
    """List all available data types and TV brands."""
    print("\nAvailable options by data type:")
    print("=" * 60)
    for data_type in sorted(DATA_FOLDERS.keys()):
        print(f"\n{data_type.upper()}:")
        print("-" * 40)
        for brand, info in sorted(DATA_FOLDERS[data_type].items()):
            configured = "✓" if is_configured(info["record_id"]) else "✗"
            n_sources = len(normalize_sources(info["record_id"]))
            src_note = f" ({n_sources} sources, merged)" if n_sources > 1 else ""
            print(f"  {configured} {brand:15} - {info['description']}{src_note}")
    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Zenodo datasets for a specific TV brand and data type",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "data_type",
        nargs="?",
        help="Data type to download (e.g., pcaps, parquets, csv)"
    )

    parser.add_argument(
        "tv_brand",
        nargs="?",
        help="TV brand to download (e.g., tizen, webos, roku_roku)"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available data types and TV brands"
    )

    args = parser.parse_args()

    if args.list:
        list_available_options()
        return 0

    if not args.data_type or not args.tv_brand:
        parser.print_help()
        list_available_options()
        return 1

    if args.data_type.lower() not in DATA_TYPE_DIRS:
        print(f"\n✗ ERROR: Unknown data type '{args.data_type}'")
        list_available_options()
        return 1

    success = download_tv_datasets(args.tv_brand, args.data_type.lower())
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())