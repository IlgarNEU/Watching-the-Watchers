"""
CDF of upload/download traffic ratios per destination domain.
One curve per TV, publication style.

Usage:
    python plot_traffic_cdf.py              # compute ratios + plot + save cache
    python plot_traffic_cdf.py --use-cache  # skip computation, plot from cache
"""

import json
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# -- Configuration -------------------------------------------------------------

DATA_ROOT    = Path("../temporary_domains_for_plot")
TV_IP_PREFIX = "192.168.14."
CACHE_FILE   = Path("key_tvs_cdf.json")
OUTPUT_FILE  = "cdf_traffic_ratios.pdf"

# tv_name: (domain_csv_stem, ratio, annotation_label)
TV_ACR_DOMAIN = {
    "Samsung":    ("acr-us-prd.samsungcloud.tv", 1.728,  "acr-us-prd.samsungcloud.tv"),
    #"Roku TV":    ("scribe.logs.roku.com",        9.909,  "scribe.logs.roku.com"),
    "LG":         ("tkacr",                       7.252,   "tkacrXXX.alphonso.tv"),
    #"TCL Roku":   ("scribe.logs.roku.com",        11.646,  "scribe.logs.roku.com"),
    "Supersonic": ("fp.us.acr.unruly.co",         6.512,   "fp.us.acr.unruly.co"),
    #"Vizio": ("kinesis.us-west-2.amazonaws.com",         1.406,   "kinesis.us-west-2.amazonaws.com"),
    #"Sony": ("216.183.117.80",         3.879,   "216.183.117.80"),
    #"Fire": ("gateway-ink.amazon.com",         7.347,   "gateway-ink.amazon.com"),

}

TV_DISPLAY_NAMES = {
    "Samsung":    "Tizen OS",
    "LG":         "webOS",
    #"Sony":       "Sony Google TV",
    #"Roku TV":    "Roku OS (Roku TV)",
    #"TCL Roku":   "Roku OS (TCL TV)",
    #"Fire":       "Fire OS",
    #"Vizio":      "SmartCast OS",
    "Supersonic": "VIDAA OS",
    #"TCL Google": "TCL Google TV",
}

# -- Helpers -------------------------------------------------------------------

def is_tv_ip(ip: str) -> bool:
    return isinstance(ip, str) and ip.startswith(TV_IP_PREFIX)


def compute_ratio(csv_path: Path) -> float | None:
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]

    if "ans_type" in df.columns:
        df = df[df["ans_type"].isna()]

    if df.empty:
        return None

    upload   = df[df["src_ip"].apply(is_tv_ip)]["packet_size"].sum()
    download = df[df["dst_ip"].apply(is_tv_ip)]["packet_size"].sum()

    if download == 0:
        return None

    return upload / download


# -- Data collection -----------------------------------------------------------

def collect_ratios() -> dict[str, list[float]]:
    tv_ratios: dict[str, list[float]] = {}

    if not DATA_ROOT.exists():
        raise FileNotFoundError(f"Data root not found: {DATA_ROOT.resolve()}")

    for tv_dir in sorted(DATA_ROOT.iterdir()):
        if not tv_dir.is_dir():
            continue

        tv_name = tv_dir.name
        ratios  = []

        for csv_file in sorted(tv_dir.glob("*.csv")):
            domain = csv_file.stem
            ratio  = compute_ratio(csv_file)
            if ratio is not None:
                ratios.append(ratio)
                print(f"  [{tv_name}] {domain}: ratio = {ratio:.3f}")
            else:
                print(f"  [{tv_name}] {domain}: skipped (no data or zero download)")

        if ratios:
            tv_ratios[tv_name] = sorted(ratios)
        else:
            print(f"  [{tv_name}]: no usable domains — skipped from plot")

    return tv_ratios


def save_cache(tv_ratios: dict[str, list[float]]) -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(tv_ratios, f, indent=2)
    print(f"Ratios cached to {CACHE_FILE}")


def load_cache() -> dict[str, list[float]]:
    with open(CACHE_FILE) as f:
        return json.load(f)


# -- Plotting ------------------------------------------------------------------

