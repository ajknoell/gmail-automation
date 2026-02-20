"""
Daily Brief routes — aggregate overnight activity for the daily brief view.
"""
from flask import Blueprint, request, jsonify, g
from app import db
from datetime import datetime, timedelta, date
from sqlalchemy import func

brief_bp = Blueprint('brief', __name__)


@brief_bp.route('', methods=['GET'])
def daily_brief():
    """
    Aggregate overnight activity for the daily brief.

    Returns summary of: new prospects, replies, auto-responses,
    follow-ups due, pipeline, active campaigns, and email stats.
    """
    from app.models.contact import Contact, CONTACT_STATUSES
    from app.models.reply_message import ReplyMessage
    from app.models.email_log import EmailLog
    from app.models.campaign import Campaign

    ws_id = g.workspace_id

    # Time range: since yesterday midnight
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    cutoff = datetime.combine(target_date - timedelta(days=1), datetime.min.time())
    today_start = datetime.combine(target_date, datetime.min.time())

    # 1. New prospects discovered
    new_prospects = Contact.query.filter(
        Contact.workspace_id == ws_id,
        Contact.status == 'discovered',
        Contact.discovered_at >= cutoff,
    ).count()

    total_prospects = Contact.query.filter_by(
        workspace_id=ws_id, status='discovered'
    ).count()

    # 2. Replies received (grouped by sentiment)
    reply_query = (
        db.session.query(ReplyMessage.sentiment, func.count(ReplyMessage.id))
        .join(EmailLog, ReplyMessage.email_log_id == EmailLog.id)
        .filter(
            EmailLog.workspace_id == ws_id,
            ReplyMessage.received_at >= cutoff,
        )
        .group_by(ReplyMessage.sentiment)
        .all()
    )
    replies = {
        'total': sum(c for _, c in reply_query),
        'positive': next((c for s, c in reply_query if s == 'positive'), 0),
        'negative': next((c for s, c in reply_query if s == 'negative'), 0),
        'neutral': next((c for s, c in reply_query if s == 'neutral'), 0),
    }

    # 3. Auto-responses sent
    auto_responses = (
        db.session.query(func.count(ReplyMessage.id))
        .join(EmailLog, ReplyMessage.email_log_id == EmailLog.id)
        .filter(
            EmailLog.workspace_id == ws_id,
            ReplyMessage.auto_responded == True,
            ReplyMessage.response_sent_at >= cutoff,
        )
        .scalar() or 0
    )

    # 4. Flagged for review
    flagged_count = (
        db.session.query(func.count(ReplyMessage.id))
        .join(EmailLog, ReplyMessage.email_log_id == EmailLog.id)
        .filter(
            EmailLog.workspace_id == ws_id,
            ReplyMessage.flagged_for_review == True,
            ReplyMessage.response_sent_at.is_(None),
        )
        .scalar() or 0
    )

    # 5. Follow-ups due today
    follow_ups_due = Contact.query.filter(
        Contact.workspace_id == ws_id,
        Contact.follow_up_date <= target_date,
        Contact.follow_up_date.isnot(None),
    ).count()

    follow_up_contacts = Contact.query.filter(
        Contact.workspace_id == ws_id,
        Contact.follow_up_date <= target_date,
        Contact.follow_up_date.isnot(None),
    ).limit(10).all()

    # 6. Pipeline summary (contacts by status)
    pipeline_query = (
        db.session.query(Contact.status, func.count(Contact.id))
        .filter(Contact.workspace_id == ws_id)
        .group_by(Contact.status)
        .all()
    )
    pipeline = {status: count for status, count in pipeline_query}

    # 7. Active campaigns
    active_campaigns = Campaign.query.filter(
        Campaign.workspace_id == ws_id,
        Campaign.status.in_(['running', 'sequence_active']),
    ).count()

    # 8. Email stats for today
    emails_sent_today = EmailLog.query.filter(
        EmailLog.workspace_id == ws_id,
        EmailLog.status == 'sent',
        EmailLog.created_at >= today_start,
    ).count()

    opens_today = EmailLog.query.filter(
        EmailLog.workspace_id == ws_id,
        EmailLog.opened_at >= today_start,
    ).count()

    clicks_today = EmailLog.query.filter(
        EmailLog.workspace_id == ws_id,
        EmailLog.clicked_at >= today_start,
    ).count()

    # 9. Needs attention items
    needs_response = (
        db.session.query(func.count(ReplyMessage.id))
        .join(EmailLog, ReplyMessage.email_log_id == EmailLog.id)
        .filter(
            EmailLog.workspace_id == ws_id,
            ReplyMessage.response_sent_at.is_(None),
            ReplyMessage.auto_responded == False,
            ReplyMessage.sentiment.in_(['positive', 'negative']),
        )
        .scalar() or 0
    )

    return jsonify({
        'date': target_date.isoformat(),
        'new_prospects': {
            'count': new_prospects,
            'total': total_prospects,
        },
        'replies': replies,
        'auto_responses': auto_responses,
        'flagged_for_review': flagged_count,
        'follow_ups': {
            'due': follow_ups_due,
            'contacts': [c.to_dict() for c in follow_up_contacts],
        },
        'pipeline': pipeline,
        'active_campaigns': active_campaigns,
        'email_stats': {
            'sent': emails_sent_today,
            'opens': opens_today,
            'clicks': clicks_today,
        },
        'needs_attention': {
            'replies_pending': needs_response,
            'flagged': flagged_count,
            'follow_ups_due': follow_ups_due,
        },
    })
