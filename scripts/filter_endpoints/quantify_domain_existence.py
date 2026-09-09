import pandas as pd
import sys
from pathlib import Path
import argparse

# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_TIMINGS_DIR = PROJECT_ROOT / "data" / "experiment_timings"
DATA_FILTERING_RESULTS_DIR = PROJECT_ROOT / "data" / "filtering_results"
DATA_DOMAIN_LISTS_DIR = PROJECT_ROOT / "data" / "domain_list_csvs"

def quantify_domain_presence(timing_csv, base_domain_csv, domain_list_dir, output_file, target_domain=None):
    timing_df = pd.read_csv(timing_csv)
    print("Columns in timing CSV:", timing_df.columns.tolist())
    base_domains_df = pd.read_csv(base_domain_csv)

    if target_domain:
        target_domains = {target_domain}
    else:
        target_domains = set(base_domains_df['base_domain'].dropna())

    acr_on = timing_df[timing_df['action_name'].str.contains('ACR=ON', na=False)]
    total = len(acr_on)

    results = []
    for _, row in acr_on.iterrows():
        action_name = str(row['action_name'])
        start_time  = str(row['start_time'])
        end_time    = str(row['end_time'])

        # NO underscores between components - same as original
        domain_file = domain_list_dir / f"{action_name}{start_time}{end_time}.csv"

        if not domain_file.exists():
            print(f"Warning: missing file for {action_name} {start_time} {end_time}")
            results.append({
                'action_name': action_name,
                'start_time' : start_time,
                'end_time'   : end_time,
                'had_traffic': None
            })
            continue

        window_domains_df = pd.read_csv(domain_file)
        window_domains_df['base_domain'] = window_domains_df['domain'].apply(
            lambda d: '.'.join(str(d).strip().split('.')[-2:]) if pd.notna(d) else None
        )
        window_base_domains = set(window_domains_df['base_domain'].dropna())
        had_traffic = bool(target_domains & window_base_domains)

        results.append({
            'action_name': action_name,
            'start_time' : start_time,
            'end_time'   : end_time,
            'had_traffic': had_traffic
        })

    results_df = pd.DataFrame(results)

    summary_rows = []
    for action, group in results_df.groupby('action_name'):
        known   = group['had_traffic'].notna()
        present = group.loc[known, 'had_traffic'].sum()
        total   = known.sum()
        missing = (~known).sum()
        pct     = 100 * present / total if total > 0 else 0

        summary_rows.append({
            'action_name'         : action,
            'windows_with_traffic': int(present),
            'total_windows'       : int(total),
            'percent'             : round(pct, 1),
            'missing_files'       : int(missing)
        })

    summary_df = pd.DataFrame(summary_rows).sort_values('action_name')

    results_df['analyzed_domain'] = target_domain if target_domain else str(target_domains)
    summary_df['analyzed_domain'] = target_domain if target_domain else str(target_domains)

    domain_slug  = target_domain.replace('.', '_') if target_domain else "all_domains"
    out_detailed = str(output_file).replace('.csv', f'_{domain_slug}.csv')
    out_summary  = str(output_file).replace('.csv', f'_{domain_slug}_per_action_summary.csv')

    pd.DataFrame(results_df).to_csv(out_detailed, index=False)
    pd.DataFrame(summary_df).to_csv(out_summary,  index=False)

    print(f"\nDetailed results saved to {out_detailed}")
    print(f"Per-action summary saved to {out_summary}")

    return results_df, summary_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Quantify domain presence in timing data')
    parser.add_argument('folder_name', help='TV model folder name (e.g., samsung)')
    parser.add_argument('--target-domain', help='Optional: analyze only a specific domain')
    
    args = parser.parse_args()
    
    folder_name = args.folder_name
    target_domain = args.target_domain
    
    # Construct paths
    timing_csv = DATA_TIMINGS_DIR / folder_name / "timing.csv"
    base_domain_csv = DATA_FILTERING_RESULTS_DIR / folder_name / "grouped_by_base.csv"
    domain_list_dir = DATA_DOMAIN_LISTS_DIR / folder_name
    output_dir = DATA_FILTERING_RESULTS_DIR / folder_name
    
    # Verify input files exist
    if not timing_csv.exists():
        print(f"Error: Timing file not found: {timing_csv}")
        sys.exit(1)
    if not base_domain_csv.exists():
        print(f"Error: Base domain CSV not found: {base_domain_csv}")
        sys.exit(1)
    if not domain_list_dir.exists():
        print(f"Error: Domain list directory not found: {domain_list_dir}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # If a specific domain is passed as argument, run for that domain only
    if target_domain:
        quantify_domain_presence(
            timing_csv      = timing_csv,
            base_domain_csv = base_domain_csv,
            domain_list_dir = domain_list_dir,
            output_file     = output_dir / "domain_presence.csv",
            target_domain   = target_domain
        )
    else:
        # Run for all domains and merge into one summary
        domains = pd.read_csv(base_domain_csv)['base_domain'].dropna().unique()
        print(f"Running analysis for {len(domains)} domains...")

        all_summaries = []
        for domain in domains:
            print(f"\n--- {domain} ---")
            _, summary_df = quantify_domain_presence(
                timing_csv      = timing_csv,
                base_domain_csv = base_domain_csv,
                domain_list_dir = domain_list_dir,
                output_file     = output_dir / "domain_presence.csv",
                target_domain   = domain
            )
            all_summaries.append(summary_df)

        # Merge all per-domain summaries into one big CSV
        merged = pd.concat(all_summaries, ignore_index=True)
        merged_path = output_dir / "all_domains_summary.csv"
        merged.to_csv(merged_path, index=False)
        print(f"\nMerged summary saved to {merged_path}")

        # Domains that appear in >75% of measurements in at least one action
        frequent = merged[merged['percent'] > 80][['analyzed_domain', 'action_name', 'windows_with_traffic', 'total_windows', 'percent']]
        frequent = frequent.sort_values(['analyzed_domain', 'percent'], ascending=[True, False])

        # One row per domain — keep the action with the highest percent
        top_domains = (
            frequent.loc[frequent.groupby('analyzed_domain')['percent'].idxmax()]
            .reset_index(drop=True)
            .sort_values('percent', ascending=False)
        )

        frequent_path    = output_dir / "frequent_domains.csv"
        top_domains_path = output_dir / "frequent_domains_top.csv"

        frequent.to_csv(frequent_path, index=False)
        top_domains.to_csv(top_domains_path, index=False)

        print(f"\nDomains appearing >80% in at least one action: {len(top_domains)}")
        print(top_domains[['analyzed_domain', 'action_name', 'percent']].to_string(index=False))
        print(f"\nAll frequent action rows saved to {frequent_path}")
        print(f"Top entry per domain saved to {top_domains_path}")