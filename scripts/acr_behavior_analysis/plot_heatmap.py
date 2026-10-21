"""
Draw heatmaps from the labeled traffic volume CSVs as two horizontal
heatmaps stacked vertically:

    (a) ACR opted in   -> scenarios whose action_name contains "ACR=ON"
    (b) ACR opted out  -> scenarios whose action_name contains "ACR=OFF"

Rows = TV operating systems (OS_NAMES order); all domains of a TV are
pooled. Columns = scenarios in the fixed order of SCENARIO_ORDER, shown as
angled labels under the bottom heatmap. Both heatmaps use the same rows
and columns, so they line up vertically.

Metrics:
  --metric percent (default)  % of windows labelled "On" (On runs / actual runs).
                              Scenarios with no recorded windows count as 0%.
  --metric label              Cells show On / Off / "2/3"
  --metric rate               Mean outgoing bytes/sec (log colour scale)

Usage:
    python plot_heatmap.py --all --combined          # the paper figure
    python plot_heatmap.py --all --combined --separate
    python plot_heatmap.py tizen                     # one TV only
    python plot_heatmap.py --all --combined --title  # add a figure title
"""
import argparse
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, SymLogNorm
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_VOLUME_RESULTS_DIR = PROJECT_ROOT / "data" / "volume_results"
DATA_ANALYSIS_FIGURES_DIR = PROJECT_ROOT / "data" / "analysis_figures"
LABELED_FILE = "traffic_volume_labeled.csv"

# Row order and display names (key = tv_model / folder name)
OS_NAMES = {
    "tizen":     "Tizen OS",
    "webos":     "webOS",
    "roku_roku": "Roku OS (Roku TV)",
    "roku_tcl":  "Roku OS (TCL TV)",
    "google":    "Sony Google TV",
    "fire":      "Fire OS",
    "smartcast": "SmartCast OS",
    "vidaa":     "VIDAA OS",
}
KNOWN_MODELS = list(OS_NAMES)
VALID_STATUSES = {"ok", "no_packets"}

# Column order and display names.
# Key = scenario name from the CSV without the ACR tag (case and spaces ignored).
SCENARIO_ORDER = [
    ("Antenna",      "Antenna Channel"),
    ("Antenna 10.1", "Antenna Black + Audio"),
    ("Antenna 14.1", "Antenna Dynamic No Audio"),
    ("FAST",         "First-party Streaming"),
    ("HDMI",         "HDMI"),
    ("Netflix",      "Netflix"),
    ("YouTube",      "YouTube"),
    ("Tubi",         "Tubi"),
    ("Screencast",   "Screen Mirroring"),
    ("Idle",         "Idle"),
]

PANELS = [("on", "(a) ACR opted in"), ("off", "(b) ACR opted out")]

TITLES = {
    "percent": "% of windows On",
    "label": "On/Off",
    "rate": "outgoing bytes/sec",
}
COLORBAR_LABELS = {
    "percent": "ACR Endpoint Traffic Share",
    "label": "ACR Endpoint Traffic Share",
    "rate": "Outgoing bytes/sec (mean)",
}

# ---------------------------------------------------------------- style
CMAP_NAME = "Reds"            # white -> dark red, as in the paper figure
CELL_INCHES = 0.5             # size of one square cell
GRID_COLOR = "black"
GRID_WIDTH = 2.5
CELL_FONTSIZE = 13
LABEL_FONTSIZE = 13
TITLE_FONTSIZE = 15
DARK_TEXT = "#333333"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "pdf.fonttype": 42,       # embed TrueType fonts (editable text in PDF)
    "ps.fonttype": 42,
})

ACR_TAG = re.compile(r"[\(\[]?\s*acr\s*=\s*(on|off)\s*[\)\]]?", re.IGNORECASE)


# ---------------------------------------------------------------- data

def resolve_input(arg):
    path = Path(arg)
    if path.suffix == ".csv" or path.exists():
        return path
    return DATA_VOLUME_RESULTS_DIR / arg / LABELED_FILE


