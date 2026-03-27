from flask import Blueprint, send_file, redirect, url_for, flash, request, render_template
from flask_login import login_required, current_user
from models import Download, Measurement, Alert
from extensions import db
from datetime import datetime
import os

download_bp = Blueprint('download', __name__)


@download_bp.route('/download/csv')
@login_required
def download_csv():
    region = request.args.get('region', '')
    hours = int(request.args.get('hours', 24))

    from utils.csv_generator import generate_csv
    file_path, file_name = generate_csv(region=region, hours=hours)

    if not file_path:
        flash('Error generating CSV file. Please try again.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Save download record
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    rec = Download(
        user_id=current_user.id,
        file_type='csv',
        region=region or 'All Regions',
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
    )
    db.session.add(rec)
    db.session.commit()

    return send_file(file_path, as_attachment=True, download_name=file_name)


@download_bp.route('/download/pdf')
@login_required
def download_pdf():
    region = request.args.get('region', '')
    hours = int(request.args.get('hours', 24))

    from utils.pdf_generator import generate_pdf
    file_path, file_name = generate_pdf(region=region, hours=hours)

    if not file_path:
        flash('Error generating PDF file. Please try again.', 'danger')
        return redirect(url_for('dashboard.index'))

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    rec = Download(
        user_id=current_user.id,
        file_type='pdf',
        region=region or 'All Regions',
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
    )
    db.session.add(rec)
    db.session.commit()

    return send_file(file_path, as_attachment=True, download_name=file_name)


@download_bp.route('/my-downloads')
@login_required
def my_downloads():
    records = Download.query.filter_by(user_id=current_user.id)\
        .order_by(Download.created_at.desc()).all()
    return render_template('downloads/my_downloads.html', records=records)


@download_bp.route('/download/redownload/<int:download_id>')
@login_required
def redownload(download_id):
    rec = Download.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    if not os.path.exists(rec.file_path):
        flash('File no longer exists on disk. Please generate a new download.', 'warning')
        return redirect(url_for('download.my_downloads'))
    return send_file(rec.file_path, as_attachment=True, download_name=rec.file_name)
