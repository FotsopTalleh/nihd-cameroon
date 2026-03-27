"""
Seed the database with realistic sample data for Cameroon internet measurements.
Only runs if the database is empty.
"""
import json
import random
from datetime import datetime, timedelta


REGIONS = [
    'Yaoundé (Centre)', 'Douala (Littoral)', 'Bafoussam (West)',
    'Garoua (North)', 'Maroua (Far North)', 'Ngaoundéré (Adamawa)',
    'Bertoua (East)', 'Bamenda (Northwest)', 'Buea (Southwest)', 'Ebolowa (South)'
]

ISPS = ['Camtel', 'MTN Cameroon', 'Orange Cameroon', 'Nexttel']

# Realistic base latency per region (ms) - northern regions typically slower
REGION_PROFILES = {
    'Yaoundé (Centre)':     {'latency': 40,  'uptime': 99.2, 'loss': 0.5},
    'Douala (Littoral)':    {'latency': 35,  'uptime': 99.5, 'loss': 0.3},
    'Bafoussam (West)':     {'latency': 55,  'uptime': 98.8, 'loss': 0.8},
    'Garoua (North)':       {'latency': 95,  'uptime': 96.5, 'loss': 2.1},
    'Maroua (Far North)':   {'latency': 130, 'uptime': 93.2, 'loss': 4.5},
    'Ngaoundéré (Adamawa)': {'latency': 110, 'uptime': 95.1, 'loss': 3.0},
    'Bertoua (East)':       {'latency': 85,  'uptime': 97.2, 'loss': 1.5},
    'Bamenda (Northwest)':  {'latency': 65,  'uptime': 97.8, 'loss': 1.2},
    'Buea (Southwest)':     {'latency': 70,  'uptime': 97.5, 'loss': 1.0},
    'Ebolowa (South)':      {'latency': 80,  'uptime': 96.9, 'loss': 1.8},
}

ISP_MULTIPLIERS = {
    'Camtel':         {'latency': 1.3, 'uptime': 0.98, 'loss': 1.5},
    'MTN Cameroon':   {'latency': 0.9, 'uptime': 1.01, 'loss': 0.8},
    'Orange Cameroon':{'latency': 1.0, 'uptime': 1.00, 'loss': 1.0},
    'Nexttel':        {'latency': 1.1, 'uptime': 0.99, 'loss': 1.2},
}

ALERT_TYPES = [
    ('High Latency Detected', 'warning', 'Latency exceeded threshold of 150ms'),
    ('Packet Loss Spike', 'critical', 'Packet loss exceeded 5% — service interruption likely'),
    ('Uptime Drop', 'critical', 'Uptime fell below 90% — possible outage detected'),
    ('Jitter Anomaly', 'warning', 'High jitter detected — voice/video services affected'),
    ('ISP Route Change', 'info', 'BGP route change detected from upstream provider'),
    ('DNS Resolution Failure', 'warning', 'Increased DNS failure rate detected'),
    ('Physical Link Degradation', 'critical', 'Physical layer error rate increasing'),
    ('Congestion Detected', 'info', 'Network congestion detected during peak hours'),
]

TRACEROUTE_HOPS_TEMPLATE = [
    {'hop': 1, 'ip': '192.168.1.1', 'hostname': 'gateway.local', 'as_number': None, 'location': 'Local', 'latency': 1.2, 'status': 'OK'},
    {'hop': 2, 'ip': '10.0.0.1', 'hostname': 'isp-edge.cm', 'as_number': 'AS37188', 'location': 'Yaoundé', 'latency': 8.5, 'status': 'OK'},
    {'hop': 3, 'ip': '196.216.2.1', 'hostname': 'afrixp-peer.net', 'as_number': 'AS37153', 'location': 'Nairobi, KE', 'latency': 42.3, 'status': 'OK'},
    {'hop': 4, 'ip': '196.11.240.1', 'hostname': 'jinx-peering.co.za', 'as_number': 'AS16637', 'location': 'Johannesburg, ZA', 'latency': 98.7, 'status': 'OK'},
    {'hop': 5, 'ip': '195.22.216.1', 'hostname': 'seacom-backbone.net', 'as_number': 'AS37100', 'location': 'London, UK', 'latency': 175.2, 'status': 'OK'},
    {'hop': 6, 'ip': '8.8.8.8', 'hostname': 'dns.google', 'as_number': 'AS15169', 'location': 'Mountain View, US', 'latency': 210.5, 'status': 'OK'},
]