def load(csv_path):
    df = pd.read_csv(csv_path)
    if "tv_model" not in df.columns:
        df["tv_model"] = csv_path.parent.name
    return df


def acr_state(action_name):
    m = ACR_TAG.search(str(action_name))
    return m.group(1).lower() if m else None


def strip_tag(action_name):
    cleaned = ACR_TAG.sub("", str(action_name))
    return re.sub(r"\s{2,}", " ", cleaned).strip(" _-") or str(action_name)


def scenario_key(name):
    """'ANTENNA 10.1 (ACR=ON)' -> 'antenna10.1'"""
    return "".join(strip_tag(name).lower().split())


ORDER_KEYS = [scenario_key(k) for k, _ in SCENARIO_ORDER]
DISPLAY_NAMES = {scenario_key(k): name for k, name in SCENARIO_ORDER}


def column_order(df):
    """All scenarios in SCENARIO_ORDER (even if missing), then any unknown ones."""
    present = list(pd.unique(df["scenario"]))
    extras = [k for k in present if k not in ORDER_KEYS]
    if extras:
        names = sorted(df.loc[df["scenario"].isin(extras), "action_name"].map(strip_tag).unique())
        print(f"Warning: scenarios not in SCENARIO_ORDER, added at the end: {names}")
        for k in extras:
            DISPLAY_NAMES.setdefault(k, strip_tag(df.loc[df["scenario"] == k, "action_name"].iloc[0]))
    return ORDER_KEYS + extras


def build_matrix(df, metric, row_key, row_order, col_order):
    """Return (values, annotations) with rows=row_order and cols=col_order."""
    if metric in ("percent", "label"):
        if "label" not in df.columns:
            raise ValueError("No 'label' column. Run label_experiments.py first, "
                             "or use --metric rate.")
        d = df[df["label"].isin(["On", "Off"])].assign(is_on=lambda x: x["label"] == "On")
        grouped = d.groupby([row_key, "scenario"])["is_on"].agg(["sum", "count"])
        values = (grouped["sum"] / grouped["count"]).unstack()
        on_counts = grouped["sum"].unstack()
        totals = grouped["count"].unstack()
    else:
        if "status" in df.columns:
            df = df[df["status"].isin(VALID_STATUSES) | df["status"].isna()]
        d = df.assign(rate=pd.to_numeric(df["outgoing_bytes_per_sec"], errors="coerce"))
        values = d.groupby([row_key, "scenario"])["rate"].mean().unstack()

    values = values.reindex(index=row_order, columns=col_order)
    if metric == "percent":
        # No recorded windows (e.g. SmartCast screen mirroring) -> 0%
        values = values.fillna(0.0)

    ann = np.full(values.shape, "", dtype=object)
    for i, r in enumerate(values.index):
        for j, c in enumerate(values.columns):
            v = values.iat[i, j]
            if pd.isna(v):
                continue
            if metric == "percent":
                pct = round(100 * v)
                ann[i, j] = f"{pct}" if pct > 0 else ""      # 0% cells stay empty
            elif metric == "label":
                on, n = int(on_counts.loc[r, c]), int(totals.loc[r, c])
                ann[i, j] = "On" if on == n else "Off" if on == 0 else f"{on}/{n}"
            else:
                ann[i, j] = f"{v:.0f}" if v >= 10 else f"{v:.1f}"

    values.columns = [DISPLAY_NAMES[c] for c in values.columns]
    values.index = [OS_NAMES.get(r, r) for r in values.index]
    return values, ann


