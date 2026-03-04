from flask import Blueprint, request, jsonify, g
from datetime import date, datetime
from app import db
from app.models.contact import Contact, CONTACT_STATUSES, STATUS_LABELS, STATUS_COLORS
from app.models.tag import Tag, contact_tags
from app.models import EmailLog, Campaign, Settings
from app.models.settings import WorkspaceSettings

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('', methods=['GET'])
def list_contacts():
    """List contacts with search, sort, tag/status filtering, and pagination."""
    q = request.args.get('q', '').strip()
    sort_field = request.args.get('sort', 'last_contacted_at')
    order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    tag_filter = request.args.get('tag', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Contact.query.filter(Contact.workspace_id == g.workspace_id)

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                Contact.email.ilike(like),
                Contact.name.ilike(like),
                Contact.company.ilike(like),
            )
        )

    if tag_filter:
        query = query.join(contact_tags).join(Tag).filter(Tag.name == tag_filter, Tag.workspace_id == g.workspace_id)

    if status_filter:
        query = query.filter(Contact.status == status_filter)

    sort_map = {
        'last_contacted_at': Contact.last_contacted_at,
        'first_contacted_at': Contact.first_contacted_at,
        'name': Contact.name,
        'company': Contact.company,
        'total_emails_sent': Contact.total_emails_sent,
        'created_at': Contact.created_at,
        'email': Contact.email,
        'status': Contact.status,
    }
    sort_col = sort_map.get(sort_field, Contact.last_contacted_at)

    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'contacts': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
    })


