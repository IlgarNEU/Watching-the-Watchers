import pandas as pd
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import argparse


# Define paths relative to script location
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_FOLDER = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_FOLDER.parent
DATA_ANALYSIS_FIGURES_DIR = PROJECT_ROOT / "data" / "analysis_figures"
DATA_VOLUME_LOGS_DIR = PROJECT_ROOT / "data" / "volume_logs"

# TV name to MAC addresses mapping
TV_MAC_MAPPING = {
    "tizen": "04:e4:b6:74:dd:94",
    "webos": "00:a1:59:8f:ab:38",
    "roku_roku": "34:5e:08:b1:b3:be",
    "roku_tcl": "c4:8b:66:60:86:02",
    "google": ["58:18:62:30:2f:eb", "4e:cb:9c:2d:bb:89"],
    "fire": ["28:73:f6:20:a6:35", "28:73:f6:20:b6:95"],
    "smartcast": "14:c6:7d:15:31:56",
    "xumo": "b8:41:d9:e4:f8:ed",
    "google_tcl": "48:87:b8:ab:34:37",
    
    # Example: Device with multiple MACs
    # "samsung": ["04:e4:b6:74:dd:94", "a8:5e:60:12:34:56"],
}


class TrafficVisualization:
    def __init__(self, csv_file, mac):
        self.csv_file = csv_file
        self.mac = [mac] if isinstance(mac, str) else mac

    def analyze_traffic_volume(self, domain, start_time_str, end_time_str, log_dir=None):
        if log_dir is None:
            log_dir = DATA_VOLUME_LOGS_DIR
        
        df = pd.read_csv(self.csv_file)
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = ['est_time', 'packet_size', 'src_ip', 'dst_ip', 'ans_type', 'src_mac', 'dst_mac']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")

        # Filter by MAC
        df = df[df['src_mac'].isin(self.mac) | df['dst_mac'].isin(self.mac)]
        if df.empty:
            print("NO PACKETS FOUND")
            return None

        df['est_time'] = pd.to_datetime(df['est_time'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
        df = df.dropna(subset=['est_time'])
        start_time = pd.to_datetime(start_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')
        end_time = pd.to_datetime(end_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')

        df = df[(df['est_time'] >= start_time) & (df['est_time'] <= end_time)]
        if df.empty:
            print(f"NO PACKETS FOUND BETWEEN {start_time} and {end_time}")
            return None

        df['packet_size'] = pd.to_numeric(df['packet_size'], errors='coerce').fillna(0)

        outgoing_df = df[df['src_mac'].isin(self.mac)]
        incoming_df = df[df['dst_mac'].isin(self.mac)]

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

        print(f"\n{'='*55}")
        print(f"  Traffic Volume Report — {domain}")
        print(f"{'='*55}")
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

        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        safe_domain = domain.replace("/", "_").replace(" ", "_")
        log_filename = f"{safe_domain}_{start_time_str.replace(':', '-')}_{end_time_str.replace(':', '-')}.log"
        log_path = log_dir / log_filename

        with open(log_path, "w") as f:
            f.write(f"# Traffic Volume Report\n")
            f.write(f"# Domain       : {domain}\n")
            f.write(f"# Start        : {start_time_str}\n")
            f.write(f"# End          : {end_time_str}\n")
            f.write(f"# Duration (s) : {duration_seconds:.1f}\n")
            f.write(f"# MAC          : {self.mac}\n")
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

        # Filter by MAC
        df = df[df['src_mac'].isin(self.mac) | df['dst_mac'].isin(self.mac)]
        if df.empty:
            print("NO PACKETS FOUND")
            return
        
        df['est_time'] = pd.to_datetime(df['est_time'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
        df = df.dropna(subset=['est_time'])
        start_time = pd.to_datetime(start_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')
        end_time = pd.to_datetime(end_time_str, format="%Y-%m-%d %H:%M:%S", errors='coerce')

        df = df[(df['est_time'] >= start_time) & (df['est_time'] <= end_time)]
        if df.empty:
            print(f"NO PACKETS FOUND BETWEEN {start_time} and {end_time}")
            return
        
        df['ans_type'] = df['ans_type'].astype(str).str.strip()
        df.loc[df['ans_type'].isin(['', 'None', 'nan']), 'ans_type'] = None
        df['packet_size'] = pd.to_numeric(df['packet_size'], errors='coerce').fillna(0)
        df['millisecond'] = df['est_time'].dt.floor('ms')

        outgoing_df = df[df['src_mac'].isin(self.mac)]
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
        
        figure_name = str(figure_name) + ".pdf"
        figure_path = Path(figure_name)
        figure_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figure_name)
        plt.close()


class TrafficCDFAnalyzerWithLog:
    def __init__(self, csv_file, tv_mac):
        self.csv_file = csv_file
        self.tv_mac = [tv_mac] if isinstance(tv_mac, str) else tv_mac
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
        if not self.tv_mac:
            raise ValueError("tv_mac must be provided")
        tv_macs = self.tv_mac if isinstance(self.tv_mac, list) else [self.tv_mac]
        self.df = self.df[self.df['src_mac'].isin(tv_macs)]

    def filter_incoming(self):
        if not self.tv_mac:
            raise ValueError("tv_mac must be provided")
        tv_macs = self.tv_mac if isinstance(self.tv_mac, list) else [self.tv_mac]
        self.df = self.df[self.df['dst_mac'].isin(tv_macs)]

    def compute_cumulative_bytes(self, interval='1T'):
        self.df['time_bin'] = self.df['est_time'].dt.floor(interval)
        grouped = self.df.groupby('time_bin')['packet_size'].sum()
        
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

        plot_name_pdf = str(plot_name) + ".pdf"
        plot_path = Path(plot_name_pdf)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(plot_name_pdf)
        plt.close()

        file_name_log = str(file_name) + ".log"
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

        plot_name_pdf = str(plot_name) + ".pdf"
        plot_path = Path(plot_name_pdf)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(plot_name_pdf)
        plt.close()

        file_name_log = str(file_name) + ".log"
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
    parser = argparse.ArgumentParser(description="Analyze traffic and generate visualizations")
    
    parser.add_argument("folder_for_domains", help="Directory containing domain CSVs")
    parser.add_argument("start_time", help="Start time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("end_time", help="End time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("title", help="Analysis title")
    parser.add_argument("domain_name", help="Domain/IP name")
    parser.add_argument("--device", default="sony", help="Device name (default: sony)")
    
    args = parser.parse_args()
    
    device_name = args.device
    mac = TV_MAC_MAPPING.get(device_name, ["04:e4:b6:74:dd:94"])
    
    folder_for_domains = Path(args.folder_for_domains)
    all_acr_csv = folder_for_domains / f"{args.domain_name}.csv"
    
    if not all_acr_csv.exists():
        print(f"Error: CSV not found: {all_acr_csv}")
        sys.exit(1)
    
    sub_path = DATA_ANALYSIS_FIGURES_DIR / device_name
    figure_dir = sub_path / "time_series"
    cdf_dir = sub_path / "cdfs"
    cdf_log_dir = sub_path / "cdf_logs"
    
    title1 = f"{args.domain_name} {args.title} {args.start_time} {args.end_time}"
    figure_name = figure_dir / title1
    
    print(f"\n{'='*60}")
    print(f"Device: {device_name}")
    print(f"MAC(s): {mac}")
    print(f"Domain: {args.domain_name}")
    print(f"Time: {args.start_time} → {args.end_time}")
    print(f"{'='*60}\n")
    
    # Analyze milliseconds
    analyzer = TrafficVisualization(str(all_acr_csv), mac)
    analyzer.analyze_milliseconds(title1, args.start_time, args.end_time, str(figure_name))
    analyzer.analyze_traffic_volume(args.domain_name, args.start_time, args.end_time)
    
    # Analyze CDF
    analyzer_cdf = TrafficCDFAnalyzerWithLog(str(all_acr_csv), tv_mac=mac)
    analyzer_cdf.filter_time(args.start_time, args.end_time)
    analyzer_cdf.filter_outgoing()
    analyzer_cdf.compute_cumulative_bytes(interval='1ms')
    
    plot_name = cdf_dir / title1
    analyzer_cdf.plot_cdf(
        title1,
        str(plot_name),
        time_prd=title1,
        title="CDF of Outgoing Packets",
        log_dir=str(cdf_log_dir)
    )
    
    print(f"\n✓ Analysis complete for {args.domain_name}")