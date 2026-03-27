"""
PDF report generator using ReportLab.
"""
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from config import Config


BRAND_BLUE = colors.HexColor('#1a73e8')
BRAND_DARK = colors.HexColor('#1a1a2e')
LIGHT_BLUE = colors.HexColor('#e8f0fe')
GREEN = colors.HexColor('#34a853')
RED = colors.HexColor('#ea4335')
ORANGE = colors.HexColor('#fbbc04')
GRAY = colors.HexColor('#5f6368')


def generate_pdf(region: str = '', hours: int = 24):
    """Generate a PDF report and return (file_path, file_name)."""
    try:
        from models import Measurement, Alert
        from extensions import db

        since = datetime.utcnow() - timedelta(hours=hours)
        q = Measurement.query.filter(Measurement.timestamp >= since)
        if region:
            q = q.filter(Measurement.region == region)
        measurements = q.order_by(Measurement.timestamp.asc()).all()

        alerts = Alert.query.filter(
            Alert.timestamp >= since,
            Alert.is_resolved == False
        ).order_by(Alert.timestamp.desc()).limit(30).all()

        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_region = region.replace(' ', '_').replace('/', '-') if region else 'AllRegions'
        file_name = f'NIHD_Report_{safe_region}_{ts}.pdf'
        file_path = os.path.join(Config.DOWNLOAD_FOLDER, file_name)

        doc = SimpleDocTemplate(
            file_path, pagesize=A4,
            topMargin=2*cm, bottomMargin=2*cm,
            leftMargin=2*cm, rightMargin=2*cm
        )

        styles = getSampleStyleSheet()
        story = []

        # Header
        header_style = ParagraphStyle('header', fontSize=20, textColor=BRAND_BLUE,
                                       spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')
        sub_style = ParagraphStyle('sub', fontSize=11, textColor=GRAY,
                                    spaceAfter=4, alignment=TA_CENTER)
        body_style = ParagraphStyle('body', fontSize=10, textColor=BRAND_DARK,
                                     spaceAfter=6, leading=14)
        section_style = ParagraphStyle('section', fontSize=13, textColor=BRAND_BLUE,
                                        spaceBefore=12, spaceAfter=6,
                                        fontName='Helvetica-Bold')
        small_style = ParagraphStyle('small', fontSize=8, textColor=GRAY)

        story.append(Paragraph('🌐 National Internet Health Dashboard', header_style))
        story.append(Paragraph('Republic of Cameroon – Internet Performance Report', sub_style))
        story.append(HRFlowable(width='100%', thickness=2, color=BRAND_BLUE))
        story.append(Spacer(1, 0.3 * cm))

        gen_time = datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')
        report_region = region if region else 'All Regions'
        period = f'Last {hours} Hours'
        story.append(Paragraph(
            f'<b>Report Region:</b> {report_region} &nbsp;&nbsp; '
            f'<b>Period:</b> {period} &nbsp;&nbsp; '
            f'<b>Generated:</b> {gen_time}',
            body_style
        ))
        story.append(Spacer(1, 0.5 * cm))

        # Summary stats
        if measurements:
            latencies = [m.latency for m in measurements]
            uptimes = [m.uptime for m in measurements]
            losses = [m.packet_loss for m in measurements]

            story.append(Paragraph('Executive Summary', section_style))
            summary_data = [
                ['Metric', 'Average', 'Min', 'Max'],
                ['Latency (ms)',
                 f'{sum(latencies)/len(latencies):.1f}',
                 f'{min(latencies):.1f}',
                 f'{max(latencies):.1f}'],
                ['Uptime (%)',
                 f'{sum(uptimes)/len(uptimes):.2f}',
                 f'{min(uptimes):.2f}',
                 f'{max(uptimes):.2f}'],
                ['Packet Loss (%)',
                 f'{sum(losses)/len(losses):.2f}',
                 f'{min(losses):.2f}',
                 f'{max(losses):.2f}'],
                ['Total Measurements', str(len(measurements)), '', ''],
            ]
            t = Table(summary_data, colWidths=[6*cm, 4*cm, 4*cm, 4*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_BLUE, colors.white]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.5*cm))

            # Per-region breakdown
            story.append(Paragraph('Regional Performance Breakdown', section_style))
            region_data = {}
            for m in measurements:
                if m.region not in region_data:
                    region_data[m.region] = {'latencies': [], 'uptimes': [], 'losses': []}
                region_data[m.region]['latencies'].append(m.latency)
                region_data[m.region]['uptimes'].append(m.uptime)
                region_data[m.region]['losses'].append(m.packet_loss)

            region_rows = [['Region', 'Avg Latency (ms)', 'Avg Uptime (%)', 'Avg Packet Loss (%)', 'Status']]
            for reg, vals in region_data.items():
                avg_lat = sum(vals['latencies']) / len(vals['latencies'])
                avg_up = sum(vals['uptimes']) / len(vals['uptimes'])
                avg_loss = sum(vals['losses']) / len(vals['losses'])
                status = 'Normal' if avg_lat < 100 and avg_up > 95 else 'Degraded'
                region_rows.append([
                    reg,
                    f'{avg_lat:.1f}',
                    f'{avg_up:.2f}',
                    f'{avg_loss:.2f}',
                    status
                ])

            rt = Table(region_rows, colWidths=[5*cm, 3.5*cm, 3.5*cm, 3.5*cm, 2.5*cm])
            rt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_BLUE, colors.white]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(rt)
            story.append(Spacer(1, 0.5*cm))

            # Recent measurements table (max 50 rows)
            story.append(Paragraph('Recent Measurement Data', section_style))
            mrows = [['Timestamp', 'Region', 'ISP', 'Latency (ms)', 'Uptime (%)', 'Pkt Loss (%)']]
            for m in measurements[-50:]:
                mrows.append([
                    m.timestamp.strftime('%Y-%m-%d %H:%M') if m.timestamp else '',
                    m.region,
                    m.isp or '',
                    f'{m.latency:.1f}',
                    f'{m.uptime:.2f}',
                    f'{m.packet_loss:.2f}',
                ])
            mt = Table(mrows, colWidths=[3.5*cm, 4.5*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm])
            mt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_BLUE, colors.white]),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(mt)
        else:
            story.append(Paragraph('No measurement data available for the selected period/region.', body_style))

        # Alerts section
        if alerts:
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph('Active Alerts', section_style))
            arows = [['Timestamp', 'Region', 'Type', 'Severity', 'Message']]
            for a in alerts[:20]:
                arows.append([
                    a.timestamp.strftime('%Y-%m-%d %H:%M') if a.timestamp else '',
                    a.region,
                    a.type,
                    a.severity.upper(),
                    (a.message or '')[:60],
                ])
            at = Table(arows, colWidths=[3.5*cm, 3.5*cm, 3.5*cm, 2.5*cm, 5*cm])
            at.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fff8e1'), colors.white]),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(at)

        # Footer
        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
        story.append(Paragraph(
            'This is a public research tool. Data provided by the National Internet Health Dashboard (NIHD) '
            'is for informational purposes only and should not be used for critical operational decisions.',
            small_style
        ))

        doc.build(story)
        return file_path, file_name

    except Exception as e:
        print(f'PDF generation error: {e}')
        return None, None