@contacts_bp.route('/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    """Get contact detail with email history."""
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    # Find emails where this contact is recipient OR sender (for gmail_sync received)
    logs = (
        EmailLog.query
        .filter(
            db.or_(
                EmailLog.recipient_email == contact.email,
                db.and_(
                    EmailLog.sender_email == contact.email,
                    EmailLog.source == 'gmail_sync',
                ),
            )
        )
        .order_by(EmailLog.created_at.desc())
        .all()
    )

    email_history = []
    for log in logs:
        entry = log.to_dict()
        if log.source == 'gmail_sync':
            if log.direction == 'received':
                entry['source'] = 'Gmail (received)'
            else:
                entry['source'] = 'Gmail (sent)'
        elif log.campaign_id:
            campaign = Campaign.query.get(log.campaign_id)
            entry['source'] = campaign.name if campaign else f'Campaign #{log.campaign_id}'
        else:
            entry['source'] = 'Quick Send'
        email_history.append(entry)

    # Cold call history
    from app.models.cold_call import ColdCall
    cold_calls = (
        ColdCall.query
        .filter_by(contact_id=contact.id)
        .order_by(ColdCall.call_date.desc())
        .all()
    )

    return jsonify({
        'contact': contact.to_dict(),
        'email_history': email_history,
        'cold_calls': [c.to_dict() for c in cold_calls],
    })


@contacts_bp.route('/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    """Update contact details (name, company, website, notes, status)."""
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    data = request.get_json()

    if 'name' in data:
        contact.name = data['name']
    if 'company' in data:
        contact.company = data['company']
    if 'website' in data:
        contact.website = data['website']
    if 'notes' in data:
        contact.notes = data['notes']
    if 'status' in data:
        if data['status'] in CONTACT_STATUSES:
            contact.status = data['status']
        else:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(CONTACT_STATUSES)}'}), 400
    if 'follow_up_date' in data:
        if data['follow_up_date']:
            try:
                contact.follow_up_date = date.fromisoformat(data['follow_up_date'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            contact.follow_up_date = None
    if 'follow_up_note' in data:
        contact.follow_up_note = data['follow_up_note'] or None

    db.session.commit()
    return jsonify(contact.to_dict())


@contacts_bp.route('/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """Delete a contact from the directory (keeps email logs)."""
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    db.session.delete(contact)
    db.session.commit()
    return jsonify({'success': True})


# --- Follow-ups ---

@contacts_bp.route('/follow-ups', methods=['GET'])
def list_follow_ups():
    """List contacts with follow-up dates set, sorted by date (overdue first)."""
    contacts = (
        Contact.query
        .filter(Contact.workspace_id == g.workspace_id, Contact.follow_up_date.isnot(None))
        .order_by(Contact.follow_up_date.asc())
        .all()
    )

    today = date.today()
    results = []
    for c in contacts:
        # Get the last email sent to this contact for context
        last_email = (
            EmailLog.query
            .filter_by(recipient_email=c.email, status='sent')
            .order_by(EmailLog.created_at.desc())
            .first()
        )

        entry = c.to_dict()
        entry['is_overdue'] = c.follow_up_date < today
        entry['is_today'] = c.follow_up_date == today
        entry['last_email'] = {
            'id': last_email.id,
            'subject': last_email.subject,
            'body': last_email.body,
            'created_at': last_email.created_at.isoformat() if last_email.created_at else None,
            'gmail_thread_id': last_email.gmail_thread_id,
            'gmail_account_id': last_email.gmail_account_id,
        } if last_email else None
        results.append(entry)

    return jsonify(results)


@contacts_bp.route('/<int:contact_id>/generate-followup', methods=['POST'])
def generate_followup(contact_id):
    """Generate a follow-up email draft for a contact who hasn't replied."""
    contact = Contact.query.get_or_404(contact_id)

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    # Get the last email sent to this contact
    last_email = (
        EmailLog.query
        .filter_by(recipient_email=contact.email, status='sent')
        .order_by(EmailLog.created_at.desc())
        .first()
    )

    if not last_email:
        return jsonify({'error': 'No previous emails found for this contact'}), 400

    # Calculate days since last email
    days_since = None
    if last_email.created_at:
        days_since = (datetime.utcnow() - last_email.created_at).days

    # Get writing style (workspace-scoped)
    import json
    writing_style = None
    style_json = WorkspaceSettings.get(g.workspace_id, 'writing_style')
    if not style_json:
        style_json = Settings.get('writing_style')  # fallback to global
    if style_json:
        try:
            writing_style = json.loads(style_json) if isinstance(style_json, str) else style_json
        except Exception:
            pass

    from app.services.claude_service import ClaudeService
    claude = ClaudeService(api_key)

    result = claude.generate_followup_email(
        original_subject=last_email.subject or '',
        original_body=last_email.body or '',
        contact_info={
            'name': contact.name,
            'company': contact.company,
        },
        follow_up_note=contact.follow_up_note,
        days_since_last=days_since,
        writing_style=writing_style,
    )

    return jsonify({
        'subject': result.get('subject', ''),
        'body': result.get('body', ''),
        'original_email_id': last_email.id,
        'gmail_thread_id': last_email.gmail_thread_id,
        'gmail_account_id': last_email.gmail_account_id,
    })


# --- Tags ---

@contacts_bp.route('/tags', methods=['GET'])
def list_tags():
    """List all tags with contact counts."""
    tags = Tag.query.filter_by(workspace_id=g.workspace_id).order_by(Tag.name).all()
    return jsonify([t.to_dict(include_count=True) for t in tags])


@contacts_bp.route('/tags', methods=['POST'])
def create_tag():
    """Create a new tag."""
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Tag name is required'}), 400

    existing = Tag.query.filter(Tag.name.ilike(name), Tag.workspace_id == g.workspace_id).first()
    if existing:
        return jsonify({'error': 'Tag already exists'}), 400

    color = data.get('color', '#6B7280')
    tag = Tag(name=name, color=color, workspace_id=g.workspace_id)
    db.session.add(tag)
    db.session.commit()
    return jsonify(tag.to_dict(include_count=True)), 201


@contacts_bp.route('/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """Delete a tag (removes from all contacts)."""
    tag = Tag.query.get(tag_id)
    if not tag:
        return jsonify({'error': 'Tag not found'}), 404

    db.session.delete(tag)
    db.session.commit()
    return jsonify({'success': True})


@contacts_bp.route('/<int:contact_id>/tags', methods=['POST'])
def add_tag_to_contact(contact_id):
    """Add a tag to a contact. Creates the tag if it doesn't exist."""
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    data = request.get_json()
    tag_id = data.get('tag_id')
    tag_name = (data.get('tag_name') or '').strip()

    if tag_id:
        tag = Tag.query.get(tag_id)
    elif tag_name:
        tag = Tag.query.filter(Tag.name.ilike(tag_name), Tag.workspace_id == g.workspace_id).first()
        if not tag:
            tag = Tag(name=tag_name, color=data.get('color', '#6B7280'), workspace_id=g.workspace_id)
            db.session.add(tag)
            db.session.flush()
    else:
        return jsonify({'error': 'tag_id or tag_name is required'}), 400

    if not tag:
        return jsonify({'error': 'Tag not found'}), 404

    if tag not in contact.tags:
        contact.tags.append(tag)
        db.session.commit()

    return jsonify(contact.to_dict())


@contacts_bp.route('/<int:contact_id>/tags/<int:tag_id>', methods=['DELETE'])
def remove_tag_from_contact(contact_id, tag_id):
    """Remove a tag from a contact."""
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    tag = Tag.query.get(tag_id)
    if tag and tag in contact.tags:
        contact.tags.remove(tag)
        db.session.commit()

    return jsonify(contact.to_dict())


# --- Statuses reference ---

@contacts_bp.route('/statuses', methods=['GET'])
def list_statuses():
    """Return available statuses for the frontend."""
    return jsonify([
        {'value': s, 'label': STATUS_LABELS[s], 'color': STATUS_COLORS[s]}
        for s in CONTACT_STATUSES
    ])
