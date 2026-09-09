"""
Autocorrelation-based periodicity analysis - one subplot per TV, combined into one figure.

All TVs use autocorrelation uniformly, which is more robust than FFT
when the capture window contains only a few cycles of the dominant period.

Folder structure expected:
    acr_domains/
        Samsung/
            acr-us-prd.samsungcloud.tv.csv
        Roku TV/
            scribe.logs.roku.com.csv
        ...  (one CSV per TV folder)

Usage:
    python plot_fourier_all_tvs.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks as sp_find_peaks
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

DATA_ROOT    = Path("../acr_domains")
TV_IP_PREFIX = "192.168.14."
BIN_SIZE_SEC = 1
MIN_PERIOD   = 5
TOP_N_PEAKS  = 3
OUTPUT_FILE  = "fourier_all_tvs.pdf"

# Per-TV config: folder name → (csv filename, start_time, end_time, max_period)
TV_CONFIG = {
    "Samsung":      ("acr-us-prd.samsungcloud.tv.csv",       "2026-04-22 17:30:52", "2026-04-22 18:02:18",  70),
    "LG":           ("tkacrXX.alphonso.tv.csv",              "2026-04-24 22:55:00", "2026-04-24 23:11:00",  25),
    "Roku TV":      ("scribe.logs.roku.com.csv",             "2026-04-23 05:17:31", "2026-04-23 05:48:57",  20),
    "TCL Roku TV":  ("scribe.logs.roku.com.csv",             "2026-04-22 19:13:45", "2026-04-22 19:45:06",  20),
    "Sony":         ("216.183.117.80.csv",                   "2026-04-23 16:58:08", "2026-04-23 17:14:55", 300),
    "Fire TV":      ("gateway-ink.amazon.com.csv",           "2026-04-22 19:56:57", "2026-04-22 20:28:06",  20),
    "Vizio":        ("kinesis.us-west-2.amazonaws.com.csv",  "2026-04-22 19:51:52", "2026-04-22 20:23:37",  70),
    "Supersonic":   ("fp.us.acr.unruly.co.csv",              "2026-04-30 20:20:00", "2026-04-30 20:35:00",  10),
}

TV_OS_NAME = {
    "Samsung":     "Tizen OS",
    "LG":          "webOS",
    "Sony":        "Sony Google TV",
    "Roku TV":     "Roku OS (Roku TV)",
    "TCL Roku TV": "Roku OS (TCL TV)",
    "Fire TV":     "Fire OS",
    "Vizio":       "SmartCast OS",
    "Supersonic":  "VIDAA OS",
}

# ── Matplotlib settings for paper quality ─────────────────────────────────────

plt.rcParams.update({
    "font.family":      "serif",
    "font.size":         12,
    "axes.titlesize":    12,
    "axes.labelsize":    12,
    "xtick.labelsize":   12,
    "ytick.labelsize":   12,
    "legend.fontsize":   12,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.format":    "pdf",
    "lines.linewidth":   0.8,
    "axes.linewidth":    0.5,
    "grid.linewidth":    0.3,
    "grid.alpha":        0.3,
})


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_tv_ip(ip) -> bool:
    return isinstance(ip, str) and ip.startswith(TV_IP_PREFIX)


def load_csv(csv_path: Path, start_time, end_time) -> pd.DataFrame:
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
    upload = df[df["src_ip"].apply(is_tv_ip)].copy()
    upload["packet_size"] = pd.to_numeric(upload["packet_size"], errors="coerce").fillna(0)
    upload["bin"] = upload["est_time"].dt.floor(f"{BIN_SIZE_SEC}s")
    binned = upload.groupby("bin")["packet_size"].sum()
    full_index = pd.date_range(binned.index.min(), binned.index.max(),
                               freq=f"{BIN_SIZE_SEC}s")
    return binned.reindex(full_index, fill_value=0).values.astype(float)


# ── Autocorrelation ────────────────────────────────────────────────────────────

def compute_autocorr(signal: np.ndarray, max_period: int):
    """
    Normalized autocorrelation via FFT (efficient for long signals).
    Returns (lags_in_seconds, normalized_correlation) clipped to
    [MIN_PERIOD, max_period].
    """
    s = signal - signal.mean()
    n   = len(s)
    fft = np.fft.rfft(s, n=2 * n)           # zero-pad to avoid circular wrap
    acf = np.fft.irfft(fft * np.conj(fft))  # power spectrum → autocorrelation
    acf = acf[:n]                            # keep non-negative lags only
    acf /= acf[0] if acf[0] != 0 else 1     # normalize to [-1, 1]

    lags = np.arange(n)                      # lag in seconds (BIN_SIZE_SEC = 1)
    mask = (lags >= MIN_PERIOD) & (lags <= max_period)
    return lags[mask].astype(float), acf[mask]


def find_autocorr_peaks(lags, acf, max_period):
    """
    Return top-N peaks from the autocorrelation function.
    Minimum distance between peaks = 10% of the search range, so
    harmonics and noise bumps don't crowd out the fundamental.
    """
    if len(lags) == 0:
        return []

    min_dist = max(1, int(0.10 * (max_period - MIN_PERIOD)))

    peak_idx, _ = sp_find_peaks(acf, distance=min_dist, height=0.0)
    if len(peak_idx) == 0:
        peak_idx = np.array([np.argmax(acf)])

    top = peak_idx[np.argsort(acf[peak_idx])[::-1][:TOP_N_PEAKS]]
    return [{"period": lags[i], "magnitude": acf[i]} for i in top]


# ── Per-TV processing ──────────────────────────────────────────────────────────

def process_tv(tv_name, csv_file, start_time, end_time, max_period):
    csv_path = DATA_ROOT / tv_name / csv_file
    if not csv_path.exists():
        print(f"  [{tv_name}] WARNING: file not found: {csv_path}")
        return None, None, None, max_period

    df = load_csv(csv_path, start_time, end_time)
    if df.empty:
        print(f"  [{tv_name}] WARNING: no data after filtering")
        return None, None, None, max_period

    signal     = build_signal(df)
    lags, acf  = compute_autocorr(signal, max_period)
    peaks      = find_autocorr_peaks(lags, acf, max_period)

    print(f"  [{tv_name}] {len(signal)}s signal, top periods: "
          + ", ".join(f"{p['period']:.1f}s" for p in peaks))

    return lags, acf, peaks, max_period


# ── Plotting ───────────────────────────────────────────────────────────────────

def plot_all(results: dict) -> None:
    valid = {k: v for k, v in results.items() if v[0] is not None}
    n     = len(valid)

    if n == 0:
        print("No valid data to plot.")
        return

    ncols = 4
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(2.5 * ncols, 2.0 * nrows),
                             squeeze=False)

    peak_colors = ["#E24B4A", "#EF9F27", "#1D9E75"]

    for idx, (tv_name, (lags, acf, peaks, max_period)) in enumerate(valid.items()):
        row, col = divmod(idx, ncols)
        ax = axes[row][col]

        mask = (lags >= MIN_PERIOD) & (lags <= max_period)
        ax.fill_between(lags[mask], acf[mask], alpha=0.15, color="#888780")
        ax.plot(lags[mask], acf[mask], linewidth=0.8, color="#444444")
        ax.axhline(0, color="#888780", linewidth=0.5, linestyle=":")

        for i, p in enumerate(peaks):
            ax.axvline(p["period"], color=peak_colors[i],
                       linewidth=1.0, linestyle="--", alpha=0.9,
                       label=f"{p['period']:.1f}s")
            ymin, ymax = ax.get_ylim()
            ax.text(p["period"] + (max_period - MIN_PERIOD) * 0.02,
                    ymin + (ymax - ymin) * 0.04,
                    f"{p['period']:.1f}s",
                    color=peak_colors[i], fontsize=5.5,
                    va="bottom", ha="left")

        ax.set_title(TV_OS_NAME.get(tv_name, tv_name))
        ax.set_xlim(MIN_PERIOD, max_period * 1.05)
        ax.legend(loc="upper right", framealpha=0.7, edgecolor="0.8")
        ax.grid(True, axis="both")

    for idx in range(n, nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row][col].set_visible(False)

    fig.tight_layout(pad=0.3, h_pad=0.5, w_pad=0.4)
    fig.supxlabel("Period (s)",       fontsize=12, y=-0.02)
    fig.supylabel("Autocorrelation",  fontsize=12, x=-0.01)

    fig.savefig(OUTPUT_FILE, bbox_inches="tight")
    print(f"\nPlot saved to: {OUTPUT_FILE}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Processing TVs...\n")
    results = {}
    for tv_name, (csv_file, start_time, end_time, max_period) in TV_CONFIG.items():
        results[tv_name] = process_tv(tv_name, csv_file, start_time, end_time, max_period)

    plot_all(results)