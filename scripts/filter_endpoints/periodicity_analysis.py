import numpy as np
import pandas as pd
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
import warnings
import argparse
import sys
warnings.filterwarnings("ignore")

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"
DATA_INDIVIDUAL_DOMAINS_DIR = PROJECT_ROOT / "data" / "individual_domain_csvs"
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_PERIODICITY_RESULTS_DIR = PROJECT_ROOT / "data" / "periodicity_results"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Periodicity Analysis for TV Network Traffic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required: folder name
    parser.add_argument(
        "folder_name",
        help="TV model folder name (e.g., samsung)",
        metavar="FOLDER"
    )

    # Optional: custom filenames
    parser.add_argument(
        "--domains-file",
        type=str,
        default="ratio.csv",
        help="Domains CSV filename (default: ratio.csv)",
        metavar="FILE"
    )
    parser.add_argument(
        "--timing-file",
        type=str,
        default="timing_periodicity.csv",
        help="Timing CSV filename (default: timing_periodicity.csv)",
        metavar="FILE"
    )

    # Thresholds (optional, with defaults)
    parser.add_argument(
        "--autocorr-threshold",
        type=float,
        default=0.15,
        help="Autocorrelation threshold for periodicity (default: 0.15)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--min-density",
        type=float,
        default=0.45,
        help="Minimum burst density (default: 0.45)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--high-density-bypass",
        type=float,
        default=0.75,
        help="High density bypass threshold (default: 0.75)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--reference-runs",
        type=int,
        default=5,
        help="Number of reference runs (default: 5)",
        metavar="INT"
    )
    parser.add_argument(
        "--period-min",
        type=float,
        default=0.5,
        help="Minimum detectable period in seconds (default: 0.5)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--period-max",
        type=float,
        default=180.0,
        help="Maximum detectable period in seconds (default: 180.0)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--clip-percentile",
        type=float,
        default=95,
        help="Spike clipping percentile (default: 95)",
        metavar="FLOAT"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output during analysis"
    )

    return parser.parse_args()



DOMAINS_CSV = None
TRAFFIC_DIR = None
TIMING_CSV = None
OUTPUT_DIR = None
TRAFFIC_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S.%f"
TIMING_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
TIMING_BUFFER = pd.Timedelta("0.5s")
AUTOCORR_THRESHOLD = None
MIN_BURST_DENSITY = None
HIGH_DENSITY_BYPASS = None
K_REFERENCE_RUNS = None
BIN_SIZE_MIN = 0.5
BIN_SIZE_MAX = 30.0
PERIOD_MIN = None
PERIOD_MAX = None
CLIP_PERCENTILE = None
VERBOSE = False