def seed_database():
    from extensions import db
    from models import Measurement, Alert, Traceroute

    if Measurement.query.first():
        return  # Already seeded

    print('Seeding database with sample data...')
    now = datetime.utcnow()

    # Generate 30 days of hourly measurements
    batch = []
    for days_back in range(30, 0, -1):
        for hour in range(0, 24, 2):  # every 2 hours
            ts = now - timedelta(days=days_back, hours=hour)
            for region in REGIONS:
                for isp in random.sample(ISPS, k=2):  # 2 random ISPs per region/time
                    profile = REGION_PROFILES[region]
                    mult = ISP_MULTIPLIERS[isp]

                    # Add time-of-day variation (peak 8am-10pm)
                    hour_of_day = ts.hour
                    peak_factor = 1.3 if 8 <= hour_of_day <= 22 else 0.9

                    base_lat = profile['latency'] * mult['latency'] * peak_factor
                    noise = random.gauss(0, base_lat * 0.15)
                    latency = max(5.0, base_lat + noise)

                    base_up = profile['uptime'] * mult['uptime']
                    uptime = min(100.0, max(70.0, base_up + random.gauss(0, 0.5)))

                    base_loss = profile['loss'] * mult['loss']
                    packet_loss = max(0.0, min(20.0, base_loss + random.gauss(0, 0.3)))

                    dl_speed = random.uniform(2, 50) if isp != 'Camtel' else random.uniform(0.5, 10)
                    ul_speed = dl_speed * random.uniform(0.2, 0.5)
                    jitter = random.uniform(1, latency * 0.3)

                    batch.append(Measurement(
                        region=region,
                        isp=isp,
                        latency=round(latency, 2),
                        packet_loss=round(packet_loss, 2),
                        uptime=round(uptime, 2),
                        download_speed=round(dl_speed, 2),
                        upload_speed=round(ul_speed, 2),
                        jitter=round(jitter, 2),
                        timestamp=ts,
                    ))

    db.session.bulk_save_objects(batch)

    # Generate alerts
    alert_batch = []
    for i in range(30):
        alert_type, severity, msg = random.choice(ALERT_TYPES)
        region = random.choice(REGIONS)
        ts = now - timedelta(hours=random.randint(1, 720))
        # Seed all alerts as resolved — only live probe creates active alerts
        alert_batch.append(Alert(
            type=alert_type,
            severity=severity,
            region=region,
            message=msg,
            is_resolved=True,
            resolved_at=ts + timedelta(hours=random.randint(1, 6)),
            timestamp=ts,
        ))
    db.session.bulk_save_objects(alert_batch)

    # Generate traceroutes
    sources = ['Yaoundé (Centre)', 'Douala (Littoral)', 'Bafoussam (West)']
    destinations = ['8.8.8.8 (Google DNS)', '1.1.1.1 (Cloudflare)', '196.216.2.1 (RINX)', 'www.google.cm']
    trace_batch = []
    for _ in range(30):
        src = random.choice(sources)
        dst = random.choice(destinations)
        ts = now - timedelta(hours=random.randint(1, 120))
        hops = []
        for h in TRACEROUTE_HOPS_TEMPLATE:
            hop = h.copy()
            hop['latency'] = round(h['latency'] + random.gauss(0, h['latency'] * 0.1), 1)
            hops.append(hop)
        trace_batch.append(Traceroute(
            source=src,
            destination=dst,
            hops=json.dumps(hops),
            total_hops=len(hops),
            total_latency=round(hops[-1]['latency'], 1),
            timestamp=ts,
        ))
    db.session.bulk_save_objects(trace_batch)

    db.session.commit()
    print(f'Seeded {len(batch)} measurements, {len(alert_batch)} alerts, {len(trace_batch)} traceroutes.')
