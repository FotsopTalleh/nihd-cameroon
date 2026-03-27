"""
SocketIO event handlers — server-side WebSocket events.
"""
import logging

logger = logging.getLogger(__name__)


def register_socket_events(socketio):

    @socketio.on('connect')
    def handle_connect():
        logger.info('Client connected via WebSocket')

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('Client disconnected from WebSocket')

    @socketio.on('request_latest')
    def handle_request_latest():
        """Client requests the latest snapshot immediately on connect."""
        from models import Measurement, Alert
        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(hours=24)
        measurements = Measurement.query.filter(Measurement.timestamp >= since).all()

        if measurements:
            latencies = [m.latency for m in measurements]
            uptimes   = [m.uptime  for m in measurements]
            losses    = [m.packet_loss for m in measurements]

            socketio.emit('kpi_update', {
                'avg_latency':     round(sum(latencies) / len(latencies), 1),
                'avg_uptime':      round(sum(uptimes)   / len(uptimes),   2),
                'avg_packet_loss': round(sum(losses)    / len(losses),    2),
                'active_alerts':   Alert.query.filter_by(is_resolved=False).count(),
                'timestamp':       datetime.utcnow().strftime('%H:%M:%S'),
            })