def init_config(args):
    global DOMAINS_CSV, TRAFFIC_DIR, TIMING_CSV, OUTPUT_DIR
    global AUTOCORR_THRESHOLD, MIN_BURST_DENSITY, HIGH_DENSITY_BYPASS
    global K_REFERENCE_RUNS, PERIOD_MIN, PERIOD_MAX, CLIP_PERCENTILE, VERBOSE

    folder_name = args.folder_name

    # Construct paths
    DOMAINS_CSV = DATA_FILTERING_RESULTS_DIR / folder_name / args.domains_file
    TRAFFIC_DIR = DATA_INDIVIDUAL_DOMAINS_DIR / folder_name
    TIMING_CSV = DATA_TIMINGS_DIR / folder_name / args.timing_file
    OUTPUT_DIR = DATA_PERIODICITY_RESULTS_DIR / folder_name
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    AUTOCORR_THRESHOLD = args.autocorr_threshold
    MIN_BURST_DENSITY = args.min_density
    HIGH_DENSITY_BYPASS = args.high_density_bypass
    K_REFERENCE_RUNS = args.reference_runs
    PERIOD_MIN = args.period_min
    PERIOD_MAX = args.period_max
    CLIP_PERCENTILE = args.clip_percentile
    VERBOSE = args.verbose

    if not Path(DOMAINS_CSV).exists():
        print(f"[ERROR] Domains CSV not found: {DOMAINS_CSV}", file=sys.stderr)
        sys.exit(1)
    if not Path(TRAFFIC_DIR).exists():
        print(f"[ERROR] Traffic directory not found: {TRAFFIC_DIR}", file=sys.stderr)
        sys.exit(1)
    if not Path(TIMING_CSV).exists():
        print(f"[ERROR] Timing CSV not found: {TIMING_CSV}", file=sys.stderr)
        sys.exit(1)

    if AUTOCORR_THRESHOLD < 0 or AUTOCORR_THRESHOLD > 1:
        print(f"[ERROR] autocorr-threshold must be in [0, 1], got {AUTOCORR_THRESHOLD}", file=sys.stderr)
        sys.exit(1)
    if MIN_BURST_DENSITY < 0 or MIN_BURST_DENSITY > 1:
        print(f"[ERROR] min-density must be in [0, 1], got {MIN_BURST_DENSITY}", file=sys.stderr)
        sys.exit(1)
    if PERIOD_MIN <= 0 or PERIOD_MAX <= 0:
        print(f"[ERROR] period-min and period-max must be positive", file=sys.stderr)
        sys.exit(1)
    if PERIOD_MIN >= PERIOD_MAX:
        print(f"[ERROR] period-min must be < period-max", file=sys.stderr)
        sys.exit(1)

    if VERBOSE:
        print("\n" + "="*70)
        print("CONFIGURATION LOADED")
        print("="*70)
        print(f"Domains CSV        : {DOMAINS_CSV}")
        print(f"Traffic Directory  : {TRAFFIC_DIR}")
        print(f"Timing CSV         : {TIMING_CSV}")
        print(f"Output Directory   : {OUTPUT_DIR}")
        print(f"\nThresholds:")
        print(f"  Autocorr threshold  : {AUTOCORR_THRESHOLD}")
        print(f"  Min burst density   : {MIN_BURST_DENSITY}")
        print(f"  High density bypass : {HIGH_DENSITY_BYPASS}")
        print(f"  Reference runs      : {K_REFERENCE_RUNS}")
        print(f"  Period range        : {PERIOD_MIN}s – {PERIOD_MAX}s")
        print(f"  Clip percentile     : {CLIP_PERCENTILE}")
        print("="*70 + "\n")




def load_domains(csv_path: str):
    df = pd.read_csv(csv_path)
    if "domain" not in df.columns:
        raise ValueError(
            f"Domains CSV must have a 'domain' column. "
            f"Found columns: {df.columns.tolist()}"
        )
    domains = df["domain"].dropna().unique().tolist()
    if VERBOSE:
        print(f"[load_domains] Loaded {len(domains)} unique domains")
    return domains


def get_traffic_csv_path(domain: str) -> str:
    return str(Path(TRAFFIC_DIR) / f"{domain}.csv")



