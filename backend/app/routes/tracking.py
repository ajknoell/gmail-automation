from flask import Blueprint, request, jsonify, Response, redirect, g
from app import db
from app.models import EmailLog, LinkClick, OpenEvent
from datetime import datetime
import json

tracking_bp = Blueprint('tracking', __name__)

# 1x1 transparent GIF
PIXEL = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,'
    b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


@tracking_bp.route('/t/o/<tracking_id>')
def track_open(tracking_id):
    """Serve tracking pixel and record email open."""
    email_log = EmailLog.query.filter_by(tracking_id=tracking_id).first()
    if email_log:
        email_log.open_count = (email_log.open_count or 0) + 1
        if not email_log.opened_at:
            email_log.opened_at = datetime.utcnow()

        event = OpenEvent(
            email_log_id=email_log.id,
            tracking_id=tracking_id,
            user_agent=request.headers.get('User-Agent', '')[:500],
        )
        db.session.add(event)
        db.session.commit()

        # Push open event to Clay if configured
        try:
            from app.services.clay_export import ClayExportService
            ClayExportService.export_single_event('open', email_log)
        except Exception:
            pass  # Don't break tracking if Clay export fails

    return Response(
        PIXEL,
        mimetype='image/gif',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
        },
    )


@tracking_bp.route('/t/c/<tracking_id>/<link_id>')
def track_click(tracking_id, link_id):
    """Record link click and redirect to original URL."""
    email_log = EmailLog.query.filter_by(tracking_id=tracking_id).first()
    if not email_log:
        return 'Link not found', 404

    # Look up original URL from link_map
    link_map = json.loads(email_log.link_map) if email_log.link_map else {}
    original_url = link_map.get(link_id)
    if not original_url:
        return 'Link not found', 404

    # Record click
    email_log.click_count = (email_log.click_count or 0) + 1
    if not email_log.clicked_at:
        email_log.clicked_at = datetime.utcnow()

    click = LinkClick(
        email_log_id=email_log.id,
        tracking_id=tracking_id,
        link_id=link_id,
        original_url=original_url,
        user_agent=request.headers.get('User-Agent', '')[:500],
    )
    db.session.add(click)
    db.session.commit()

    # Push click event to Clay if configured
    try:
        from app.services.clay_export import ClayExportService
        ClayExportService.export_single_event('click', email_log)
    except Exception:
        pass  # Don't break tracking if Clay export fails

    return redirect(original_url, code=302)


@tracking_bp.route('/api/campaigns/<int:campaign_id>/tracking')
def campaign_tracking(campaign_id):
    """Get aggregate tracking stats for a campaign."""
    logs = EmailLog.query.filter_by(campaign_id=campaign_id).filter(
        EmailLog.status.in_(['sent', 'bounced'])
    ).all()

    total_sent = len(logs)
    if total_sent == 0:
        return jsonify({
            'total_sent': 0,
            'total_opened': 0,
            'total_clicked': 0,
            'total_replied': 0,
            'total_bounced': 0,
            'open_rate': 0,
            'click_rate': 0,
            'reply_rate': 0,
            'bounce_rate': 0,
        })

    total_opened = sum(1 for l in logs if l.opened_at)
    total_clicked = sum(1 for l in logs if l.clicked_at)
    total_replied = sum(1 for l in logs if l.replied_at)
    total_bounced = sum(1 for l in logs if l.bounced_at)

    return jsonify({
        'total_sent': total_sent,
        'total_opened': total_opened,
        'total_clicked': total_clicked,
        'total_replied': total_replied,
        'total_bounced': total_bounced,
        'open_rate': round(total_opened / total_sent, 2) if total_sent else 0,
        'click_rate': round(total_clicked / total_sent, 2) if total_sent else 0,
        'reply_rate': round(total_replied / total_sent, 2) if total_sent else 0,
        'bounce_rate': round(total_bounced / total_sent, 2) if total_sent else 0,
    })


@tracking_bp.route('/api/tracking/check-replies', methods=['POST'])
def check_replies():
    """Manually trigger reply detection."""
    from app.services.reply_checker import ReplyChecker
    results = ReplyChecker.check_replies()
    return jsonify(results)


@tracking_bp.route('/api/quick-send/history')
def quick_send_history():
    """Get recent Quick Send emails with tracking data."""
    logs = (
        EmailLog.query
        .filter_by(campaign_id=None, workspace_id=g.workspace_id)
        .order_by(EmailLog.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([l.to_dict() for l in logs])
