#!/usr/bin/env python3
import gdown
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

DATA_FOLDERS = {
    "pcaps": {
        "tizen": {
            "folder_id": "1hEOLSOdXgRcR6E_QZqwVMWVyG_xsBYDK",
            "description": "Tizen pcaps datasets"
        },
        "webos": {
            "folder_id": "1kyGRN-h7zo4lJxwZXoH5aGf-XVy7O1u5",
            "description": "WebOS pcaps datasets"
        },
        "roku_roku": {
            "folder_id": "1EWFG3YNGvtXwYJ29kNxS9kc-CzFMfC8H",
            "description": "Roku (Roku) pcaps datasets"
        },
        "roku_tcl": {
            "folder_id": "12p9a2XPIh690pvqHk8rz2Ds47kJ4sJHV",
            "description": "Roku (TCL) pcaps datasets"
        },
        "google": {
            "folder_id": ["1mW_D6U5W3GP4YtYOyvYN-BeXD4PVGCdE","1s4guAswVaa_WhHL6hhxpwhnPKJ6w4aO2"],
            "description": "Google TV pcaps datasets"
        },
        "fire": {
            "folder_id": ["1IP_9zGE11UkXcHGDfY63NXkP73WNHDzl","1w3G0RbRHVb7a-f-y2CLCN1FuPaIFFRvl"],
            "description": "Fire TV pcaps datasets"
        },
        "smartcast": {
            "folder_id": "1JJ1vbANexRYWQLD9XArgYh-g3QqIxp41",
            "description": "SmartCast pcaps datasets"
        },
        "xumo": {
            "folder_id": "1XvuATSxREL_X4BbjeXx9Zcd2kzGlwXyA",
            "description": "XUMO pcaps datasets"
        },
        "google_sony_non_acr": {
            "folder_id": "1nGNfm1Oz4sVs2hRFgeUXB9QREvloqfLg",
            "description": "Google (Sony Non-ACR) pcaps datasets"
        },
        "google_hisense": {
            "folder_id": "1Lm4GFtzuULXXtTqs_gSB4JIBAFMi6xxJ",
            "description": "Google (Hisense) pcaps datasets"
        },
        "google_tcl": {
            "folder_id": "1YSyNIg72Xt3UNOX4ELy_E0XJDT7_7R26",
            "description": "Google (TCL) pcaps datasets"
        },
    },
    "parquets": {
        "tizen": {
            "folder_id": "1VMnWO0OO64v6Cb4pCUINvI1_eY7-6ZwM",
            "description": "Tizen parquets datasets"
        },
        "webos": {
            "folder_id": "1SRlit9X_OtrREczP9VxzDY1zJQkOPe4t",
            "description": "WebOS parquets datasets"
        },
        "roku_roku": {
            "folder_id": "1ZsSdhGs24DIcZIe2guwOEfAZF-5KJcMl",
            "description": "Roku (Roku) parquets datasets"
        },
        "roku_tcl": {
            "folder_id": "116IUtgDkR_hexbAw2OQWTLfAvXZoMiJv",
            "description": "Roku (TCL) parquets datasets"
        },
        "google": {
            "folder_id": "1UdXalHwHZkCL-slXaCV5cge3jHnJ6oBr",
            "description": "Google TV parquets datasets"
        },
        "fire": {
            "folder_id": "1X6LQZaWe5XJFLFHbAriahhSofOEOmisn",
            "description": "Fire TV parquets datasets"
        },
        "smartcast": {
            "folder_id": "1oqxxlBi0as7MTz71UwdmTIeAtRdpOeY8",
            "description": "SmartCast parquets datasets"
        },
        "xumo": {
            "folder_id": "1zT1_cKHpbJ6sjMRIPH6DLAe5yTd5yF4r",
            "description": "XUMO parquets datasets"
        },
        "google_sony_non_acr": {
            "folder_id": "1rqoyLLZbr0vP4HQ2o1JMLdetXXNT3bFf",
            "description": "Google (Sony Non-ACR) parquets datasets"
        },
        "google_hisense": {
            "folder_id": "1tnCz0ujHEcNl9vACyMsIbrv-h3SefMwc",
            "description": "Google (Hisense) parquets datasets"
        },
        "google_tcl": {
            "folder_id": "116IUtgDkR_hexbAw2OQWTLfAvXZoMiJv",
            "description": "Google (TCL) parquets datasets"
        },
    },
    "csv": {
        "tizen": {
            "folder_id": "1VFGR7jmqGOUjvrkIz7njNNAuwrHoICRC",
            "description": "Tizen csv datasets"
        },
        "webos": {
            "folder_id": "1PLTNsH0hjtWjXjcBbfxRcF7YFXCQ-3Mo",
            "description": "WebOS csv datasets"
        },
        "roku_roku": {
            "folder_id": "1VcFdgttZfRpLBJDL2S9RODMSWbDPb6fi",
            "description": "Roku (Roku) csv datasets"
        },
        "roku_tcl": {
            "folder_id": "1rDRFskSdhfjyLuyKArIbTCD-bDNZWdvw",
            "description": "Roku (TCL) csv datasets"
        },
        "google": {
            "folder_id": "1KrNr98LhvfmR8q5bc0xyxRUs969qmTE5",
            "description": "Google TV csv datasets"
        },
        "fire": {
            "folder_id": "1V6y7WCru0XzewKPYxWb5qXhL-_b-IduZ",
            "description": "Fire TV csv datasets"
        },
        "smartcast": {
            "folder_id": "1py8hasRyRENmLCi0uliu2PCC5G3Kj3Z8",
            "description": "SmartCast csv datasets"
        }
    },
}


