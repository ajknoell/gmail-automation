from flask import Blueprint, request, jsonify
from app import db
from app.models import Template
from app.services.claude_service import clean_company_name
import re

templates_bp = Blueprint('templates', __name__)

def extract_variables(text):
    """Extract {{variable}} placeholders from text."""
    pattern = r'\{\{(\w+)\}\}'
    return list(set(re.findall(pattern, text)))

@templates_bp.route('', methods=['GET'])
def list_templates():
    """List all templates."""
    templates = Template.query.order_by(Template.updated_at.desc()).all()
    return jsonify([t.to_dict() for t in templates])

@templates_bp.route('/<int:id>', methods=['GET'])
def get_template(id):
    """Get a single template."""
    template = Template.query.get_or_404(id)
    return jsonify(template.to_dict())

@templates_bp.route('', methods=['POST'])
def create_template():
    """Create a new template."""
    data = request.get_json()

    if not data.get('name') or not data.get('subject') or not data.get('body'):
        return jsonify({'error': 'Name, subject, and body are required'}), 400

    # Auto-detect variables from subject and body
    variables = extract_variables(data['subject'] + ' ' + data['body'])

    template = Template(
        name=data['name'],
        subject=data['subject'],
        body=data['body']
    )
    template.set_variables(variables)

    db.session.add(template)
    db.session.commit()

    return jsonify(template.to_dict()), 201

@templates_bp.route('/<int:id>', methods=['PUT'])
def update_template(id):
    """Update a template."""
    template = Template.query.get_or_404(id)
    data = request.get_json()

    if 'name' in data:
        template.name = data['name']
    if 'subject' in data:
        template.subject = data['subject']
    if 'body' in data:
        template.body = data['body']

    # Re-detect variables
    variables = extract_variables(template.subject + ' ' + template.body)
    template.set_variables(variables)

    db.session.commit()
    return jsonify(template.to_dict())

@templates_bp.route('/<int:id>', methods=['DELETE'])
def delete_template(id):
    """Delete a template."""
    template = Template.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})

@templates_bp.route('/<int:id>/preview', methods=['POST'])
def preview_template(id):
    """Preview template with sample data."""
    template = Template.query.get_or_404(id)
    data = request.get_json()
    sample_data = data.get('sample_data', {})

    # Replace variables in subject and body
    subject = template.subject
    body = template.body

    for key, value in sample_data.items():
        placeholder = '{{' + key + '}}'
        cleaned = clean_company_name(str(value)) if key == 'company' else str(value)
        subject = subject.replace(placeholder, cleaned)
        body = body.replace(placeholder, cleaned)

    return jsonify({
        'subject': subject,
        'body': body,
        'variables': template.get_variables()
    })