def plot_cdf(tv_ratios: dict[str, list[float]]) -> None:
    tv_ratios = {
        "Samsung":   tv_ratios["Samsung"],
        "LG":        tv_ratios["LG"],
        #"Roku TV":   tv_ratios["Roku TV"],
        #"TCL Roku":  tv_ratios["TCL Roku"],
        #"Sony":      tv_ratios["Sony"],
        #"Fire":      tv_ratios["Fire"],
        #"Vizio":     tv_ratios["Vizio"],
        "Supersonic": tv_ratios["Supersonic"],
        #"TCL Google": tv_ratios["TCL Google"],
    }
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "serif"]
    styles = ["-", "--", "-.", ":", (0, (3,1,1,1)), (0,(5,1)), (0,(1,1)), (0,(3,1,1,1,1,1))]
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(7, 4.5))

    # Draw CDF curves
    for i, (tv_name, ratios) in enumerate(tv_ratios.items()):
        n = len(ratios)
        y = np.arange(1, n + 1) / n
        ax.step(ratios, y,
            label=TV_DISPLAY_NAMES.get(tv_name, tv_name),
                color=colors[i % len(colors)],
                linestyle="-",
                linewidth=3.0,
                where="post")

    # Annotate ACR domain points
    X_MAX = 2.6
    inside_count  = 0
    outside_count = 0

    for i, (tv_name, ratios) in enumerate(tv_ratios.items()):
        if tv_name not in TV_ACR_DOMAIN:
            continue

        _, acr_ratio, annotation = TV_ACR_DOMAIN[tv_name]

        ratios_sorted = sorted(ratios)
        n     = len(ratios_sorted)
        idx   = sum(r <= acr_ratio for r in ratios_sorted)
        y_val = idx / n

        if acr_ratio > X_MAX:
            # stack overflow labels on the right edge from top down
            y_edge_targets = [0.91, 0.97]  # actual CDF y values on the right edge — tune to match your curves
            y_label_positions = [0.60, 0.7]  # where the labels sit — in the white space

            y_target = y_edge_targets[outside_count % len(y_edge_targets)]
            y_label  = y_label_positions[outside_count % len(y_label_positions)]

            ax.scatter(X_MAX, y_target, color=colors[i % len(colors)],
                    marker=">", s=40, zorder=5)
            ax.annotate(f"{annotation} ({acr_ratio:.1f})",
                        xy=(X_MAX, y_target),
                        xytext=(1.4, y_label),
                        fontsize=12,
                        fontweight="bold",
                        color=colors[i % len(colors)],
                        arrowprops=dict(arrowstyle="->",
                                        color=colors[i % len(colors)],
                                        lw=0.8))
            outside_count += 1
        else:
            # normal annotation inside the plot, staggered
            dx = -0.52 if inside_count % 2 == 0 else -0.05
            dy = 0.071 - inside_count * 0.12
            ax.scatter(acr_ratio, y_val, color=colors[i % len(colors)],
                    marker="o", s=40, zorder=5)
            ax.annotate(f"{annotation} ({acr_ratio:.1f})",
                        xy=(acr_ratio, y_val),
                        xytext=(acr_ratio + dx, y_val + dy),
                        fontsize=12,
                        fontweight="bold",
                        color=colors[i % len(colors)],
                        arrowprops=dict(arrowstyle="->",
                                        color=colors[i % len(colors)],
                                        lw=0.8))
            inside_count += 1

    ax.axvline(1.0, color="grey", linewidth=0.8, linestyle="--", alpha=0.6,
               label="ratio = 1 (balanced)")

    ax.set_xlim(0, 2.6)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Upload / download packet ratio", fontsize=16)
    ax.set_ylabel("Fraction of domains  <= x", fontsize=16)
    ax.tick_params(labelsize=12)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.legend(fontsize=12.5, loc="lower right", ncols=2, columnspacing=0.5)

    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, bbox_inches="tight")
    print(f"\nPlot saved to: {OUTPUT_FILE}")
    plt.show()


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":
    use_cache = "--use-cache" in sys.argv

    if use_cache and CACHE_FILE.exists():
        print(f"Loading ratios from cache ({CACHE_FILE})...")
        tv_ratios = load_cache()
    else:
        if use_cache:
            print(f"Cache not found at {CACHE_FILE}, computing from scratch...")
        else:
            print("Collecting ratios...\n")
        tv_ratios = collect_ratios()
        save_cache(tv_ratios)

    if not tv_ratios:
        print("No data found — check DATA_ROOT path and ALLOWED_DOMAINS list.")
    else:
        print(f"\nPlotting {len(tv_ratios)} TV curve(s)...")
        plot_cdf(tv_ratios)