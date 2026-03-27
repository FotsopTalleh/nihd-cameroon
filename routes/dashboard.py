from flask import Blueprint, render_template, request
from models import Measurement, Traceroute, Alert
from extensions import db
from datetime import datetime, timedelta
import json

dashboard_bp = Blueprint('dashboard', __name__)

REGIONS = [
    'Yaoundé (Centre)', 'Douala (Littoral)', 'Bafoussam (West)',
    'Garoua (North)', 'Maroua (Far North)', 'Ngaoundéré (Adamawa)',
    'Bertoua (East)', 'Bamenda (Northwest)', 'Buea (Southwest)', 'Ebolowa (South)'
]

ISPS = ['Camtel', 'MTN Cameroon', 'Orange Cameroon', 'Nexttel']


@dashboard_bp.route('/')
def index():
    """Home/Overview Dashboard - public."""
    active_alerts = Alert.query.filter_by(is_resolved=False).count()
    region_stats = _region_summary(hours=24)
    return render_template('index.html',
                           region_stats=region_stats,
                           active_alerts=active_alerts,
                           regions=REGIONS)


@dashboard_bp.route('/regions')
def regions():
    """Regional Dashboard - public."""
    selected_region = request.args.get('region', REGIONS[0])
    hours = int(request.args.get('hours', 24))
    if selected_region not in REGIONS:
        selected_region = REGIONS[0]

    since = datetime.utcnow() - timedelta(hours=hours)
    measurements = Measurement.query.filter(
        Measurement.region == selected_region,
        Measurement.timestamp >= since
    ).order_by(Measurement.timestamp.asc()).all()

    # ISP stats for region
    isp_stats = {}
    for m in measurements:
        if m.isp not in isp_stats:
            isp_stats[m.isp] = {'latencies': [], 'uptimes': [], 'losses': []}
        isp_stats[m.isp]['latencies'].append(m.latency)
        isp_stats[m.isp]['uptimes'].append(m.uptime)
        isp_stats[m.isp]['losses'].append(m.packet_loss)

    isp_table = []
    for isp, vals in isp_stats.items():
        avg_lat = sum(vals['latencies']) / len(vals['latencies'])
        avg_up = sum(vals['uptimes']) / len(vals['uptimes'])
        isp_table.append({
            'name': isp,
            'avg_latency': round(avg_lat, 1),
            'avg_uptime': round(avg_up, 2),
            'avg_packet_loss': round(sum(vals['losses']) / len(vals['losses']), 2),
            'status': 'Good' if avg_lat < 100 and avg_up > 95 else 'Degraded'
        })

    # Current stats
    current = measurements[-1] if measurements else None

    return render_template('regional.html',
                           regions=REGIONS,
                           selected_region=selected_region,
                           hours=hours,
                           measurements=[m.to_dict() for m in measurements],
                           isp_table=isp_table,
                           current=current)


@dashboard_bp.route('/traceroute')
def traceroute():
    """Traceroute Analysis page - public."""
    recent = Traceroute.query.order_by(Traceroute.timestamp.desc()).limit(20).all()
    sources = db.session.query(Traceroute.source).distinct().all()
    dests = db.session.query(Traceroute.destination).distinct().all()
    return render_template('traceroute.html',
                           recent_traces=[t.to_dict() for t in recent],
                           sources=[s[0] for s in sources],
                           destinations=[d[0] for d in dests])


@dashboard_bp.route('/historical')
def historical():
    """Historical Trends - public."""
    return render_template('historical.html', regions=REGIONS)


@dashboard_bp.route('/alerts')
def alerts():
    """Alerts & Events - public."""
    page = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', '')
    region = request.args.get('region', '')
    resolved = request.args.get('resolved', 'false')

    q = Alert.query
    if severity:
        q = q.filter(Alert.severity == severity)
    if region:
        q = q.filter(Alert.region == region)
    if resolved == 'false':
        q = q.filter_by(is_resolved=False)

    alerts_paginated = q.order_by(Alert.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False)

    # Summary counts
    counts = {
        'critical': Alert.query.filter_by(severity='critical', is_resolved=False).count(),
        'warning': Alert.query.filter_by(severity='warning', is_resolved=False).count(),
        'info': Alert.query.filter_by(severity='info', is_resolved=False).count(),
    }

    return render_template('alerts.html',
                           alerts=alerts_paginated,
                           regions=REGIONS,
                           counts=counts,
                           selected_severity=severity,
                           selected_region=region,
                           show_resolved=resolved)


@dashboard_bp.route('/sources')
def sources():
    """Data Sources & Methodology - public."""
    return render_template('sources.html')


@dashboard_bp.route('/about')
def about():
    """About page - public."""
    return render_template('about.html')


def _region_summary(hours=24):
    since = datetime.utcnow() - timedelta(hours=hours)
    measurements = Measurement.query.filter(Measurement.timestamp >= since).all()

    region_data = {}
    for m in measurements:
        if m.region not in region_data:
            region_data[m.region] = {'latencies': [], 'uptimes': [], 'losses': []}
        region_data[m.region]['latencies'].append(m.latency)
        region_data[m.region]['uptimes'].append(m.uptime)
        region_data[m.region]['losses'].append(m.packet_loss)

    result = []
    for region in REGIONS:
        if region in region_data:
            vals = region_data[region]
            avg_lat = sum(vals['latencies']) / len(vals['latencies'])
            avg_up = sum(vals['uptimes']) / len(vals['uptimes'])
            result.append({
                'name': region,
                'avg_latency': round(avg_lat, 1),
                'avg_uptime': round(avg_up, 2),
                'avg_packet_loss': round(sum(vals['losses']) / len(vals['losses']), 2),
                'status': 'Normal' if avg_lat < 100 and avg_up > 95 else 'Degraded'
            })
    return result
