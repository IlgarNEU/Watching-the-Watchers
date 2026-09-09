import csv
import subprocess
import sys
import pandas as pd
from io import StringIO
from datetime import datetime


class TraceExtractor:
    def __init__(self, pcap_file, output_csv, exclude_mdns=False):
        self.pcap_file = pcap_file
        self.output_csv = output_csv
        self.exclude_mdns = exclude_mdns

        self.tshark_fields = [
            'frame.time',
            'frame.time_epoch',
            'frame.len',
            'eth.src',
            'eth.dst',
            'ip.src',
            'ip.dst',
            'udp.srcport',
            'tcp.srcport',
            'udp.dstport',
            'tcp.dstport',
            'dns.flags.response',
            'dns.id',
            'dns.flags.rcode',
            'dns.qry.name',
            'dns.qry.type',
            'dns.resp.name',
            'dns.resp.type',
            'dns.resp.ttl',
            'dns.a',
            'dns.aaaa',
            'tls.handshake.extensions_server_name',
        ]

        self.output_fieldnames = [
            'timestamp', 'est_time', 'frame_time_epoch', 'packet_size',
            'src_mac', 'dst_mac', 'src_ip', 'dst_ip',
            'src_port', 'dst_port', 'is_response', 'transaction_id',
            'rcode', 'qry_name', 'qry_type', 'ans_name',
            'ans_type', 'ans_ttl', 'ans_data', 'sni'
        ]

    def extract(self):
        print(f"Reading pcap: {self.pcap_file}")

        cmd = ['tshark', '-r', self.pcap_file, '-T', 'fields']
        for f in self.tshark_fields:
            cmd += ['-e', f]
        cmd += [
            '-E', 'header=y',
            '-E', 'separator=|',
            '-E', 'occurrence=f',
            '-E', 'quote=n',
        ]

        if self.exclude_mdns:
            cmd += ['-Y', '!(udp.port == 5353)']

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"tshark warning (truncated file, processing partial data): {result.stderr.strip()}")

        if not result.stdout.strip():
            print("No output from tshark — is the pcap file valid?")
            sys.exit(1)

        df = pd.read_csv(StringIO(result.stdout), sep='|', dtype=str, low_memory=False)
        df.columns = [
            'timestamp', 'frame_time_epoch', 'packet_size',
            'src_mac', 'dst_mac', 'src_ip', 'dst_ip',
            'src_port_udp', 'src_port_tcp', 'dst_port_udp', 'dst_port_tcp',
            'is_response', 'transaction_id', 'rcode',
            'qry_name', 'qry_type', 'ans_name', 'ans_type_raw', 'ans_ttl',
            'ans_data_a', 'ans_data_aaaa', 'sni_raw'
        ]

        df = self._enrich_dns_answers(df)

        df = self._postprocess(df)

        df[self.output_fieldnames].to_csv(self.output_csv, index=False)
        print(f"Extraction complete. {len(df)} packets written to {self.output_csv}")

    def _enrich_dns_answers(self, df):
        print("Running second pass for full DNS answer IPs...")
        cmd = [
            'tshark', '-r', self.pcap_file, '-T', 'fields',
            '-e', 'frame.time_epoch',
            '-e', 'dns.a',
            '-E', 'header=n',
            '-E', 'separator=|',
            '-E', 'occurrence=a',
            '-E', 'quote=n',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            print("Second pass failed or empty — using first-pass DNS data only")
            return df

        dns_all = pd.read_csv(
            StringIO(result.stdout), sep='|', dtype=str,
            header=None, names=['frame_time_epoch', 'dns_a_all']
        )

        dns_all = dns_all[dns_all['dns_a_all'].notna() & (dns_all['dns_a_all'] != '')]
        dns_all = dns_all.drop_duplicates(subset='frame_time_epoch', keep='last')

        df = df.merge(dns_all, on='frame_time_epoch', how='left')
        df['ans_data_a'] = df['dns_a_all'].combine_first(df['ans_data_a'])
        df = df.drop(columns=['dns_a_all'])

        return df

    def _postprocess(self, df):
        df['src_ip'] = df['src_ip'].str.split(',').str[0].str.strip()
        df['dst_ip'] = df['dst_ip'].str.split(',').str[0].str.strip()

        df['src_port'] = df['src_port_udp'].fillna(df['src_port_tcp'])
        df['dst_port'] = df['dst_port_udp'].fillna(df['dst_port_tcp'])

        type_map = {
            '1':  'A',
            '2':  'NS',
            '5':  'CNAME',
            '6':  'SOA',
            '12': 'PTR',
            '15': 'MX',
            '16': 'TXT',
            '28': 'AAAA',
            '33': 'SRV',
        }
        df['ans_type'] = df['ans_type_raw'].map(lambda x: type_map.get(str(x).strip(), x) if pd.notna(x) else '')

        df['ans_data'] = df['ans_data_a'].fillna(df['ans_data_aaaa']).fillna('')

        df['sni'] = df['sni_raw'].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ('', 'nan') else ''
        )

        def reformat_ts(epoch_str):
            try:
                epoch = float(epoch_str)
                return datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S.%f')
            except Exception:
                return ''

        df['est_time'] = df['frame_time_epoch'].apply(reformat_ts)

        def normalize_response(val):
            if pd.isna(val) or str(val).strip() == '':
                return ''
            return 1 if str(val).strip() in ('1', 'True', 'true') else 0

        df['is_response'] = df['is_response'].apply(normalize_response)

        df = df.fillna('')

        return df


if __name__ == "__main__":
    pcap_file    = sys.argv[1] if len(sys.argv) > 1 else 'input.pcap'
    output_csv   = sys.argv[2] if len(sys.argv) > 2 else 'traces.csv'
    exclude_mdns = '--exclude-mdns' in sys.argv

    extractor = TraceExtractor(pcap_file, output_csv, exclude_mdns=exclude_mdns)
    extractor.extract()