def split_panels(df, metric, row_key):
    """Build (a) ACR=ON and (b) ACR=OFF matrices with the same rows and columns."""
    df = df.assign(acr=df["action_name"].map(acr_state))

    untagged = sorted(df.loc[df["acr"].isna(), "action_name"].astype(str).unique())
    if untagged:
        print(f"Warning: these scenarios have no ACR=ON/OFF tag and are skipped: {untagged}")

    df = df[df["acr"].notna()].assign(scenario=lambda x: x["action_name"].map(scenario_key))
    present = list(pd.unique(df[row_key]))
    row_order = [m for m in OS_NAMES if m in present] + [m for m in present if m not in OS_NAMES]
    col_order = column_order(df)

    panels = []
    for state, title in PANELS:
        part = df[df["acr"] == state]
        if part.empty:
            print(f"Warning: no scenarios tagged ACR={state.upper()}; panel '{title}' is empty.")
            panels.append((title, None, None))
            continue
        values, ann = build_matrix(part, metric, row_key, row_order, col_order)
        panels.append((title, values, ann))
    return panels


# ---------------------------------------------------------------- drawing

def make_norm_cmap(metric, panels):
    if metric in ("percent", "label"):
        cmap = plt.get_cmap(CMAP_NAME).copy()
        norm = Normalize(vmin=0, vmax=1)
    else:
        cmap = plt.get_cmap(CMAP_NAME).copy()
        vmax = max([float(np.nanmax(v.to_numpy(dtype=float)))
                    for _, v, _ in panels if v is not None and v.notna().any().any()] + [1.0])
        norm = SymLogNorm(linthresh=1, vmin=0, vmax=vmax, base=10)
    cmap.set_bad("white")
    return norm, cmap


def draw_panel(ax, values, ann, caption, norm, cmap, show_cols=True):
    n_rows, n_cols = values.shape
    data = np.ma.masked_invalid(values.to_numpy(dtype=float))
    im = ax.imshow(data, cmap=cmap, norm=norm, aspect="equal")

    for i in range(n_rows):
        for j in range(n_cols):
            text = ann[i, j]
            if not text:
                continue
            r, g, b, _ = cmap(norm(values.iat[i, j]))
            dark = (0.299 * r + 0.587 * g + 0.114 * b) < 0.55
            ax.text(j, i, text, ha="center", va="center", fontsize=CELL_FONTSIZE,
                    fontweight="bold", color="white" if dark else DARK_TEXT)

    # Scenario names: angled, under the heatmap
    ax.set_xticks(range(n_cols))
    if show_cols:
        ax.set_xticklabels(values.columns, rotation=45, ha="right", rotation_mode="anchor",
                           fontsize=LABEL_FONTSIZE, fontweight="bold")
    else:
        ax.set_xticklabels([])

    # OS names on the left
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(values.index, fontsize=LABEL_FONTSIZE, fontweight="bold")
    ax.tick_params(axis="both", which="major", length=0, pad=4)

    # Thick black cell borders and frame
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color=GRID_COLOR, linewidth=GRID_WIDTH)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(GRID_WIDTH)

    # Caption above, left-aligned: "(a) ACR opted in"
    ax.set_title(caption, loc="left", fontsize=TITLE_FONTSIZE, fontweight="bold", pad=6)
    return im


def add_colorbar(fig, im, axes, metric, threshold):
    cbar = fig.colorbar(im, ax=axes, orientation="horizontal", location="bottom",
                        fraction=0.025, aspect=30, pad=0.03)
    cbar.outline.set_linewidth(GRID_WIDTH)
    cbar.outline.set_edgecolor(GRID_COLOR)
    if metric in ("percent", "label"):
        ticks = np.linspace(0, 1, 6)
        cbar.set_ticks(ticks)
        cbar.set_ticklabels([f"{100 * t:.0f}%" for t in ticks])
    elif threshold is not None:
        cbar.ax.axvline(threshold, color="black", linewidth=2, linestyle="--")
    cbar.ax.tick_params(labelsize=LABEL_FONTSIZE - 1)
    label = COLORBAR_LABELS[metric]
    if metric == "rate" and threshold is not None:
        label += f" (dashed = threshold {threshold:g})"
    cbar.set_label(label, fontsize=LABEL_FONTSIZE + 1, fontweight="bold")


