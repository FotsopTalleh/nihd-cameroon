"""
alert_checker.py — Auto-generate alerts when thresholds are breached.
Called by the probe agent after each measurement cycle.
"""
from datetime import datetime


THRESHOLDS = {
    'latency_warning':  150,   # ms
    'latency_critical': 250,   # ms
    'loss_warning':     3,     # %
    'loss_critical':    8,     # %
    'uptime_warning':   95,    # %
    'uptime_critical':  90,    # %
}


def check_and_raise_alerts(measurements: list) -> list:
    """
    Inspect a list of Measurement objects and create Alert records for any
    that breach defined thresholds. Returns list of newly created Alert objects.
    """
    from models import Alert
    from extensions import db

    new_alerts = []

    for m in measurements:
        # Latency alerts
        if m.latency >= THRESHOLDS['latency_critical']:
            alert = _make_alert(
                alert_type='High Latency Detected',
                severity='critical',
                region=m.region,
                message=f'Latency reached {m.latency:.1f}ms on {m.isp} (threshold: {THRESHOLDS["latency_critical"]}ms)',
            )
            db.session.add(alert)
            new_alerts.append(alert)

        elif m.latency >= THRESHOLDS['latency_warning']:
            alert = _make_alert(
                alert_type='High Latency Detected',
                severity='warning',
                region=m.region,
                message=f'Latency elevated at {m.latency:.1f}ms on {m.isp} (threshold: {THRESHOLDS["latency_warning"]}ms)',
            )
            db.session.add(alert)
            new_alerts.append(alert)

        # Packet loss alerts
        if m.packet_loss >= THRESHOLDS['loss_critical']:
            alert = _make_alert(
                alert_type='Packet Loss Spike',
                severity='critical',
                region=m.region,
                message=f'Packet loss at {m.packet_loss:.1f}% on {m.isp} — service interruption likely',
            )
            db.session.add(alert)
            new_alerts.append(alert)

        elif m.packet_loss >= THRESHOLDS['loss_warning']:
            alert = _make_alert(
                alert_type='Packet Loss Spike',
                severity='warning',
                region=m.region,
                message=f'Elevated packet loss: {m.packet_loss:.1f}% on {m.isp}',
            )
            db.session.add(alert)
            new_alerts.append(alert)

        # Uptime alerts
        if m.uptime <= THRESHOLDS['uptime_critical']:
            alert = _make_alert(
                alert_type='Uptime Drop',
                severity='critical',
                region=m.region,
                message=f'Uptime fell to {m.uptime:.1f}% on {m.isp} — possible outage',
            )
            db.session.add(alert)
            new_alerts.append(alert)

        elif m.uptime <= THRESHOLDS['uptime_warning']:
            alert = _make_alert(
                alert_type='Uptime Drop',
                severity='warning',
                region=m.region,
                message=f'Uptime degraded: {m.uptime:.1f}% on {m.isp}',
            )
            db.session.add(alert)
            new_alerts.append(alert)

    return new_alerts


def _make_alert(alert_type, severity, region, message):
    from models import Alert
    return Alert(
        type=alert_type,
        severity=severity,
        region=region,
        message=message,
        timestamp=datetime.utcnow(),
        is_resolved=False,
    )