def normalize_sources(folder_id_field):
    if isinstance(folder_id_field, str):
        return [{"id": folder_id_field, "label": None}]

    if isinstance(folder_id_field, list):
        sources = []
        for i, entry in enumerate(folder_id_field, start=1):
            if isinstance(entry, str):
                sources.append({"id": entry, "label": f"source_{i}"})
            elif isinstance(entry, dict):
                sources.append({
                    "id": entry["id"],
                    "label": entry.get("label", f"source_{i}")
                })
            else:
                raise ValueError(f"Invalid folder_id entry: {entry!r}")
        return sources

    raise ValueError(f"Invalid folder_id field: {folder_id_field!r}")


def is_configured(folder_id_field):
    sources = normalize_sources(folder_id_field)
    return all(not s["id"].startswith("REPLACE_WITH") for s in sources)


def download_tv_datasets(tv_brand, data_type):
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

    # Check if folder ID(s) are configured
    if not is_configured(tv_info["folder_id"]):
        print(f"\n✗ ERROR: Folder ID not configured for '{tv_brand}' ({data_type})")
        print(f"\nPlease update DATA_FOLDERS dict with Google Drive folder ID(s):")
        print(f"  1. Go to Google Drive")
        print(f"  2. Right-click {tv_brand} {data_type} folder → Share")
        print(f"  3. Copy link: https://drive.google.com/drive/folders/FOLDER_ID")
        print(f"  4. Extract FOLDER_ID and update this script")
        sys.exit(1)

    sources = normalize_sources(tv_info["folder_id"])
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
        print(f"Sources: {len(sources)} (merging into one folder)")
    else:
        print(f"Folder ID: {sources[0]['id']}")
    print(f"Output: {tv_data_dir}")
    print("\nStarting download...")
    print("(This may take a while for large datasets...)\n")

    any_failure = False

    for i, source in enumerate(sources, start=1):
        folder_id = source["id"]

        if multi_source:
            print(f"\n--- Source {i}/{len(sources)}: {source['label']} ({folder_id}) ---")

        try:
            gdown.download_folder(
                f"https://drive.google.com/drive/folders/{folder_id}",
                output=str(tv_data_dir),
                quiet=False,
                use_cookies=False
            )
        except Exception as e:
            any_failure = True
            print(f"\n✗ Download failed for source {i} ({folder_id})!")
            print(f"Error: {e}")
            print("\nTroubleshooting:")
            print(f"1. Check the folder is public (Share → Anyone with link)")
            print(f"2. Check FOLDER_ID is correct: {folder_id}")
            print("3. Check internet connection")
            print("4. For very large folders, download may time out")
            continue

    if any_failure:
        print("\n" + "=" * 70)
        print(f"✗ One or more sources failed for {tv_brand}")
        print("=" * 70)
        return False

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


def list_available_options():
    print("\nAvailable options by data type:")
    print("=" * 60)
    for data_type in sorted(DATA_FOLDERS.keys()):
        print(f"\n{data_type.upper()}:")
        print("-" * 40)
        for brand, info in sorted(DATA_FOLDERS[data_type].items()):
            configured = "✓" if is_configured(info["folder_id"]) else "✗"
            n_sources = len(normalize_sources(info["folder_id"]))
            src_note = f" ({n_sources} sources, merged)" if n_sources > 1 else ""
            print(f"  {configured} {brand:15} - {info['description']}{src_note}")
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Download Google Drive datasets for a specific TV brand and data type",
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
        help="TV brand to download (e.g., samsung, lg, sony)"
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