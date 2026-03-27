"""
probe_agent.py — Real-time probe using your local machine.

- Uses Windows `ping` (or cross-platform subprocess) to measure actual latency
  to well-known internet hosts (Google, Cloudflare, etc.)
- Maps each ping result to a Cameroon region using realistic multipliers
- Saves measurements to the DB and emits SocketIO events for live dashboard updates
- Runs via APScheduler every 30 seconds in the background
"""

import subprocess
import re
import random
import platform
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Real internet targets — we ping these to get true network measurements
PING_TARGETS = [
    {'host': '8.8.8.8',         'label': 'Google DNS'},
    {'host': '1.1.1.1',         'label': 'Cloudflare'},
    {'host': '208.67.222.222',  'label': 'OpenDNS'},
]

# Cameroon regions with realistic multipliers relative to base latency
# (simulating that different probe machines around Cameroon would see these differences)
REGION_PROFILES = {
    'Yaoundé (Centre)':     {'factor': 1.00, 'uptime_base': 99.2, 'loss_add': 0.0},
    'Douala (Littoral)':    {'factor': 0.90, 'uptime_base': 99.5, 'loss_add': -0.1},
    'Bafoussam (West)':     {'factor': 1.30, 'uptime_base': 98.8, 'loss_add': 0.3},
    'Garoua (North)':       {'factor': 2.10, 'uptime_base': 96.5, 'loss_add': 1.5},
    'Maroua (Far North)':   {'factor': 2.90, 'uptime_base': 93.2, 'loss_add': 3.5},
    'Ngaoundéré (Adamawa)': {'factor': 2.40, 'uptime_base': 95.1, 'loss_add': 2.0},
    'Bertoua (East)':       {'factor': 1.90, 'uptime_base': 97.2, 'loss_add': 1.0},
    'Bamenda (Northwest)':  {'factor': 1.50, 'uptime_base': 97.8, 'loss_add': 0.6},
    'Buea (Southwest)':     {'factor': 1.60, 'uptime_base': 97.5, 'loss_add': 0.5},
    'Ebolowa (South)':      {'factor': 1.80, 'uptime_base': 96.9, 'loss_add': 0.8},
}

ISP_MULTIPLIERS = {
    'Camtel':         {'lat': 1.30, 'loss': 1.50},
    'MTN Cameroon':   {'lat': 0.90, 'loss': 0.80},
    'Orange Cameroon':{'lat': 1.00, 'loss': 1.00},
    'Nexttel':        {'lat': 1.10, 'loss': 1.20},
}

ISPS = list(ISP_MULTIPLIERS.keys())


def ping_host(host: str, count: int = 4) -> tuple[float | None, float]:
    """
    Run a real system ping and return (avg_latency_ms, packet_loss_pct).
    Works on Windows (ping -n) and Linux/macOS (ping -c).
    """
    is_windows = platform.system().lower() == 'windows'
    cmd = ['ping', f'-{"n" if is_windows else "c"}', str(count), host]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20, encoding='utf-8', errors='replace'
        )
        output = result.stdout

        # --- Parse packet loss ---
        if is_windows:
            # "Packets: Sent = 4, Received = 3, Lost = 1 (25% loss)"
            loss_match = re.search(r'Lost\s*=\s*\d+\s*\((\d+)%\s*loss\)', output, re.IGNORECASE)
        else:
            # "4 packets transmitted, 3 received, 25% packet loss"
            loss_match = re.search(r'(\d+)% packet loss', output)
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0

        # --- Parse average latency ---
        if is_windows:
            # "Average = 45ms"
            avg_match = re.search(r'Average\s*=\s*(\d+)ms', output, re.IGNORECASE)
            avg_latency = float(avg_match.group(1)) if avg_match else None
        else:
            # "rtt min/avg/max/mdev = 10.1/45.2/90.0/5.1 ms"
            avg_match = re.search(r'[\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms', output)
            avg_latency = float(avg_match.group(1)) if avg_match else None

        return avg_latency, packet_loss

    except subprocess.TimeoutExpired:
        logger.warning(f'Ping timeout for {host}')
        return None, 100.0
    except Exception as e:
        logger.error(f'Ping error for {host}: {e}')
        return None, 100.0


def get_base_measurement() -> tuple[float, float]:
    """
    Ping multiple real hosts and return (avg_latency, avg_loss) as the
    base measurement for this probe cycle.
    """
    results = []
    for target in PING_TARGETS:
        lat, loss = ping_host(target['host'], count=3)
        if lat is not None:
            results.append((lat, loss))
            logger.info(f"Probe → {target['host']} ({target['label']}): {lat:.1f}ms, {loss:.0f}% loss")

    if not results:
        logger.warning('All ping targets failed — using fallback values')
        return 80.0, 5.0  # fallback if network is unreachable

    avg_lat  = sum(r[0] for r in results) / len(results)
    avg_loss = sum(r[1] for r in results) / len(results)
    return round(avg_lat, 2), round(avg_loss, 2)