def load_traffic(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["est_time"] = pd.to_datetime(df["est_time"], format=TRAFFIC_TIMESTAMP_FMT)

    is_dns = (
        df["qry_name"].notna() & (df["qry_name"].astype(str).str.strip() != "") |
        df["ans_name"].notna() & (df["ans_name"].astype(str).str.strip() != "")
    )
    df_data = df[~is_dns].copy()
    if VERBOSE:
        print(f"[load] Total rows: {len(df):,}  |  "
              f"DNS filtered: {is_dns.sum():,}  |  "
              f"Data rows kept: {len(df_data):,}")
    return df_data


def load_timing(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["start_time"] = pd.to_datetime(df["start_time"], format=TIMING_TIMESTAMP_FMT)
    df["end_time"]   = pd.to_datetime(df["end_time"],   format=TIMING_TIMESTAMP_FMT)
    return df




def slice_runs(traffic: pd.DataFrame, timing: pd.DataFrame) -> dict:
    runs_by_action = {}
    for _, row in timing.iterrows():
        action = row["action_name"]
        mask = (
            (traffic["est_time"] >= row["start_time"] - TIMING_BUFFER) &
            (traffic["est_time"] <= row["end_time"]   + TIMING_BUFFER)
        )
        run_df = traffic[mask].copy()
        runs_by_action.setdefault(action, []).append(run_df)

    for action, runs in runs_by_action.items():
        durations = [
            (r["est_time"].max() - r["est_time"].min()).total_seconds()
            for r in runs if len(r) > 1
        ]
        n_nonempty = sum(1 for r in runs if len(r) > 0)
        med_dur = np.median(durations) if durations else 0
        if VERBOSE:
            print(f"[slice] {action}: {len(runs)} runs, "
                  f"{n_nonempty} non-empty, median duration={med_dur:.0f}s")
            if med_dur > 0 and med_dur < PERIOD_MAX * 5:
                print(f"  [warn] Median run duration ({med_dur:.0f}s) < 5× max period "
                      f"({PERIOD_MAX}s). Long periods may not be reliably detected.")

    return runs_by_action




def auto_bin_size(run_df: pd.DataFrame) -> float:
    if len(run_df) < 2:
        return BIN_SIZE_MIN
    duration = (run_df["est_time"].max() - run_df["est_time"].min()).total_seconds()
    return round(max(BIN_SIZE_MIN, min(BIN_SIZE_MAX, duration / 100.0)), 1)


def build_time_series(run_df: pd.DataFrame, bin_size: float):
    if len(run_df) == 0:
        return np.array([]), np.array([])

    t0       = run_df["est_time"].min()
    duration = (run_df["est_time"].max() - t0).total_seconds()

    if duration <= 0:
        return np.array([1.0]), np.array([float(run_df["packet_size"].sum())])

    n_bins      = max(1, int(np.ceil(duration / bin_size)))
    elapsed     = (run_df["est_time"] - t0).dt.total_seconds().values
    bin_indices = np.floor(elapsed / bin_size).astype(int).clip(0, n_bins - 1)

    count_series = np.zeros(n_bins)
    bytes_series = np.zeros(n_bins)
    np.add.at(count_series, bin_indices, 1)
    np.add.at(bytes_series, bin_indices, run_df["packet_size"].values)

    if np.any(count_series > 0):
        p = np.percentile(count_series[count_series > 0], CLIP_PERCENTILE)
        count_series = np.clip(count_series, 0, p)

    if np.any(bytes_series > 0):
        p = np.percentile(bytes_series[bytes_series > 0], CLIP_PERCENTILE)
        bytes_series = np.clip(bytes_series, 0, p)

    return count_series, bytes_series




def find_candidate_periods(ts: np.ndarray, bin_size: float, top_k: int = 5):
    N = len(ts)
    if N < 4:
        return np.array([]), np.array([])

    yf    = np.abs(fft(ts - ts.mean()))
    xf    = fftfreq(N, d=bin_size)
    pos   = xf > 0
    freqs = xf[pos]
    power = yf[pos]

    if len(power) == 0:
        return np.array([]), np.array([])

    peaks, _ = find_peaks(power, height=np.mean(power))
    if len(peaks) == 0:
        peaks = np.argsort(power)[-top_k:]

    top     = peaks[np.argsort(power[peaks])[-top_k:][::-1]]
    periods = 1.0 / freqs[top]
    valid   = (periods >= PERIOD_MIN) & (periods <= PERIOD_MAX)
    return periods[valid], power[top][valid]


def autocorrelation_at_lag(ts: np.ndarray, lag: int) -> float:
    n = len(ts)
    if lag <= 0 or lag >= n:
        return 0.0
    var = ts.var()
    if var == 0:
        return 0.0
    s = ts - ts.mean()
    return float(np.dot(s[:n - lag], s[lag:]) / (var * (n - lag)))


def best_period_and_score(ts: np.ndarray, bin_size: float):
    candidates, _ = find_candidate_periods(ts, bin_size)
    best_score, best_period = 0.0, None

    for period in candidates:
        lag   = int(round(period / bin_size))
        score = autocorrelation_at_lag(ts, lag)
        if score > best_score:
            best_score  = score
            best_period = period

    return best_period, best_score



def burst_density(ts: np.ndarray, bin_size: float, period: float) -> dict:
    if period <= 0 or len(ts) == 0:
        return {"expected_cycles": 0, "active_cycles": 0,
                "density": 0.0, "cycle_cv": np.nan}

    period_bins  = max(1, int(round(period / bin_size)))
    n_bins       = len(ts)
    expected     = max(1, n_bins // period_bins)
    cycle_totals = []

    for i in range(expected):
        start = i * period_bins
        end   = min(start + period_bins, n_bins)
        cycle_totals.append(float(np.sum(ts[start:end])))

    active  = sum(1 for c in cycle_totals if c > 0)
    density = active / expected if expected > 0 else 0.0

    active_vals = [c for c in cycle_totals if c > 0]
    if len(active_vals) >= 2:
        cv = float(np.std(active_vals) / np.mean(active_vals))
    else:
        cv = np.nan

    return {
        "expected_cycles": expected,
        "active_cycles":   active,
        "density":         round(density, 3),
        "cycle_cv":        round(cv, 3) if not np.isnan(cv) else np.nan,
    }



def estimate_reference(runs: list, signal: str = "count", k: int = K_REFERENCE_RUNS):
    periods, bin_sizes, used = [], [], 0

    for run_df in runs:
        if used >= k:
            break
        if len(run_df) < 4:
            continue
        bin_size           = auto_bin_size(run_df)
        count_ts, bytes_ts = build_time_series(run_df, bin_size)
        ts                 = count_ts if signal == "count" else bytes_ts
        period, score      = best_period_and_score(ts, bin_size)

        if period is not None and (score >= AUTOCORR_THRESHOLD or score >= 0.08):
            periods.append(period)
            bin_sizes.append(bin_size)
            used += 1

    if not periods:
        return None, None
    return float(np.median(periods)), float(np.median(bin_sizes))




def verify_all_runs(runs: list, ref_period: float, signal: str = "count"):
    results = []
    for i, run_df in enumerate(runs):
        if len(run_df) < 2:
            results.append({
                "run": i + 1, "score": np.nan, "passed": False,
                "n_packets": 0, "bin_size": np.nan, "duration": 0.0,
                "density": np.nan, "active_cycles": 0, "expected_cycles": 0,
                "cycle_cv": np.nan,
            })
            continue

        bin_size           = auto_bin_size(run_df)
        count_ts, bytes_ts = build_time_series(run_df, bin_size)
        ts                 = count_ts if signal == "count" else bytes_ts
        lag                = int(round(ref_period / bin_size))
        score              = autocorrelation_at_lag(ts, lag) if 0 < lag < len(ts) else np.nan
        bd                 = burst_density(ts, bin_size, ref_period)
        passed             = is_periodic(score, bd["density"])

        results.append({
            "run":            i + 1,
            "score":          score,
            "passed":         passed,
            "n_packets":      len(run_df),
            "bin_size":       bin_size,
            "duration":       (run_df["est_time"].max() - run_df["est_time"].min()).total_seconds(),
            "density":        bd["density"],
            "active_cycles":  bd["active_cycles"],
            "expected_cycles":bd["expected_cycles"],
            "cycle_cv":       bd["cycle_cv"],
        })
    return results




def analyze_single_run(run_df: pd.DataFrame, signal: str = "count"):
    if len(run_df) < 4:
        return None, 0.0, {}
    bin_size           = auto_bin_size(run_df)
    count_ts, bytes_ts = build_time_series(run_df, bin_size)
    ts                 = count_ts if signal == "count" else bytes_ts
    period, score      = best_period_and_score(ts, bin_size)
    bd                 = burst_density(ts, bin_size, period) if period else {}
    return period, score, bd



def analyze_action(action_name: str, runs: list, verbose: bool = None) -> dict:
    if verbose is None:
        verbose = VERBOSE
    if verbose:
        print(f"\n{'='*60}")
        print(f"ACTION: {action_name}  ({len(runs)} runs)")
        print(f"{'='*60}")

    result = {"action": action_name, "n_runs": len(runs)}
    single = len(runs) == 1

    for signal in ["count", "bytes"]:
        label = "Packet Count" if signal == "count" else "Byte Sum"
        if verbose:
            print(f"\n  ── Signal: {label} ──")

        if single:
            period, score, bd = analyze_single_run(runs[0], signal=signal)
            density   = bd.get("density", 0.0)
            passed    = (period is not None and is_periodic(score, density))

            if verbose:
                if period is None:
                    print("  [!] No periodic signal found.")
                else:
                    status = "✓ PERIODIC" if passed else "✗ not periodic"
                    bypass = (not _isnan(score) and not _isnan(density) and
                              density >= HIGH_DENSITY_BYPASS and
                              score >= 0.08 and score < AUTOCORR_THRESHOLD)
                    gate_note = "  [density bypass]" if bypass else ""
                    print(f"  Period          : {period:.2f}s")
                    print(f"  Score           : {score:.3f}")
                    print(f"  Burst density   : {density:.3f}  "
                          f"({bd.get('active_cycles',0)}/{bd.get('expected_cycles',0)} cycles active)")
                    print(f"  Cycle CV        : {bd.get('cycle_cv', float('nan')):.3f}")
                    print(f"  Verdict         : {status}{gate_note}")

            result[signal] = {
                "ref_period":      period,
                "ref_binsize":     auto_bin_size(runs[0]) if len(runs[0]) >= 2 else None,
                "run_results":     [{
                    "run": 1, "score": score if period else np.nan,
                    "passed": passed, "n_packets": len(runs[0]),
                    "density": density,
                    "active_cycles":   bd.get("active_cycles", 0),
                    "expected_cycles": bd.get("expected_cycles", 0),
                    "cycle_cv":        bd.get("cycle_cv", np.nan),
                }],
                "pass_rate":       100.0 if passed else 0.0,
                "mean_score":      score if period else 0.0,
                "std_score":       0.0,
                "mean_density":    density,
                "active_cycles":   bd.get("active_cycles", 0),
                "expected_cycles": bd.get("expected_cycles", 0),
                "mean_cycle_cv":   bd.get("cycle_cv", np.nan),
            }

        else:
            ref_period, ref_binsize = estimate_reference(runs, signal=signal)

            if ref_period is None:
                if verbose:
                    print("  [!] No significant periodic signal found in reference runs.")
                result[signal] = {
                    "ref_period": None, "run_results": [],
                    "pass_rate": 0.0, "mean_score": 0.0, "std_score": 0.0,
                    "mean_density": 0.0, "active_cycles": 0,
                    "expected_cycles": 0, "mean_cycle_cv": np.nan,
                }
                continue

            if verbose:
                print(f"  Reference period : {ref_period:.2f}s  "
                      f"(ref bin size: {ref_binsize:.1f}s)")

            run_results = verify_all_runs(runs, ref_period, signal=signal)
            scores      = [r["score"]   for r in run_results if not np.isnan(r["score"])]
            densities   = [r["density"] for r in run_results if not np.isnan(r["density"])]
            cvs         = [r["cycle_cv"] for r in run_results if not np.isnan(r.get("cycle_cv", np.nan))]
            passed      = [r["passed"]  for r in run_results]
            pass_rate   = np.mean(passed) * 100 if passed else 0.0

            if verbose:
                print(f"  Pass rate       : {pass_rate:.1f}%  ({sum(passed)}/{len(runs)})")
                if scores:
                    print(f"  Mean score      : {np.mean(scores):.3f}  ±  {np.std(scores):.3f}")
                if densities:
                    print(f"  Mean density    : {np.mean(densities):.3f}")

                for r in run_results:
                    status    = "✓" if r["passed"] else "✗"
                    score_str = f"{r['score']:.3f}" if not np.isnan(r["score"]) else "  n/a"
                    den_str   = f"{r['density']:.3f}" if not np.isnan(r["density"]) else " n/a"
                    print(f"    Run {r['run']:02d}  score={score_str}  "
                          f"density={den_str}  "
                          f"cycles={r['active_cycles']}/{r['expected_cycles']}  "
                          f"pkts={r['n_packets']:4d}  {status}")

            result[signal] = {
                "ref_period":      ref_period,
                "ref_binsize":     ref_binsize,
                "run_results":     run_results,
                "pass_rate":       pass_rate,
                "mean_score":      np.mean(scores)    if scores    else 0.0,
                "std_score":       np.std(scores)     if scores    else 0.0,
                "mean_density":    np.mean(densities) if densities else 0.0,
                "mean_cycle_cv":   np.mean(cvs)       if cvs       else np.nan,
            }

    return result




def plot_action(action_result: dict, output_subdir: Path):
    action = action_result["action"]
    single = action_result["n_runs"] == 1
    fig    = plt.figure(figsize=(14, 6 if single else 10))
    fig.suptitle(f"Periodicity Analysis — {action}", fontsize=13, fontweight="bold")
    n_rows = 1 if single else 3
    gs     = gridspec.GridSpec(n_rows, 2, figure=fig, hspace=0.55, wspace=0.35)

    for col, signal in enumerate(["count", "bytes"]):
        label = "Packet Count" if signal == "count" else "Byte Sum"
        data  = action_result.get(signal, {})

        if not data or data["ref_period"] is None:
            ax = fig.add_subplot(gs[:, col])
            ax.text(0.5, 0.5, f"No periodic signal\nfound\n({label})",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=11, color="gray")
            ax.set_title(label)
            ax.axis("off")
            continue

        period  = data["ref_period"]
        density = data.get("mean_density", 0.0)
        score   = data["mean_score"]

        if single:
            ax = fig.add_subplot(gs[0, col])
            color = "#2ecc71" if data["pass_rate"] == 100 else "#e74c3c"
            bars  = ax.bar(["Score", "Density"], [score, density],
                           color=[color, "#3498db"], edgecolor="white", width=0.4)
            ax.axhline(AUTOCORR_THRESHOLD, linestyle="--", color="black",
                       linewidth=1, label=f"Score threshold ({AUTOCORR_THRESHOLD})")
            ax.axhline(MIN_BURST_DENSITY, linestyle=":", color="gray",
                       linewidth=1, label=f"Density threshold ({MIN_BURST_DENSITY})")
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.02,
                        f"{bar.get_height():.3f}",
                        ha="center", va="bottom", fontsize=9)
            rr = data["run_results"][0]
            ax.set_title(
                f"{label}\nPeriod={period:.1f}s  |  "
                f"Cycles={rr['active_cycles']}/{rr['expected_cycles']}  |  "
                f"CV={rr.get('cycle_cv', float('nan')):.2f}"
            )
            ax.set_ylim(0, 1.15)
            ax.set_ylabel("Value")
            ax.legend(fontsize=8)

        else:
            run_results = data["run_results"]
            runs_idx    = [r["run"]     for r in run_results]
            scores      = [r["score"]   if not np.isnan(r["score"])   else 0.0 for r in run_results]
            densities   = [r["density"] if not np.isnan(r["density"]) else 0.0 for r in run_results]
            colors      = ["#2ecc71" if r["passed"] else "#e74c3c" for r in run_results]

            ax1 = fig.add_subplot(gs[0, col])
            ax1.bar(runs_idx, scores, color=colors, edgecolor="white", linewidth=0.5)
            ax1.axhline(AUTOCORR_THRESHOLD, linestyle="--", color="black",
                        linewidth=1, label=f"Threshold ({AUTOCORR_THRESHOLD})")
            ax1.set_title(
                f"{label}  |  Period={period:.1f}s  |  Pass={data['pass_rate']:.0f}%"
            )
            ax1.set_xlabel("Run #")
            ax1.set_ylabel("Autocorr Score")
            ax1.set_ylim(0, 1)
            ax1.legend(fontsize=8)

            ax2 = fig.add_subplot(gs[1, col])
            ax2.bar(runs_idx, densities, color="#3498db", edgecolor="white", linewidth=0.5)
            ax2.axhline(MIN_BURST_DENSITY, linestyle="--", color="gray",
                        linewidth=1, label=f"Min density ({MIN_BURST_DENSITY})")
            ax2.set_title(f"Burst Density  (μ={np.mean(densities):.2f})")
            ax2.set_xlabel("Run #")
            ax2.set_ylabel("Density")
            ax2.set_ylim(0, 1)
            ax2.legend(fontsize=8)

            ax3 = fig.add_subplot(gs[2, col])
            ax3.hist(scores, bins=10, range=(0, 1), color="#9b59b6",
                     edgecolor="white", linewidth=0.5)
            ax3.axvline(AUTOCORR_THRESHOLD, linestyle="--", color="red",
                        linewidth=1, label="Score threshold")
            ax3.set_xlabel("Autocorr Score")
            ax3.set_ylabel("# Runs")
            ax3.set_title(
                f"Score distribution  "
                f"(μ={data['mean_score']:.2f}, σ={data['std_score']:.2f})"
            )
            ax3.legend(fontsize=8)

    safe_name = action.replace(" ", "_").replace("/", "-")
    out_path  = output_subdir / f"{safe_name}_periodicity.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    if VERBOSE:
        print(f"  [plot] Saved → {out_path}")




def save_summary(all_results: list, output_path: Path):
    rows = []
    for domain_result in all_results:
        domain = domain_result["domain"]
        for action_result in domain_result["action_results"]:
            for signal in ["count", "bytes"]:
                d = action_result.get(signal, {})
                score_val   = d.get("mean_score",   0.0)
                density_val = d.get("mean_density", 0.0)
                rows.append({
                    "domain":          domain,
                    "action":          action_result["action"],
                    "signal":          signal,
                    "n_runs":          action_result["n_runs"],
                    "ref_period_s":    d.get("ref_period"),
                    "score":           round(score_val,   3),
                    "burst_density":   round(density_val, 3),
                    "periodic":        is_periodic(score_val, density_val),
                    "active_cycles":   d.get("active_cycles",  ""),
                    "expected_cycles": d.get("expected_cycles",""),
                    "cycle_cv":        round(d.get("mean_cycle_cv", float("nan")), 3)
                                       if not _isnan(d.get("mean_cycle_cv")) else "",
                    "pass_rate_%":     round(d.get("pass_rate",  0.0), 1),
                    "std_score":       round(d.get("std_score",  0.0), 3),
                })

    df  = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"[summary] Saved → {output_path}")
    if VERBOSE:
        print(df.to_string(index=False))
    return df


def save_periodic_domains(all_domain_results: list, output_path: Path):
    domain_periodic_counts = {}
    
    for domain_result in all_domain_results:
        domain = domain_result["domain"]
        total_combinations = 0
        periodic_combinations = 0
        
        for action_result in domain_result["action_results"]:
            for signal in ["count", "bytes"]:
                d = action_result.get(signal, {})
                score_val   = d.get("mean_score",   0.0)
                density_val = d.get("mean_density", 0.0)
                
                total_combinations += 1
                
                if is_periodic(score_val, density_val):
                    periodic_combinations += 1
        
        domain_periodic_counts[domain] = (periodic_combinations, total_combinations)
    
    periodic_domains = []
    for domain, (periodic_count, total_count) in domain_periodic_counts.items():
        if periodic_count > total_count / 2: 
            periodic_domains.append(domain)
    
    periodic_domains.sort()  
    

    df = pd.DataFrame({"domain": periodic_domains})
    
    df.to_csv(output_path, index=False)
    print(f"[periodic] Saved → {output_path}")
    print(f"[periodic] Found {len(periodic_domains)} periodic domain(s):")
    for domain in periodic_domains:
        periodic_count, total_count = domain_periodic_counts[domain]
        percentage = round(periodic_count * 100 / total_count, 1)
        print(f"  ✓ {domain} ")
    
    return df


def _isnan(v):
    try:
        return np.isnan(v)
    except (TypeError, ValueError):
        return v is None


def is_periodic(score, density) -> bool:
    if _isnan(score) or _isnan(density):
        return False
    density_ok = density >= MIN_BURST_DENSITY
    score_ok   = (score >= AUTOCORR_THRESHOLD) or (
                     density >= HIGH_DENSITY_BYPASS and score >= 0.08
                 )
    return density_ok and score_ok



def process_domain(domain: str, timing_df: pd.DataFrame):
    traffic_csv_path = get_traffic_csv_path(domain)
    traffic_path = Path(traffic_csv_path)

    if not traffic_path.exists():
        print(f"[!] Traffic CSV not found for '{domain}': {traffic_csv_path}")
        return None

    if VERBOSE:
        print(f"\n{'#'*70}")
        print(f"# DOMAIN: {domain}")
        print(f"# Traffic: {traffic_csv_path}")
        print(f"{'#'*70}")

    try:
        traffic = load_traffic(str(traffic_path))
    except Exception as e:
        print(f"[ERROR] Failed to load traffic for '{domain}': {e}")
        return None

    if len(traffic) == 0:
        print(f"[!] No traffic data found for '{domain}'")
        return None

    runs_by_action = slice_runs(traffic, timing_df)

    action_results = []
    for action_name, runs in runs_by_action.items():
        result = analyze_action(action_name, runs, verbose=True)
        action_results.append(result)

    return {
        "domain": domain,
        "action_results": action_results,
    }




def main():
    if VERBOSE:
        print(f"\nLoading domains from: {DOMAINS_CSV}")
    try:
        domains = load_domains(str(DOMAINS_CSV))
    except Exception as e:
        print(f"[ERROR] Failed to load domains: {e}")
        sys.exit(1)

    if VERBOSE:
        print(f"Loading timing from: {TIMING_CSV}")
    try:
        timing = load_timing(str(TIMING_CSV))
    except Exception as e:
        print(f"[ERROR] Failed to load timing: {e}")
        sys.exit(1)

    print(f"\nProcessing {len(domains)} domain(s)...\n")

    all_domain_results = []
    for i, domain in enumerate(domains, 1):
        print(f"[{i}/{len(domains)}] {domain}...", end=" ", flush=True)
        domain_result = process_domain(domain, timing)

        if domain_result is None:
            print("✗ (skipped)")
            continue

        all_domain_results.append(domain_result)

        domain_output_dir = OUTPUT_DIR / domain
        domain_output_dir.mkdir(exist_ok=True)

        for action_result in domain_result["action_results"]:
            plot_action(action_result, domain_output_dir)

        print("✓")

    print()
    if all_domain_results:
        summary_path = OUTPUT_DIR / "summary_all_domains.csv"
        save_summary(all_domain_results, summary_path)
        
        periodic_path = OUTPUT_DIR / "periodic_domains.csv"
        save_periodic_domains(all_domain_results, periodic_path)
        
        print(f"\n✓ Processed {len(all_domain_results)}/{len(domains)} domains successfully")
    else:
        print(f"✗ No domains processed successfully")
        sys.exit(1)

    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    args = parse_arguments()
    init_config(args)
    main()