def fig_size(values, n_panels):
    n_rows, n_cols = values.shape
    label_w = 0.11 * max(len(str(r)) for r in values.index)
    width = label_w + CELL_INCHES * n_cols + 0.6
    longest_col = max(len(str(c)) for c in values.columns)
    height = (n_panels * (CELL_INCHES * n_rows + 0.45)   # heatmaps + captions
              + 0.07 * longest_col + 0.6)                  # angled labels + colour bar
    return width, height


def save(fig, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"✓ Saved: {out_path}")


def render(panels, metric, suptitle, out_path, threshold=None, separate=False):
    present = [(t, v, a) for t, v, a in panels if v is not None]
    if not present:
        print(f"✗ Nothing to plot for {out_path.name}")
        return
    norm, cmap = make_norm_cmap(metric, present)

    # (a) on top, (b) below; scenario labels only under the bottom heatmap
    fig = plt.figure(figsize=fig_size(present[0][1], len(present)), layout="constrained")
    axes = np.atleast_1d(fig.subplots(len(present), 1))
    for k, (ax, (caption, values, ann)) in enumerate(zip(axes, present)):
        im = draw_panel(ax, values, ann, caption, norm, cmap, show_cols=(k == len(present) - 1))
    add_colorbar(fig, im, list(axes), metric, threshold)
    if suptitle:
        fig.suptitle(suptitle, fontsize=TITLE_FONTSIZE, fontweight="bold")
    save(fig, out_path)

    if separate:
        for (caption, values, ann), suffix in zip(panels, ["a", "b"]):
            if values is None:
                continue
            fig = plt.figure(figsize=fig_size(values, 1), layout="constrained")
            ax = fig.subplots()
            im = draw_panel(ax, values, ann, caption, norm, cmap)
            add_colorbar(fig, im, ax, metric, threshold)
            save(fig, out_path.with_name(f"{out_path.stem}_{suffix}{out_path.suffix}"))


def model_threshold(df):
    if "threshold" in df.columns:
        t = pd.to_numeric(df["threshold"], errors="coerce").dropna().unique()
        if len(t) == 1:
            return float(t[0])
    return None


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACR opted in / opted out heatmaps")
    parser.add_argument("inputs", nargs="*", help="TV model names or CSV paths")
    parser.add_argument("--all", action="store_true", help="Use every known TV model")
    parser.add_argument("--metric", choices=["percent", "label", "rate"], default="percent")
    parser.add_argument("--combined", action="store_true",
                        help="Put all inputs into one figure (one row per TV OS)")
    parser.add_argument("--separate", action="store_true",
                        help="Also save panels (a) and (b) as separate files")
    parser.add_argument("--title", action="store_true", help="Add a figure title")
    parser.add_argument("--format", default="pdf", help="Output format (pdf, png, svg)")
    parser.add_argument("--output", default=None, help="Output path (combined mode only)")
    args = parser.parse_args()

    inputs = list(args.inputs)
    if args.all:
        inputs += [m for m in KNOWN_MODELS if m not in inputs]
    if not inputs:
        parser.error("give at least one TV model / CSV path, or use --all")

    frames = []
    for item in inputs:
        path = resolve_input(item)
        if not path.exists():
            print(f"✗ Not found: {path}")
            continue
        frames.append(load(path))
    if not frames:
        sys.exit(1)

    try:
        if args.combined:
            df = pd.concat(frames, ignore_index=True)
            panels = split_panels(df, args.metric, "tv_model")
            out = Path(args.output) if args.output else \
                DATA_ANALYSIS_FIGURES_DIR / "heatmaps" / f"all_models_{args.metric}.{args.format}"
            title = TITLES[args.metric] if args.title else None
            render(panels, args.metric, title, out, separate=args.separate)
        else:
            for df in frames:
                model = str(df["tv_model"].iloc[0])
                panels = split_panels(df, args.metric, "tv_model")
                out = DATA_ANALYSIS_FIGURES_DIR / model / "heatmaps" / f"{model}_{args.metric}.{args.format}"
                title = f"{OS_NAMES.get(model, model)}: {TITLES[args.metric]}" if args.title else None
                render(panels, args.metric, title, out, model_threshold(df),
                       separate=args.separate)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)