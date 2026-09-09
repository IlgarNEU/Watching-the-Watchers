import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import json


# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_ANALYSIS_FIGURES_DIR = PROJECT_ROOT / "data" / "analysis_figures"
DATA_VOLUME_LOGS_DIR = PROJECT_ROOT / "data" / "volume_logs"


def _parse_mac_addresses(mac_input):
    """
    Parse MAC input (string or comma-separated string) into a list.
    
    Args:
        mac_input: Single MAC string or comma-separated MAC string
        
    Returns:
        List of MAC addresses
    """
    if isinstance(mac_input, str):
        # Handle comma-separated MACs: "mac1,mac2,mac3"
        if ',' in mac_input:
            return [m.strip() for m in mac_input.split(',')]
        else:
            return [mac_input.strip()]
    else:
        return [str(mac_input)]


class TrafficVisualization:
    def __init__(self, csv_file, mac='04:e4:b6:74:dd:94'):
        """
        Initialize with single MAC or list of MACs.
        
        Args:
            csv_file: Path to CSV file
            mac: Single MAC address (str) or comma-separated MAC string
        """
        self.csv_file = csv_file
        # Parse and store as list
        self.macs = _parse_mac_addresses(mac)

    def analyze_traffic_volume(self, domain, start_time_str, end_time_str, log_dir=None):
        if log_dir is None:
            log_dir = DATA_VOLUME_LOGS_DIR
        
        df = pd.read_csv(self.csv_file)
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = ['est_time', 'packet_size', 'src_ip', 'dst_ip', 'ans_type', 'src_mac', 'dst_mac']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")

        # Filter for any of the device MACs
        df = df[(df['src_mac'].isin(self.macs)) | (df['dst_mac'].isin(self.macs))]
        if df.empty:
            print(f"NO PACKETS FOUND INVOLVING ANY OF THESE MACS: {self.macs}")
            return None

        df['est_time'] = pd.to_datetime(df['est_time'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
        df = df.dropna(subset=['est_time'])
        start_time = pd.to_datetime(start_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')
        start_time  = start_time + timedelta(minutes=5)
        end_time = pd.to_datetime(end_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')

        df = df[(df['est_time'] >= start_time) & (df['est_time'] <= end_time)]
        if df.empty:
            print(f"NO PACKETS FOUND BETWEEN {start_time} and {end_time}")
            return None

        df['packet_size'] = pd.to_numeric(df['packet_size'], errors='coerce').fillna(0)

        outgoing_df = df[df['src_mac'].isin(self.macs)]
        incoming_df = df[df['dst_mac'].isin(self.macs)]

        duration_seconds = (end_time - start_time).total_seconds()

        stats = {
            'domain':           domain,
            'start_time':       start_time_str,
            'end_time':         end_time_str,
            'duration_seconds': duration_seconds,
            'outgoing_bytes':   int(outgoing_df['packet_size'].sum()),
            'outgoing_packets': len(outgoing_df),
            'outgoing_avg_bps': outgoing_df['packet_size'].sum() / duration_seconds if duration_seconds > 0 else 0,
            'incoming_bytes':   int(incoming_df['packet_size'].sum()),
            'incoming_packets': len(incoming_df),
            'incoming_avg_bps': incoming_df['packet_size'].sum() / duration_seconds if duration_seconds > 0 else 0,
            'total_bytes':      int(df['packet_size'].sum()),
            'total_packets':    len(df),
        }

        # Pretty-print to console
        print(f"\n{'='*55}")
        print(f"  Traffic Volume Report — {domain}")
        print(f"{'='*55}")
        print(f"  MACs        : {', '.join(self.macs)}")
        print(f"  Period      : {start_time_str}  →  {end_time_str}")
        print(f"  Duration    : {duration_seconds:.1f} seconds")
        print(f"{'-'*55}")
        print(f"  OUTGOING")
        print(f"    Bytes     : {stats['outgoing_bytes']:>15,} bytes")
        print(f"    Packets   : {stats['outgoing_packets']:>15,}")
        print(f"    Avg rate  : {stats['outgoing_avg_bps']:>15.2f} bytes/sec")
        print(f"{'-'*55}")
        print(f"  INCOMING")
        print(f"    Bytes     : {stats['incoming_bytes']:>15,} bytes")
        print(f"    Packets   : {stats['incoming_packets']:>15,}")
        print(f"    Avg rate  : {stats['incoming_avg_bps']:>15.2f} bytes/sec")
        print(f"{'-'*55}")
        print(f"  TOTAL")
        print(f"    Bytes     : {stats['total_bytes']:>15,} bytes")
        print(f"    Packets   : {stats['total_packets']:>15,}")
        print(f"{'='*55}\n")

        # Save to log file
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        safe_domain = domain.replace("/", "_").replace(" ", "_")
        log_filename = f"{safe_domain}_{start_time_str.replace(':', '-')}_{end_time_str.replace(':', '-')}.log"
        log_path = log_dir / log_filename

        with open(log_path, "w") as f:
            f.write(f"# Traffic Volume Report\n")
            f.write(f"# Domain       : {domain}\n")
            f.write(f"# MACs         : {', '.join(self.macs)}\n")
            f.write(f"# Start        : {start_time_str}\n")
            f.write(f"# End          : {end_time_str}\n")
            f.write(f"# Duration (s) : {duration_seconds:.1f}\n")
            f.write("#\n")
            f.write("metric,value\n")
            f.write(f"outgoing_bytes,{stats['outgoing_bytes']}\n")
            f.write(f"outgoing_packets,{stats['outgoing_packets']}\n")
            f.write(f"outgoing_avg_bps,{stats['outgoing_avg_bps']:.4f}\n")
            f.write(f"incoming_bytes,{stats['incoming_bytes']}\n")
            f.write(f"incoming_packets,{stats['incoming_packets']}\n")
            f.write(f"incoming_avg_bps,{stats['incoming_avg_bps']:.4f}\n")
            f.write(f"total_bytes,{stats['total_bytes']}\n")
            f.write(f"total_packets,{stats['total_packets']}\n")

        print(f"✅ Volume log saved: {log_path}")

        return stats

    def analyze_milliseconds(self, domain, start_time_str, end_time_str, figure_name):
        df = pd.read_csv(self.csv_file)
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = ['est_time', 'packet_size', 'src_ip', 'dst_ip', 'ans_type', 'src_mac', 'dst_mac']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")
            
        # Filter for any of the device MACs
        df = df[(df['src_mac'].isin(self.macs)) | (df['dst_mac'].isin(self.macs))]
        if df.empty:
            print(f"NO PACKETS FOUND INVOLVING ANY OF THESE MACS: {self.macs}")
            return
        
        df['est_time'] = pd.to_datetime(df['est_time'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
        df = df.dropna(subset=['est_time'])
        start_time = pd.to_datetime(start_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')
        start_time  = start_time + timedelta(minutes=5)
        end_time = pd.to_datetime(end_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')

        df = df[(df['est_time'] >= start_time) & (df['est_time'] <= end_time)]
        if df.empty:
            print(f"NO PACKETS FOUND BETWEEN {start_time} and {end_time}")
            return
        
        df['ans_type'] = df['ans_type'].astype(str).str.strip()
        df.loc[df['ans_type'].isin(['', 'None', 'nan']), 'ans_type'] = None
        df['packet_size'] = pd.to_numeric(df['packet_size'], errors='coerce').fillna(0)

        df['millisecond'] = df['est_time'].dt.floor('ms')

        outgoing_df = df[df['src_mac'].isin(self.macs)]
        traffic_per_ms = outgoing_df.groupby('millisecond')['packet_size'].sum().reset_index()
        traffic_per_ms = traffic_per_ms.sort_values(by='millisecond').reset_index(drop=True)
        ans_ms = df[df['ans_type'].notna()]['millisecond'].unique()

        plt.figure(figsize=(14,6))
        ax = plt.gca()

        ax.plot(
            traffic_per_ms['millisecond'],
            traffic_per_ms['packet_size'],
            marker='',
            linestyle='-',
            color='blue',
            linewidth=1,
            label='Outgoing Traffic (bytes/ms)'
        )

        for m in ans_ms:
            nearest_idx = (abs((traffic_per_ms['millisecond'] - m).dt.total_seconds())).idxmin()
            m_display = traffic_per_ms.loc[nearest_idx, 'millisecond']
            y_val = traffic_per_ms.loc[nearest_idx, 'packet_size']

            ax.scatter(
                m_display,
                y_val,
                marker='s',
                color='red',
                s=50,
                label='DNS Answer' if 'DNS Answer' not in ax.get_legend_handles_labels()[1] else ""
            )

        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
        plt.xticks(rotation=90)
        plt.xlabel("Time (HH:MM:SS)", fontsize=14)
        plt.ylabel("Bytes Sent per Millisecond", fontsize=24)
        plt.title(f"Traffic Spikes for {domain}", fontsize=26)

        handles, labels = ax.get_legend_handles_labels()
        num_entries = len(handles)

        import math
        ncol = math.ceil(num_entries / 3)
        ncol = max(1, ncol)
        plt.legend(fontsize=12, loc='best', ncol=ncol)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=12)
        
        figure_name = figure_name + ".pdf"
        figure_path = Path(figure_name)
        figure_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figure_name)
        plt.close()


class TrafficCDFAnalyzerWithLog:
    def __init__(self, csv_file, tv_mac='04:e4:b6:74:dd:94'):
        """
        Initialize with single MAC or comma-separated MAC string.
        
        Args:
            csv_file: Path to CSV file
            tv_mac: Single MAC address (str) or comma-separated MAC string
        """
        self.csv_file = csv_file
        # Parse and store as list
        self.macs = _parse_mac_addresses(tv_mac)
        
        self.df = pd.read_csv(csv_file)
        self.df.columns = [c.strip().lower() for c in self.df.columns]
        self._preprocess_time()
        self.bytes_per_interval = None

    def _preprocess_time(self):
        self.df['est_time'] = pd.to_datetime(
            self.df['est_time'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce'
        )
        self.df = self.df.dropna(subset=['est_time'])

    def filter_time(self, start_time_str, end_time_str):
        start = pd.to_datetime(start_time_str, format='%Y-%m-%d %H:%M:%S')
        end = pd.to_datetime(end_time_str, format='%Y-%m-%d %H:%M:%S')
        self.df = self.df[
            (self.df['est_time'] >= start) &
            (self.df['est_time'] <= end)
        ]
    
    def filter_outgoing(self):
        if not self.macs:
            raise ValueError("MACs must be provided")
        self.df = self.df[self.df['src_mac'].isin(self.macs)]

    def filter_incoming(self):
        if not self.macs:
            raise ValueError("MACs must be provided")
        self.df = self.df[self.df['dst_mac'].isin(self.macs)]

    def compute_cumulative_bytes(self, interval='1T'):
        self.df['time_bin'] = self.df['est_time'].dt.floor(interval)

        grouped = (
            self.df.groupby('time_bin')['packet_size'].sum()
        )
        if grouped.empty:
            print("WARNING: NO DATA AVAILABLE FOR CUMULATIVE BYTE COMPUTATION")
            self.bytes_per_interval = None
            return None
        full_index = pd.date_range(
            start=grouped.index.min(),
            end=grouped.index.max(),
            freq=interval
        )
        bytes_per_interval = (
            grouped.reindex(full_index, fill_value=0).rename_axis('time_bin').reset_index()
        )
        bytes_per_interval['cumulative_bytes'] = (
            bytes_per_interval['packet_size'].cumsum()
        )

        self.bytes_per_interval = bytes_per_interval
        self.interval = interval

    def plot_cdf(self, file_name, plot_name, time_prd="Time", title="CDF of Outgoing Packets", log_dir=None):
        if log_dir is None:
            log_dir = DATA_VOLUME_LOGS_DIR
        
        if not hasattr(self, 'bytes_per_interval'):
            self.compute_cumulative_bytes()
        if self.bytes_per_interval is None or self.bytes_per_interval.empty:
            print("Warning: No data to plot CDF.")
            return
        
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(10,5))
        plt.plot(
            self.bytes_per_interval['time_bin'],
            self.bytes_per_interval['cumulative_bytes'],
            linewidth=2
        )

        plt.xlabel(time_prd, fontsize=20)
        plt.ylabel('Cumulative outgoing bytes', fontsize=20)
        plt.title(f"{title}", fontsize=20)
        plt.grid(True)

        from matplotlib.dates import MinuteLocator, DateFormatter
        ax = plt.gca()
        ax.xaxis.set_major_locator(MinuteLocator(interval=1))
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        ax.tick_params(axis='x', rotation=90)

        plt.tight_layout()

        plot_name_pdf = plot_name + ".pdf"
        plot_path = Path(plot_name_pdf)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(plot_name_pdf)
        plt.close()

        # Save log
        file_name_log = file_name + ".log"
        log_file = log_dir / file_name_log
        with open(log_file, "w") as f:
            f.write(f"# Title: {title}\n")
            f.write(f"# XLabel: {time_prd}\n")
            f.write(f"# YLabel: Cumulative outgoing bytes\n")
            f.write(f'# Interval: {self.interval}\n')
            f.write(f"# Total Points: {len(self.bytes_per_interval)}\n")
            f.write("# Data:\n")

        self.bytes_per_interval[['time_bin', 'cumulative_bytes']].to_csv(
            log_file, mode='a', index=False
        )

        print(f"✅ Log file saved: {log_file}")

    def plot_cdf_incoming(self, file_name, plot_name, time_prd="Time", title="CDF of Incoming Packets", log_dir=None):
        if log_dir is None:
            log_dir = DATA_VOLUME_LOGS_DIR
        
        if not hasattr(self, 'bytes_per_interval'):
            self.compute_cumulative_bytes()
        if self.bytes_per_interval is None or self.bytes_per_interval.empty:
            print("Warning: No data to plot CDF.")
            return
        
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(10,5))
        plt.plot(
            self.bytes_per_interval['time_bin'],
            self.bytes_per_interval['cumulative_bytes'],
            linewidth=2
        )

        plt.xlabel(time_prd, fontsize=20)
        plt.ylabel('Cumulative incoming bytes', fontsize=20)
        plt.title(f"{title}", fontsize=20)
        plt.grid(True)

        from matplotlib.dates import MinuteLocator, DateFormatter
        ax = plt.gca()
        ax.xaxis.set_major_locator(MinuteLocator(interval=1))
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        ax.tick_params(axis='x', rotation=90)

        plt.tight_layout()

        plot_name_pdf = plot_name + ".pdf"
        plot_path = Path(plot_name_pdf)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(plot_name_pdf)
        plt.close()

        # Save log
        file_name_log = file_name + ".log"
        log_file = log_dir / file_name_log
        with open(log_file, "w") as f:
            f.write(f"# Title: {title}\n")
            f.write(f"# XLabel: {time_prd}\n")
            f.write(f"# YLabel: Cumulative incoming bytes\n")
            f.write(f'# Interval: {self.interval}\n')
            f.write(f"# Total Points: {len(self.bytes_per_interval)}\n")
            f.write("# Data:\n")

        self.bytes_per_interval[['time_bin', 'cumulative_bytes']].to_csv(
            log_file, mode='a', index=False
        )

        print(f"✅ Log file saved: {log_file}")


if __name__ == "__main__":
    # Arguments from manager script
    folder_for_domains = sys.argv[1]  # Directory containing domain CSVs
    start_time = sys.argv[2]
    end_time = sys.argv[3]
    title = sys.argv[4]
    domain_name = sys.argv[5]
    device_name = sys.argv[6] if len(sys.argv) > 6 else "unknown"
    mac = sys.argv[7] if len(sys.argv) > 7 else "04:e4:b6:74:dd:94"
    # mac can be: "single_mac" or "mac1,mac2,mac3" (comma-separated)
    
    all_acr_csv = Path(folder_for_domains) / f"{domain_name}.csv"
    
    if not all_acr_csv.exists():
        print(f"ERROR: Domain CSV not found: {all_acr_csv}")
        sys.exit(1)
    
    # Create output paths
    sub_path = DATA_ANALYSIS_FIGURES_DIR / device_name
    figure_dir = sub_path / "time_series"
    cdf_dir = sub_path / "cdfs"
    cdf_log_dir = sub_path / "cdf_logs"
    
    title1 = f"{domain_name} {title} {start_time} {end_time}"
    figure_name = figure_dir / title1
    
    # Analyze milliseconds
    print(f"\n[1/2] Analyzing milliseconds...")
    analyzer = TrafficVisualization(str(all_acr_csv), mac)
    analyzer.analyze_milliseconds(title1, start_time, end_time, str(figure_name))
    
    # Analyze CDF
    print(f"[2/2] Analyzing CDF...")
    analyzer_cdf = TrafficCDFAnalyzerWithLog(str(all_acr_csv), tv_mac=mac)
    analyzer_cdf.filter_time(start_time, end_time)
    analyzer_cdf.filter_outgoing()
    analyzer_cdf.compute_cumulative_bytes(interval='10s')
    
    plot_name = cdf_dir / title1
    analyzer_cdf.plot_cdf(
        title1,
        str(plot_name),
        time_prd=title1,
        title="CDF of Outgoing Packets",
        log_dir=str(cdf_log_dir)
    )
    
    print(f"\n✓ Analysis complete for {domain_name}")