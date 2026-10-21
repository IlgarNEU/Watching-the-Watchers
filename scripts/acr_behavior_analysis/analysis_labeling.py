"""
Compute the traffic volume between the TV and a single endpoint (domain)
during one experiment window.

Prints exactly one JSON object to stdout so the caller can parse it.
All diagnostics go to stderr.

Usage:
    analysis.py <input_dir> <start_time> <end_time> <action_name> <domain> <device_name> <mac(s)> [--skip-minutes N]
"""
import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

PACKET_TIME_FMT = "%Y-%m-%d %H:%M:%S.%f"
WINDOW_TIME_FMT = "%Y-%m-%d %H:%M:%S"
REQUIRED_COLS = ["est_time", "packet_size", "src_mac", "dst_mac"]
DEFAULT_MAC = "04:e4:b6:74:dd:94"


def log(msg):
    print(msg, file=sys.stderr)


def parse_macs(mac_input):
    return [m.strip().lower() for m in str(mac_input).split(",") if m.strip()]


def compute_traffic_volume(csv_file, macs, start_time_str, end_time_str, skip_minutes=5.0):
    """Return a dict of byte/packet counts for traffic to/from `macs` in the window."""
    window_start = pd.to_datetime(start_time_str, format=WINDOW_TIME_FMT, errors="coerce")
    window_end = pd.to_datetime(end_time_str, format=WINDOW_TIME_FMT, errors="coerce")
    if pd.isna(window_start) or pd.isna(window_end):
        raise ValueError(f"Could not parse window times: {start_time_str!r}, {end_time_str!r}")

    # Same warm-up skip as the original analyze_traffic_volume (default 5 min)
    effective_start = window_start + timedelta(minutes=skip_minutes)
    duration = max((window_end - effective_start).total_seconds(), 0.0)

    result = {
        "effective_start": effective_start.strftime(WINDOW_TIME_FMT),
        "duration_seconds": duration,
        "outgoing_bytes": 0,
        "outgoing_packets": 0,
        "outgoing_bytes_per_sec": 0.0,
        "incoming_bytes": 0,
        "incoming_packets": 0,
        "incoming_bytes_per_sec": 0.0,
        "total_bytes": 0,
        "total_packets": 0,
        "status": "ok",
    }

    # Only load the columns we need (much faster on large captures)
    df = pd.read_csv(csv_file, usecols=lambda c: c.strip().lower() in REQUIRED_COLS)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s) in {csv_file}: {missing}")

    df["src_mac"] = df["src_mac"].astype(str).str.strip().str.lower()
    df["dst_mac"] = df["dst_mac"].astype(str).str.strip().str.lower()
    df = df[df["src_mac"].isin(macs) | df["dst_mac"].isin(macs)].copy()

    df["est_time"] = pd.to_datetime(df["est_time"], format=PACKET_TIME_FMT, errors="coerce")
    df = df.dropna(subset=["est_time"])
    df = df[(df["est_time"] >= effective_start) & (df["est_time"] <= window_end)].copy()

    if df.empty:
        # Zero traffic is a valid measurement, so we still return a row
        result["status"] = "no_packets"
        return result

    df["packet_size"] = pd.to_numeric(df["packet_size"], errors="coerce").fillna(0)

    outgoing = df[df["src_mac"].isin(macs)]
    incoming = df[df["dst_mac"].isin(macs)]

    out_bytes = int(outgoing["packet_size"].sum())
    in_bytes = int(incoming["packet_size"].sum())

    result.update({
        "outgoing_bytes": out_bytes,
        "outgoing_packets": len(outgoing),
        "outgoing_bytes_per_sec": out_bytes / duration if duration > 0 else 0.0,
        "incoming_bytes": in_bytes,
        "incoming_packets": len(incoming),
        "incoming_bytes_per_sec": in_bytes / duration if duration > 0 else 0.0,
        "total_bytes": int(df["packet_size"].sum()),
        "total_packets": len(df),
    })
    return result


def main():
    parser = argparse.ArgumentParser(description="Compute traffic volume for one domain/window")
    parser.add_argument("input_dir")
    parser.add_argument("start_time")
    parser.add_argument("end_time")
    parser.add_argument("action_name")
    parser.add_argument("domain")
    parser.add_argument("device_name", nargs="?", default="unknown")
    parser.add_argument("mac", nargs="?", default=DEFAULT_MAC)
    parser.add_argument("--skip-minutes", type=float, default=5.0,
                        help="Minutes to skip at the start of each window (default: 5)")
    args = parser.parse_args()

    record = {
        "tv_model": args.device_name,
        "domain": args.domain,
        "action_name": args.action_name,
        "start_time": args.start_time,
        "end_time": args.end_time,
    }

    csv_file = Path(args.input_dir) / f"{args.domain}.csv"
    if not csv_file.exists():
        log(f"Domain CSV not found: {csv_file}")
        record["status"] = "missing_csv"
    else:
        record.update(compute_traffic_volume(
            csv_file, parse_macs(args.mac), args.start_time, args.end_time, args.skip_minutes
        ))

    print(json.dumps(record))


if __name__ == "__main__":
    main()