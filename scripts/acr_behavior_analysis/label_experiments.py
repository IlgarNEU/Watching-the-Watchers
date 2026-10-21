"""
Label each experiment window in a traffic_volume.csv as "On" or "Off"
based on outgoing_bytes_per_sec and a per-TV-model threshold.

    outgoing_bytes_per_sec >= threshold  ->  "On"
    outgoing_bytes_per_sec <  threshold  ->  "Off"
    row has no valid measurement         ->  "Unknown"

A TV model can also have per-scenario thresholds (see SCENARIO_THRESHOLDS).
Scenario names are matched ignoring case and spaces:
  - "HDMI"              -> applies to both HDMI (ACR=ON) and HDMI (ACR=OFF)
  - "HDMI (ACR=OFF)"    -> applies only to HDMI (ACR=OFF)
A tagged entry wins over an untagged one for the same scenario.

Usage:
    python label_experiments.py tizen webos             # by TV model name
    python label_experiments.py --all                   # every model with a threshold
    python label_experiments.py path/to/results.csv     # explicit file
    python label_experiments.py tizen --threshold 25    # override threshold
    python label_experiments.py tizen --in-place        # overwrite input CSV
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_VOLUME_RESULTS_DIR = PROJECT_ROOT / "data" / "volume_results"
DEFAULT_RESULTS_FILE = "traffic_volume.csv"

# Default outgoing bytes/sec threshold per TV model (folder_name)
THRESHOLDS = {
    "tizen": 20,        # Samsung Tizen
    "webos": 200,       # LG webOS
    "roku_roku": 100,   # Roku OS, Roku TV
    "roku_tcl": 88,     # Roku OS, TCL TV
    "google": 1,        # Google TV
    "fire": 1.3,        # Fire TV
    "smartcast": 100,   # Vizio SmartCast (default; see per-scenario overrides below)
}

# Per-scenario overrides: {tv_model: {scenario_name: threshold}}
# No ACR tag in the name  -> applies to both ACR=ON and ACR=OFF.
# With an ACR tag         -> applies only to that ACR state.
SCENARIO_THRESHOLDS = {
    "smartcast": {
        "HDMI": 180,
        "YouTube": 365,
    },
    "roku_tcl": {
        "Antenna (ACR=OFF)": 250,
        "Antenna 10.1 (ACR=OFF)": 210,
        "Antenna 14.1 (ACR=OFF)": 210,
    },
}

# Rows with these statuses have a real measurement (no_packets = 0 bytes/sec)
VALID_STATUSES = {"ok", "no_packets"}

ACR_TAG = re.compile(r"[\(\[]?\s*acr\s*=\s*(on|off)\s*[\)\]]?", re.IGNORECASE)


def normalize_scenario(name):
    """'YouTube (ACR=ON)' -> 'youtube'"""
    return "".join(ACR_TAG.sub("", str(name)).lower().split())


def acr_state(name):
    """'YouTube (ACR=ON)' -> 'on', 'HDMI' -> None"""
    m = ACR_TAG.search(str(name))
    return m.group(1).lower() if m else None


def scenario_key(name):
    return normalize_scenario(name), acr_state(name)


# Pre-normalise override keys once: {model: {(scenario, acr_state_or_None): threshold}}
_SCENARIO_LOOKUP = {
    model: {scenario_key(k): v for k, v in overrides.items()}
    for model, overrides in SCENARIO_THRESHOLDS.items()
}


def get_threshold(model, action_name):
    overrides = _SCENARIO_LOOKUP.get(model, {})
    scenario, state = scenario_key(action_name)
    if (scenario, state) in overrides:        # exact: scenario + ACR state
        return overrides[(scenario, state)]
    if (scenario, None) in overrides:         # untagged: any ACR state
        return overrides[(scenario, None)]
    return THRESHOLDS.get(model)


def resolve_input(arg):
    """Accept either a CSV path or a TV model name."""
    path = Path(arg)
    if path.suffix == ".csv" or path.exists():
        return path
    return DATA_VOLUME_RESULTS_DIR / arg / DEFAULT_RESULTS_FILE


def label_row(row, threshold_override, fallback_model):
    if "status" in row and pd.notna(row["status"]) and row["status"] not in VALID_STATUSES:
        return pd.Series({"threshold": None, "label": "Unknown"})

    model = row["tv_model"] if pd.notna(row.get("tv_model")) else fallback_model
    if threshold_override is not None:
        threshold = threshold_override
    else:
        threshold = get_threshold(model, row.get("action_name", ""))
    rate = pd.to_numeric(row.get("outgoing_bytes_per_sec"), errors="coerce")

    if threshold is None or pd.isna(rate):
        return pd.Series({"threshold": threshold, "label": "Unknown"})
    return pd.Series({"threshold": threshold, "label": "On" if rate >= threshold else "Off"})


def label_file(csv_path, threshold_override=None, in_place=False):
    df = pd.read_csv(csv_path)
    if "outgoing_bytes_per_sec" not in df.columns:
        print(f"ERROR: 'outgoing_bytes_per_sec' column missing in {csv_path}")
        return False

    if "tv_model" not in df.columns:
        df["tv_model"] = csv_path.parent.name
    fallback_model = csv_path.parent.name

    models = set(df["tv_model"].dropna().unique()) or {fallback_model}
    if threshold_override is None:
        unknown = sorted(m for m in models if m not in THRESHOLDS)
        if unknown:
            print(f"Warning: no threshold defined for {unknown}; those rows will be 'Unknown'. "
                  f"Use --threshold to set one.")

        # Warn about overrides that match no scenario (likely a naming mismatch)
        if "action_name" in df.columns:
            for model in models & _SCENARIO_LOOKUP.keys():
                keys = set(df.loc[df["tv_model"] == model, "action_name"].map(scenario_key))
                names = {s for s, _ in keys}
                for original in SCENARIO_THRESHOLDS[model]:
                    scenario, state = scenario_key(original)
                    hit = (scenario, state) in keys if state else scenario in names
                    if not hit:
                        print(f"Warning: '{model}' override for scenario '{original}' "
                              f"matched no rows.")

    # Drop old label columns so re-running doesn't duplicate them
    df = df.drop(columns=[c for c in ("threshold", "label") if c in df.columns])
    df[["threshold", "label"]] = df.apply(
        label_row, axis=1, threshold_override=threshold_override, fallback_model=fallback_model
    )

    out_path = csv_path if in_place else csv_path.with_name(f"{csv_path.stem}_labeled.csv")
    df.to_csv(out_path, index=False)

    counts = df["label"].value_counts()
    print(f"✓ {csv_path}")
    print(f"    On: {counts.get('On', 0)}   Off: {counts.get('Off', 0)}   "
          f"Unknown: {counts.get('Unknown', 0)}")
    print(f"    → {out_path}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label experiment windows as On/Off")
    parser.add_argument("inputs", nargs="*",
                        help="TV model names (e.g. tizen) or paths to traffic volume CSVs")
    parser.add_argument("--all", action="store_true",
                        help="Process every TV model that has a threshold defined")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Override the threshold (bytes/sec) for all inputs and scenarios")
    parser.add_argument("--in-place", action="store_true",
                        help="Overwrite the input CSV instead of writing *_labeled.csv")
    args = parser.parse_args()

    inputs = list(args.inputs)
    if args.all:
        inputs += [m for m in THRESHOLDS if m not in inputs]
    if not inputs:
        parser.error("give at least one TV model / CSV path, or use --all")

    ok = True
    for item in inputs:
        csv_path = resolve_input(item)
        if not csv_path.exists():
            print(f"✗ Not found: {csv_path}")
            ok = False
            continue
        ok &= label_file(csv_path, args.threshold, args.in_place)

    sys.exit(0 if ok else 1)