from flask import Blueprint, request, jsonify, g
from datetime import datetime, date
from app import db
from app.models import EmailLog, Settings, OAuthToken
from app.models.contact import Contact
from app.models.reply_message import ReplyMessage
from app.models.settings import WorkspaceSettings

replies_bp = Blueprint('replies', __name__)


@replies_bp.route('', methods=['GET'])
def list_replies():
    """List all replies with optional filters."""
    sentiment = request.args.get('sentiment')
    responded = request.args.get('responded')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = ReplyMessage.query.join(EmailLog, ReplyMessage.email_log_id == EmailLog.id).filter(
        EmailLog.workspace_id == g.workspace_id
    )

    if sentiment:
        query = query.filter(ReplyMessage.sentiment == sentiment)

    if responded == 'true':
        query = query.filter(ReplyMessage.response_sent_at.isnot(None))
    elif responded == 'false':
        query = query.filter(ReplyMessage.response_sent_at.is_(None))

    query = query.order_by(ReplyMessage.received_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    results = []
    for reply in pagination.items:
        email_log = EmailLog.query.get(reply.email_log_id)
        contact = None
        if email_log:
            contact = Contact.query.filter_by(email=email_log.recipient_email, workspace_id=g.workspace_id).first()

        results.append({
            'reply': reply.to_dict(),
            'original_email': {
                'id': email_log.id,
                'subject': email_log.subject,
                'body': email_log.body,
                'recipient_email': email_log.recipient_email,
                'gmail_thread_id': email_log.gmail_thread_id,
                'gmail_message_id': email_log.gmail_message_id,
                'gmail_account_id': email_log.gmail_account_id,
                'created_at': email_log.created_at.isoformat() if email_log.created_at else None,
            } if email_log else None,
            'contact': contact.to_dict() if contact else None,
        })

    return jsonify({
        'replies': results,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@replies_bp.route('/<int:reply_id>', methods=['GET'])
def get_reply(reply_id):
    """Get a single reply with full context."""
    reply = ReplyMessage.query.get_or_404(reply_id)
    email_log = EmailLog.query.get(reply.email_log_id)

    contact = None
    if email_log:
        contact = Contact.query.filter_by(email=email_log.recipient_email, workspace_id=g.workspace_id).first()

    return jsonify({
        'reply': reply.to_dict(),
        'original_email': email_log.to_dict() if email_log else None,
        'contact': contact.to_dict() if contact else None,
    })


@replies_bp.route('/<int:reply_id>/classify', methods=['POST'])
def classify_reply(reply_id):
    """Re-run sentiment classification on a reply."""
    reply = ReplyMessage.query.get_or_404(reply_id)
    email_log = EmailLog.query.get(reply.email_log_id)

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    from app.services.claude_service import ClaudeService
    claude = ClaudeService(api_key)

    result = claude.classify_sentiment(
        original_subject=email_log.subject or '',
        original_body=email_log.body or '',
        reply_text=reply.body_text or reply.snippet or '',
    )

    if result:
        reply.sentiment = result.get('sentiment')
        reply.sentiment_reason = result.get('reason')
        db.session.commit()

    return jsonify({
        'sentiment': reply.sentiment,
        'reason': reply.sentiment_reason,
    })


@replies_bp.route('/<int:reply_id>/generate-response', methods=['POST'])
def generate_response(reply_id):
    """Generate an AI response for a reply."""
    reply = ReplyMessage.query.get_or_404(reply_id)
    email_log = EmailLog.query.get(reply.email_log_id)
    data = request.get_json() or {}

    response_type = data.get('type', 'rebuttal')
    account_id = data.get('account_id')

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    # Get contact info
    contact = Contact.query.filter_by(email=email_log.recipient_email, workspace_id=g.workspace_id).first()
    contact_info = {
        'name': contact.name if contact else reply.from_name,
        'company': contact.company if contact else None,
    }

    # Get writing style (workspace-scoped, fallback to global)
    import json
    writing_style = None
    style_json = WorkspaceSettings.get(g.workspace_id, 'writing_style')
    if not style_json:
        style_json = Settings.get('writing_style')
    if style_json:
        try:
            writing_style = json.loads(style_json) if isinstance(style_json, str) else style_json
        except Exception:
            pass

    from app.services.claude_service import ClaudeService

    claude = ClaudeService(api_key)

    if response_type == 'meeting_followup':
        # Get calendar availability
        available_slots = []
        try:
            from app.services.calendar_service import CalendarService
            cal = CalendarService(account_id=account_id)
            if cal.connect():
                available_slots = cal.get_available_slots()
        except Exception as e:
            print(f"Calendar error: {e}")

        result = claude.generate_meeting_followup(
            original_subject=email_log.subject or '',
            original_body=email_log.body or '',
            reply_text=reply.body_text or reply.snippet or '',
            contact_info=contact_info,
            available_slots=available_slots,
            writing_style=writing_style,
        )

        # Cache the generated response
        reply.ai_response_subject = result.get('subject', '')
        reply.ai_response_body = result.get('body', '')
        db.session.commit()

        return jsonify({
            'subject': result.get('subject', ''),
            'body': result.get('body', ''),
            'available_slots': available_slots,
            'type': 'meeting_followup',
        })

    else:
        # Default: rebuttal
        result = claude.generate_rebuttal(
            original_subject=email_log.subject or '',
            original_body=email_log.body or '',
            reply_text=reply.body_text or reply.snippet or '',
            contact_info=contact_info,
            writing_style=writing_style,
        )

        # Cache the generated response
        reply.ai_response_subject = result.get('subject', '')
        reply.ai_response_body = result.get('body', '')
        db.session.commit()

        return jsonify({
            'subject': result.get('subject', ''),
            'body': result.get('body', ''),
            'type': 'rebuttal',
        })


@replies_bp.route('/<int:reply_id>/send-response', methods=['POST'])
def send_response(reply_id):
    """Send a response in the same Gmail thread."""
    reply = ReplyMessage.query.get_or_404(reply_id)
    email_log = EmailLog.query.get(reply.email_log_id)
    data = request.get_json() or {}

    subject = data.get('subject', reply.ai_response_subject or f"Re: {email_log.subject}")
    body = data.get('body', reply.ai_response_body)
    account_id = data.get('account_id', email_log.gmail_account_id)

    if not body:
        return jsonify({'error': 'No response body provided'}), 400

    from app.services.gmail_service import GmailService

    gmail = GmailService(account_id=account_id)
    if not gmail.connect():
        return jsonify({'error': 'Gmail not connected'}), 400

    # Resolve attachments if provided
    attachment_list = None
    if data.get('attachments'):
        from app.routes.quick_send import _resolve_attachments
        attachment_list = _resolve_attachments(data['attachments']) or None

    # Send as a reply in the same thread
    result = gmail.send_reply(
        thread_id=email_log.gmail_thread_id,
        message_id=reply.gmail_message_id or email_log.gmail_message_id,
        to=reply.from_email or email_log.recipient_email,
        subject=subject,
        body=body,
        attachments=attachment_list,
    )

    if result.get('success'):
        reply.response_sent_at = datetime.utcnow()
        reply.ai_response_subject = subject
        reply.ai_response_body = body
        db.session.commit()

        # Optionally advance contact status
        contact = Contact.query.filter_by(email=email_log.recipient_email, workspace_id=g.workspace_id).first()
        if contact and reply.sentiment == 'positive' and contact.status in ('new', 'contacted', 'replied'):
            contact.status = 'interested'
            db.session.commit()

        return jsonify({
            'success': True,
            'message_id': result.get('message_id'),
            'sent_from': gmail.get_account_email(),
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to send'),
        }), 500


@replies_bp.route('/<int:reply_id>/dismiss', methods=['POST'])
def dismiss_reply(reply_id):
    """Mark a reply as handled without sending a response (pass/skip)."""
    reply = ReplyMessage.query.get_or_404(reply_id)

    # Verify workspace ownership
    email_log = EmailLog.query.get(reply.email_log_id)
    if not email_log or email_log.workspace_id != g.workspace_id:
        return jsonify({'error': 'Reply not found'}), 404

    reply.response_sent_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})


@replies_bp.route('/stats', methods=['GET'])
def reply_stats():
    """Get summary reply statistics."""
    ws_replies = ReplyMessage.query.join(EmailLog, ReplyMessage.email_log_id == EmailLog.id).filter(
        EmailLog.workspace_id == g.workspace_id
    )
    total = ws_replies.count()
    positive = ws_replies.filter(ReplyMessage.sentiment == 'positive').count()
    negative = ws_replies.filter(ReplyMessage.sentiment == 'negative').count()
    neutral = ws_replies.filter(ReplyMessage.sentiment == 'neutral').count()
    needs_response = ws_replies.filter(ReplyMessage.response_sent_at.is_(None)).count()

    # Follow-ups due (overdue + today)
    follow_ups_due = Contact.query.filter(
        Contact.workspace_id == g.workspace_id,
        Contact.follow_up_date.isnot(None),
        Contact.follow_up_date <= date.today(),
    ).count()

    return jsonify({
        'total': total,
        'positive': positive,
        'negative': negative,
        'neutral': neutral,
        'needs_response': needs_response,
        'follow_ups_due': follow_ups_due,
    })


@replies_bp.route('/<int:reply_id>/set-followup', methods=['POST'])
def set_reply_followup(reply_id):
    """Set a follow-up date on the contact associated with a reply."""
    reply = ReplyMessage.query.get_or_404(reply_id)
    email_log = EmailLog.query.get(reply.email_log_id)
    data = request.get_json() or {}

    contact = Contact.query.filter_by(email=email_log.recipient_email, workspace_id=g.workspace_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found for this reply'}), 404

    follow_date = data.get('date')
    if follow_date:
        try:
            contact.follow_up_date = date.fromisoformat(follow_date)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        contact.follow_up_date = None

    contact.follow_up_note = data.get('note') or None
    db.session.commit()

    return jsonify(contact.to_dict())


@replies_bp.route('/calendar-status', methods=['GET'])
def calendar_status():
    """Check if the default account has calendar scope."""
    token = OAuthToken.get_default_gmail()
    if not token:
        return jsonify({'has_calendar': False, 'reason': 'No Gmail account connected'})

    return jsonify({
        'has_calendar': token.has_calendar_scope,
        'account_id': token.id,
        'email': token.email_address,
    })