def run_probe_cycle(app, socketio):
    """
    Main probe function called by APScheduler every 30 seconds.
    1. Gets real base measurement from this machine
    2. Derives per-region measurements using realistic multipliers
    3. Saves to DB
    4. Emits SocketIO events for live dashboard updates
    """
    with app.app_context():
        from extensions import db
        from models import Measurement, Alert
        from utils.alert_checker import check_and_raise_alerts as _check_and_raise_alerts

        base_latency, base_loss = get_base_measurement()
        now = datetime.utcnow()
        saved_measurements = []

        for region, profile in REGION_PROFILES.items():
            isp = random.choice(ISPS)
            isp_mult = ISP_MULTIPLIERS[isp]

            noise = random.gauss(0, base_latency * 0.08)
            latency = max(5.0, base_latency * profile['factor'] * isp_mult['lat'] + noise)

            loss_noise = random.gauss(0, 0.2)
            packet_loss = max(0.0, min(20.0,
                (base_loss * isp_mult['loss'] + profile['loss_add'] + loss_noise)
            ))
            uptime = max(70.0, min(100.0, profile['uptime_base'] + random.gauss(0, 0.3)))

            dl_speed = random.uniform(1, 50) * (1 / isp_mult['lat'])
            ul_speed = dl_speed * random.uniform(0.2, 0.4)
            jitter    = max(0.5, latency * 0.15 + random.gauss(0, 2))

            m = Measurement(
                region=region,
                isp=isp,
                latency=round(latency, 2),
                packet_loss=round(packet_loss, 2),
                uptime=round(uptime, 2),
                download_speed=round(dl_speed, 2),
                upload_speed=round(ul_speed, 2),
                jitter=round(jitter, 2),
                timestamp=now,
            )
            db.session.add(m)
            saved_measurements.append(m)

        db.session.commit()

        # Only raise alerts for truly significant breaches (not noise)
        new_alerts = []
        for m in saved_measurements:
            if m.latency > 300 or m.packet_loss > 10 or m.uptime < 90:
                from utils.alert_checker import check_and_raise_alerts
                new_alerts = check_and_raise_alerts(
                    [x for x in saved_measurements if x.latency > 300 or x.packet_loss > 10 or x.uptime < 90]
                )
                db.session.commit()
                break

        # --- Build national averages to broadcast ---
        latencies = [m.latency for m in saved_measurements]
        uptimes   = [m.uptime  for m in saved_measurements]
        losses    = [m.packet_loss for m in saved_measurements]
        active_alerts = Alert.query.filter_by(is_resolved=False).count()

        kpi_payload = {
            'avg_latency':     round(sum(latencies) / len(latencies), 1),
            'avg_uptime':      round(sum(uptimes)   / len(uptimes),   2),
            'avg_packet_loss': round(sum(losses)    / len(losses),    2),
            'active_alerts':   active_alerts,
            'timestamp':       now.strftime('%H:%M:%S'),
        }

        region_payload = [
            {
                'name':            m.region,
                'isp':             m.isp,
                'latency':         m.latency,
                'packet_loss':     m.packet_loss,
                'uptime':          m.uptime,
                'download_speed':  m.download_speed,
                'timestamp':       now.strftime('%H:%M:%S'),
                'status':          'Normal' if m.latency < 100 and m.uptime > 95 else 'Degraded',
            }
            for m in saved_measurements
        ]

        probe_status = {
            'status':         'ok',
            'last_run':       now.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'base_latency':   base_latency,
            'base_loss':      base_loss,
            'regions_probed': len(saved_measurements),
            'new_alerts':     len(new_alerts),
        }

        # --- Emit SocketIO events to all connected clients ---
        socketio.emit('kpi_update',     kpi_payload)
        socketio.emit('region_update',  region_payload)
        socketio.emit('probe_status',   probe_status)

        if new_alerts:
            for alert in new_alerts:
                socketio.emit('new_alert', {
                    'type':      alert.type,
                    'severity':  alert.severity,
                    'region':    alert.region,
                    'message':   alert.message,
                    'timestamp': alert.timestamp.strftime('%H:%M:%S'),
                })

        logger.info(
            f'Probe cycle complete: base={base_latency:.1f}ms, '
            f'regions={len(saved_measurements)}, alerts={len(new_alerts)}'
        )
