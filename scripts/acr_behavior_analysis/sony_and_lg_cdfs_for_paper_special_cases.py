"""
Multi-TV CDF comparison figure (side-by-side subplots).

Generates one combined PDF with two subplots: one for each TV.

Configure TV1_CSV_PATH, TV2_CSV_PATH, and SCENARIOS below, then run:
    python plot_two_tvs_cdf.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# -- Configuration -------------------------------------------------------

TV_IP_PREFIX = "192.168.14."
BIN_SIZE_SEC = 1

# CSV files for each TV
TV2_CSV_PATH = Path("/home/mammadovi/everything_ACR_on_achtung/acr_domains/Sony/216.183.117.80.csv")
TV1_CSV_PATH = Path("/home/mammadovi/everything_ACR_on_achtung/acr_domains/LG/tkacrXXX.alphonso.tv.csv")

# TV names for display
TV2_NAME = "(b) Sony Google TV"
TV1_NAME = "(a) webOS (LG TV)"

# Scenarios: (label, start_time, end_time)
TV2_SCENARIOS = [
    ("Antenna Channel", "2026-04-24 17:57:00", "2026-04-24 18:12:00"),
    ("Antenna Dynamic No Audio", "2026-04-24 20:11:30", "2026-04-24 20:26:30"),
    ("Antenna Black + Audio", "2026-04-23 22:31:30", "2026-04-23 22:46:30"),
]

TV1_SCENARIOS = [
    ("Antenna Channel", "2026-04-24 22:54:11", "2026-04-24 23:11:02"),
    ("Antenna Dynamic No Audio", "2026-04-24 17:01:00", "2026-04-24 17:16:02"),
    ("Antenna Black + Audio", "2026-04-23 04:39:00", "2026-04-23 04:54:02"),
]

# Output folder
OUTPUT_DIR = Path("scenario_plots_comparison")

# -- Helpers ---------------------------------------------------------------

def is_tv_ip(ip) -> bool:
    """Check if IP matches TV IP prefix."""
    return isinstance(ip, str) and ip.startswith(TV_IP_PREFIX)


def load_and_filter(csv_path: Path, start_time, end_time) -> pd.DataFrame:
    """Load CSV and filter by time range."""
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]

    if "ans_type" in df.columns:
        df = df[df["ans_type"].isna()]

    df["est_time"] = pd.to_datetime(df["est_time"], errors="coerce")
    df = df.dropna(subset=["est_time"])

    if start_time:
        df = df[df["est_time"] >= pd.to_datetime(start_time)]
    if end_time:
        df = df[df["est_time"] <= pd.to_datetime(end_time)]

    return df


def build_signal(df: pd.DataFrame) -> np.ndarray:
    """
    Build upload traffic signal from dataframe.
    Returns array of per-second upload bytes (exactly 900 seconds = 15 minutes).
    """
    upload = df[df["src_ip"].apply(is_tv_ip)].copy()
    upload["packet_size"] = pd.to_numeric(upload["packet_size"], errors="coerce").fillna(0)
    upload["bin"] = upload["est_time"].dt.floor(f"{BIN_SIZE_SEC}s")
    binned = upload.groupby("bin")["packet_size"].sum()
    
    full_index = pd.date_range(binned.index.min(), binned.index.max(),
                               freq=f"{BIN_SIZE_SEC}s")
    signal = binned.reindex(full_index, fill_value=0).values.astype(float)

    # Force exactly 15 minutes (900 seconds)
    target = 15 * 60
    if len(signal) < target:
        signal = np.pad(signal, (0, target - len(signal)))
    else:
        signal = signal[:target]

    return signal


def plot_combined_cdf_two_tvs(tv1_scenarios: list[tuple[str, np.ndarray]], 
                               tv2_scenarios: list[tuple[str, np.ndarray]],
                               tv1_name: str,
                               tv2_name: str,
                               output_dir: Path) -> None:
    """
    Plot CDFs for 2 TVs in side-by-side subplots.
    
    Args:
        tv1_scenarios: list of (label, signal) tuples for TV1
        tv2_scenarios: list of (label, signal) tuples for TV2
        tv1_name: display name for TV1
        tv2_name: display name for TV2
        output_dir: directory to save PDF
    """
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))
    #fig.suptitle("Upload Traffic CDFs", fontsize=14, fontweight="bold")
    
    # ---- Plot TV1 ----
    for i, (label, signal) in enumerate(tv1_scenarios):
        values = sorted(signal[signal > 0])
        if not values:
            print(f"  [{tv1_name} - {label}] no upload data — skipped")
            continue
        n = len(values)
        y = np.arange(1, n + 1) / n
        ax1.step(values, y, label=label, color=colors[i % len(colors)],
                linewidth=3, where="post", alpha=0.8)
    
    ax1.set_title(tv1_name, fontsize=20, fontweight="bold")
    ax1.set_xlabel("Upload Traffic (bytes/sec)", fontsize=16, fontweight="bold")
    ax1.set_ylabel("CDF", fontsize=16, fontweight="bold")
    ax1.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    ax1.legend(fontsize=15.5, loc="upper left", framealpha=0.95)
    ax1.set_xscale("log")
    ax1.tick_params(labelsize=16)
    for spine in ax1.spines.values():
        spine.set_linewidth(2)
    # ---- Plot TV2 ----
    for i, (label, signal) in enumerate(tv2_scenarios):
        values = sorted(signal[signal > 0])
        if not values:
            print(f"  [{tv2_name} - {label}] no upload data — skipped")
            continue
        n = len(values)
        y = np.arange(1, n + 1) / n
        ax2.step(values, y, label=label, color=colors[i % len(colors)],
                linewidth=3, where="post", alpha=0.8)
    
    ax2.set_title(tv2_name, fontsize=20, fontweight="bold")
    ax2.set_xlabel("Upload Traffic (bytes/sec)", fontsize=16, fontweight="bold")
    ax2.set_ylabel("CDF", fontsize=16, fontweight="bold")
    ax2.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    ax2.legend(fontsize=15.5, loc="upper left", framealpha=0.95)
    ax2.set_xscale("log")
    ax2.tick_params(labelsize=16)
    for spine in ax1.spines.values():
        spine.set_linewidth(2)
    fig.tight_layout(pad = 2)
    out = output_dir / "cdf_two_tvs.pdf"
    fig.savefig(out, bbox_inches="tight", dpi=300)
    print(f"  Saved: {out}")
    plt.close(fig)


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Validate CSV files exist
    if not TV1_CSV_PATH.exists():
        print(f"ERROR: TV1 CSV not found: {TV1_CSV_PATH}")
        raise SystemExit(1)
    
    if not TV2_CSV_PATH.exists():
        print(f"ERROR: TV2 CSV not found: {TV2_CSV_PATH}")
        raise SystemExit(1)

    tv1_signals = []
    tv2_signals = []

    # ---- Process TV1 ----
    print(f"\n{'='*60}")
    print(f"Processing {TV1_NAME}")
    print(f"{'='*60}")
    
    for label, start_time, end_time in TV1_SCENARIOS:
        print(f"\n  Scenario: {label}")
        df = load_and_filter(TV1_CSV_PATH, start_time, end_time)
        
        if df.empty:
            print(f"    WARNING: no data — skipped")
            continue
        
        print(f"    Packets: {len(df)}")
        signal = build_signal(df)
        print(f"    Signal: {len(signal)}s ({len(signal)/60:.1f} min)")
        tv1_signals.append((label, signal))

    # ---- Process TV2 ----
    print(f"\n{'='*60}")
    print(f"Processing {TV2_NAME}")
    print(f"{'='*60}")
    
    for label, start_time, end_time in TV2_SCENARIOS:
        print(f"\n  Scenario: {label}")
        df = load_and_filter(TV2_CSV_PATH, start_time, end_time)
        
        if df.empty:
            print(f"    WARNING: no data — skipped")
            continue
        
        print(f"    Packets: {len(df)}")
        signal = build_signal(df)
        print(f"    Signal: {len(signal)}s ({len(signal)/60:.1f} min)")
        tv2_signals.append((label, signal))

    # ---- Generate combined CDF figure ----
    print(f"\n{'='*60}")
    print("Generating combined CDF figure...")
    print(f"{'='*60}\n")
    
    plot_combined_cdf_two_tvs(tv1_signals, tv2_signals, TV1_NAME, TV2_NAME, OUTPUT_DIR)
    
    print("Done.")