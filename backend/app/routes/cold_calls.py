from flask import Blueprint, request, jsonify, g
from datetime import datetime
from app import db
from app.models.cold_call import ColdCall, COLD_CALL_OUTCOMES, OUTCOME_LABELS
from app.models.contact import Contact
from app.models.recipient import Recipient

cold_calls_bp = Blueprint('cold_calls', __name__)


@cold_calls_bp.route('', methods=['GET'])
def list_cold_calls():
    """List cold calls, optionally filtered by contact_id or campaign_id."""
    contact_id = request.args.get('contact_id', type=int)
    campaign_id = request.args.get('campaign_id', type=int)

    query = ColdCall.query.filter(ColdCall.workspace_id == g.workspace_id)

    if contact_id:
        query = query.filter(ColdCall.contact_id == contact_id)
    if campaign_id:
        query = query.filter(ColdCall.campaign_id == campaign_id)

    calls = query.order_by(ColdCall.call_date.desc()).all()
    return jsonify([c.to_dict() for c in calls])


@cold_calls_bp.route('', methods=['POST'])
def create_cold_call():
    """Log a new cold call."""
    data = request.get_json()

    contact_id = data.get('contact_id')
    recipient_id = data.get('recipient_id')
    campaign_id = data.get('campaign_id')

    if not contact_id and not recipient_id:
        return jsonify({'error': 'contact_id or recipient_id is required'}), 400

    # If recipient_id provided, resolve/create the contact
    if not contact_id and recipient_id:
        recipient = Recipient.query.get(recipient_id)
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404
        # Look up or create contact by email
        contact = Contact.query.filter_by(
            email=recipient.email.strip().lower(),
            workspace_id=g.workspace_id,
        ).first()
        if not contact:
            contact = Contact(
                email=recipient.email.strip().lower(),
                name=recipient.name,
                company=recipient.company,
                workspace_id=g.workspace_id,
                status='contacted',
            )
            db.session.add(contact)
            db.session.flush()
        contact_id = contact.id
        if not campaign_id:
            campaign_id = recipient.campaign_id

    # Validate contact exists
    contact = Contact.query.get(contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    # Validate outcome
    outcome = data.get('outcome', 'connected')
    if outcome not in COLD_CALL_OUTCOMES:
        return jsonify({
            'error': f'Invalid outcome. Must be one of: {", ".join(COLD_CALL_OUTCOMES)}'
        }), 400

    # Parse call_date
    call_date = datetime.utcnow()
    if data.get('call_date'):
        try:
            call_date = datetime.fromisoformat(data['call_date'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid call_date format'}), 400

    cold_call = ColdCall(
        workspace_id=g.workspace_id,
        contact_id=contact_id,
        campaign_id=campaign_id,
        recipient_id=recipient_id,
        call_date=call_date,
        outcome=outcome,
        notes=data.get('notes', '').strip() or None,
        duration_minutes=data.get('duration_minutes'),
    )
    db.session.add(cold_call)
    db.session.commit()

    return jsonify(cold_call.to_dict()), 201


@cold_calls_bp.route('/<int:call_id>', methods=['PUT'])
def update_cold_call(call_id):
    """Update an existing cold call record."""
    cold_call = ColdCall.query.get(call_id)
    if not cold_call:
        return jsonify({'error': 'Cold call not found'}), 404

    data = request.get_json()

    if 'outcome' in data:
        if data['outcome'] not in COLD_CALL_OUTCOMES:
            return jsonify({
                'error': f'Invalid outcome. Must be one of: {", ".join(COLD_CALL_OUTCOMES)}'
            }), 400
        cold_call.outcome = data['outcome']

    if 'notes' in data:
        cold_call.notes = data['notes'].strip() or None
    if 'duration_minutes' in data:
        cold_call.duration_minutes = data['duration_minutes']
    if 'call_date' in data and data['call_date']:
        try:
            cold_call.call_date = datetime.fromisoformat(data['call_date'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid call_date format'}), 400

    db.session.commit()
    return jsonify(cold_call.to_dict())


@cold_calls_bp.route('/<int:call_id>', methods=['DELETE'])
def delete_cold_call(call_id):
    """Delete a cold call record."""
    cold_call = ColdCall.query.get(call_id)
    if not cold_call:
        return jsonify({'error': 'Cold call not found'}), 404

    db.session.delete(cold_call)
    db.session.commit()
    return jsonify({'success': True})


@cold_calls_bp.route('/outcomes', methods=['GET'])
def list_outcomes():
    """Return available outcomes for the frontend."""
    return jsonify([
        {'value': o, 'label': OUTCOME_LABELS[o]}
        for o in COLD_CALL_OUTCOMES
    ])
