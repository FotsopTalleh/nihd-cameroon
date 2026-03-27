from flask import Blueprint, render_template, request, jsonify, abort
from models import Measurement, Traceroute, Alert
from extensions import db
from datetime import datetime, timedelta
import json

api_bp = Blueprint('api', __name__)

VALID_REGIONS = [
    'Yaoundé (Centre)', 'Douala (Littoral)', 'Bafoussam (West)',
    'Garoua (North)', 'Maroua (Far North)', 'Ngaoundéré (Adamawa)',
    'Bertoua (East)', 'Bamenda (Northwest)', 'Buea (Southwest)', 'Ebolowa (South)'
]


@api_bp.route('/submit/ping', methods=['POST'])
def submit_ping():
    """Ingest a new measurement from a probe agent."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    required = ['region', 'latency', 'packet_loss', 'uptime']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400

    try:
        m = Measurement(
            region=str(data['region'])[:100],
            isp=str(data.get('isp', 'Unknown'))[:100],
            latency=float(data['latency']),
            packet_loss=float(data['packet_loss']),
            uptime=float(data['uptime']),
            download_speed=float(data['download_speed']) if 'download_speed' in data else None,
            upload_speed=float(data['upload_speed']) if 'upload_speed' in data else None,
            jitter=float(data['jitter']) if 'jitter' in data else None,
        )
        db.session.add(m)
        db.session.commit()
        return jsonify({'status': 'ok', 'id': m.id}), 201
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/submit/traceroute', methods=['POST'])
def submit_traceroute():
    """Ingest a traceroute result."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    required = ['source', 'destination', 'hops']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400

    try:
        hops = data['hops'] if isinstance(data['hops'], list) else []
        t = Traceroute(
            source=str(data['source'])[:150],
            destination=str(data['destination'])[:150],
            hops=json.dumps(hops),
            total_hops=len(hops),
            total_latency=float(data.get('total_latency', 0)),
        )
        db.session.add(t)
        db.session.commit()
        return jsonify({'status': 'ok', 'id': t.id}), 201
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/dashboard-data')
def dashboard_data():
    """Return aggregated stats for the home dashboard (public)."""
    since = datetime.utcnow() - timedelta(hours=24)
    measurements = Measurement.query.filter(Measurement.timestamp >= since).all()

    if not measurements:
        return jsonify({'avg_latency': 0, 'avg_uptime': 0,
                        'avg_packet_loss': 0, 'active_alerts': 0,
                        'regions': [], 'chart_labels': [], 'chart_latency': []})

    import statistics
    latencies = [m.latency for m in measurements]
    uptimes = [m.uptime for m in measurements]
    losses = [m.packet_loss for m in measurements]

    # Per-region aggregation
    region_data = {}
    for m in measurements:
        if m.region not in region_data:
            region_data[m.region] = {'latencies': [], 'uptimes': [], 'losses': []}
        region_data[m.region]['latencies'].append(m.latency)
        region_data[m.region]['uptimes'].append(m.uptime)
        region_data[m.region]['losses'].append(m.packet_loss)

    regions = []
    for region, vals in region_data.items():
        avg_lat = sum(vals['latencies']) / len(vals['latencies'])
        avg_up = sum(vals['uptimes']) / len(vals['uptimes'])
        status = 'Normal' if avg_lat < 100 and avg_up > 95 else 'Degraded'
        regions.append({
            'name': region,
            'avg_latency': round(avg_lat, 1),
            'avg_uptime': round(avg_up, 2),
            'avg_packet_loss': round(sum(vals['losses']) / len(vals['losses']), 2),
            'status': status
        })

    active_alerts = Alert.query.filter_by(is_resolved=False).count()

    # Chart: latency over last 12 hours (hourly buckets)
    chart_labels = []
    chart_latency = []
    chart_uptime = []
    for h in range(11, -1, -1):
        start = datetime.utcnow() - timedelta(hours=h + 1)
        end = datetime.utcnow() - timedelta(hours=h)
        bucket = [m.latency for m in measurements if start <= m.timestamp < end]
        uptime_bucket = [m.uptime for m in measurements if start <= m.timestamp < end]
        chart_labels.append(end.strftime('%H:%M'))
        chart_latency.append(round(sum(bucket) / len(bucket), 1) if bucket else None)
        chart_uptime.append(round(sum(uptime_bucket) / len(uptime_bucket), 2) if uptime_bucket else None)

    return jsonify({
        'avg_latency': round(sum(latencies) / len(latencies), 1),
        'avg_uptime': round(sum(uptimes) / len(uptimes), 2),
        'avg_packet_loss': round(sum(losses) / len(losses), 2),
        'active_alerts': active_alerts,
        'regions': regions,
        'chart_labels': chart_labels,
        'chart_latency': chart_latency,
        'chart_uptime': chart_uptime,
    })


