from datetime import datetime
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    organization = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    downloads = db.relationship('Download', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


class Measurement(db.Model):
    __tablename__ = 'measurements'

    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(100), nullable=False, index=True)
    isp = db.Column(db.String(100), nullable=True)
    latency = db.Column(db.Float, nullable=False)          # ms
    packet_loss = db.Column(db.Float, nullable=False)       # %
    uptime = db.Column(db.Float, nullable=False)            # %
    download_speed = db.Column(db.Float, nullable=True)     # Mbps
    upload_speed = db.Column(db.Float, nullable=True)       # Mbps
    jitter = db.Column(db.Float, nullable=True)             # ms
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'region': self.region,
            'isp': self.isp,
            'latency': self.latency,
            'packet_loss': self.packet_loss,
            'uptime': self.uptime,
            'download_speed': self.download_speed,
            'upload_speed': self.upload_speed,
            'jitter': self.jitter,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self):
        return f'<Measurement {self.region} @ {self.timestamp}>'


class Traceroute(db.Model):
    __tablename__ = 'traceroutes'

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    hops = db.Column(db.Text, nullable=False)               # JSON string
    total_hops = db.Column(db.Integer, nullable=True)
    total_latency = db.Column(db.Float, nullable=True)      # ms
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'source': self.source,
            'destination': self.destination,
            'hops': json.loads(self.hops) if self.hops else [],
            'total_hops': self.total_hops,
            'total_latency': self.total_latency,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self):
        return f'<Traceroute {self.source} → {self.destination}>'


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)        # e.g. "High Latency", "Packet Loss"
    severity = db.Column(db.String(20), nullable=False)     # critical, warning, info
    region = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=True)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'region': self.region,
            'message': self.message,
            'is_resolved': self.is_resolved,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self):
        return f'<Alert {self.type} [{self.severity}] @ {self.region}>'


class Download(db.Model):
    __tablename__ = 'downloads'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)    # pdf, csv
    region = db.Column(db.String(100), nullable=True)       # None = all regions
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(200), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)        # bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Download {self.file_type} by User {self.user_id}>'
