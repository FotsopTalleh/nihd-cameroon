"""
CSV report generator using Python csv module + pandas.
"""
import os
import csv
from datetime import datetime, timedelta
from config import Config


def generate_csv(region: str = '', hours: int = 24):
    """Generate a CSV file of measurements and return (file_path, file_name)."""
    try:
        from models import Measurement
        since = datetime.utcnow() - timedelta(hours=hours)
        q = Measurement.query.filter(Measurement.timestamp >= since)
        if region:
            q = q.filter(Measurement.region == region)
        measurements = q.order_by(Measurement.timestamp.asc()).all()

        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_region = region.replace(' ', '_').replace('/', '-') if region else 'AllRegions'
        file_name = f'NIHD_Data_{safe_region}_{ts}.csv'
        file_path = os.path.join(Config.DOWNLOAD_FOLDER, file_name)

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Metadata header
            writer.writerow(['# National Internet Health Dashboard – CSV Export'])
            writer.writerow([f'# Region: {region if region else "All Regions"}'])
            writer.writerow([f'# Period: Last {hours} Hours'])
            writer.writerow([f'# Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}'])
            writer.writerow([f'# Total Records: {len(measurements)}'])
            writer.writerow([])

            # Column headers
            writer.writerow([
                'ID', 'Timestamp (UTC)', 'Region', 'ISP',
                'Latency (ms)', 'Packet Loss (%)', 'Uptime (%)',
                'Download Speed (Mbps)', 'Upload Speed (Mbps)', 'Jitter (ms)'
            ])

            # Data rows
            for m in measurements:
                writer.writerow([
                    m.id,
                    m.timestamp.strftime('%Y-%m-%d %H:%M:%S') if m.timestamp else '',
                    m.region,
                    m.isp or '',
                    f'{m.latency:.2f}',
                    f'{m.packet_loss:.2f}',
                    f'{m.uptime:.2f}',
                    f'{m.download_speed:.2f}' if m.download_speed else '',
                    f'{m.upload_speed:.2f}' if m.upload_speed else '',
                    f'{m.jitter:.2f}' if m.jitter else '',
                ])

        return file_path, file_name

    except Exception as e:
        print(f'CSV generation error: {e}')
        return None, None