@api_bp.route('/api/region-data')
def region_data():
    """Return measurements for a specific region."""
    region = request.args.get('region', '')
    hours = int(request.args.get('hours', 24))
    since = datetime.utcnow() - timedelta(hours=hours)

    q = Measurement.query.filter(Measurement.timestamp >= since)
    if region:
        q = q.filter(Measurement.region == region)
    q = q.order_by(Measurement.timestamp.asc())
    measurements = q.all()

    return jsonify([m.to_dict() for m in measurements])


@api_bp.route('/api/alerts-data')
def alerts_data():
    """Return alerts with optional filters."""
    region = request.args.get('region', '')
    severity = request.args.get('severity', '')
    resolved = request.args.get('resolved', 'false')

    q = Alert.query
    if region:
        q = q.filter(Alert.region == region)
    if severity:
        q = q.filter(Alert.severity == severity)
    if resolved == 'false':
        q = q.filter_by(is_resolved=False)

    alerts = q.order_by(Alert.timestamp.desc()).limit(200).all()
    return jsonify([a.to_dict() for a in alerts])


@api_bp.route('/api/regions-list')
def regions_list():
    """Return distinct region names in the database."""
    regions = db.session.query(Measurement.region).distinct().all()
    return jsonify([r[0] for r in regions])


@api_bp.route('/api/traceroutes')
def traceroutes():
    """Return recent traceroutes."""
    source = request.args.get('source', '')
    dest = request.args.get('destination', '')

    q = Traceroute.query
    if source:
        q = q.filter(Traceroute.source.ilike(f'%{source}%'))
    if dest:
        q = q.filter(Traceroute.destination.ilike(f'%{dest}%'))

    results = q.order_by(Traceroute.timestamp.desc()).limit(50).all()
    return jsonify([t.to_dict() for t in results])


@api_bp.route('/api/isp-comparison')
def isp_comparison():
    """Return per-ISP averages for the last 24h."""
    since = datetime.utcnow() - timedelta(hours=24)
    measurements = Measurement.query.filter(
        Measurement.timestamp >= since,
        Measurement.isp.isnot(None)
    ).all()

    isp_data = {}
    for m in measurements:
        if m.isp not in isp_data:
            isp_data[m.isp] = {'latencies': [], 'uptimes': [], 'losses': []}
        isp_data[m.isp]['latencies'].append(m.latency)
        isp_data[m.isp]['uptimes'].append(m.uptime)
        isp_data[m.isp]['losses'].append(m.packet_loss)

    result = []
    for isp, vals in isp_data.items():
        result.append({
            'isp': isp,
            'avg_latency': round(sum(vals['latencies']) / len(vals['latencies']), 1),
            'avg_uptime': round(sum(vals['uptimes']) / len(vals['uptimes']), 2),
            'avg_packet_loss': round(sum(vals['losses']) / len(vals['losses']), 2),
        })

    return jsonify(sorted(result, key=lambda x: x['avg_latency']))
