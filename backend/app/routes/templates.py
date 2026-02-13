from flask import Blueprint, request, jsonify, current_app, g
from app import db
from app.models import Template
from app.services.claude_service import ClaudeService, clean_company_name
import re
import os

templates_bp = Blueprint('templates', __name__)

def extract_variables(text):
    """Extract {{variable}} placeholders from text."""
    pattern = r'\{\{(\w+)\}\}'
    return list(set(re.findall(pattern, text)))

@templates_bp.route('', methods=['GET'])
def list_templates():
    """List all templates."""
    templates = Template.query.filter_by(workspace_id=g.workspace_id).order_by(Template.updated_at.desc()).all()
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
        workspace_id=g.workspace_id,
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


@templates_bp.route('/generate', methods=['POST'])
def generate_template():
    """Generate a template using Claude AI."""
    data = request.get_json()

    purpose = data.get('purpose')
    if not purpose:
        return jsonify({'error': 'Purpose is required'}), 400

    # Get API key from settings
    from app.models import Settings
    api_key = Settings.get('anthropic_api_key')

    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured. Please add it in Settings.'}), 400

    try:
        claude = ClaudeService(api_key)
        result = claude.generate_template(
            purpose=purpose,
            target_audience=data.get('target_audience'),
            tone=data.get('tone', 'professional but casual'),
            key_points=data.get('key_points'),
            call_to_action=data.get('call_to_action'),
            length=data.get('length', 'short')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@templates_bp.route('/refine', methods=['POST'])
def refine_template():
    """Refine an AI-generated template based on user feedback."""
    data = request.get_json()

    feedback = data.get('feedback')
    current_subject = data.get('subject')
    current_body = data.get('body')
    current_name = data.get('name', 'Template')

    if not feedback:
        return jsonify({'error': 'Feedback is required'}), 400
    if not current_subject or not current_body:
        return jsonify({'error': 'Current template subject and body are required'}), 400

    # Get API key from settings
    from app.models import Settings
    api_key = Settings.get('anthropic_api_key')

    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured. Please add it in Settings.'}), 400

    try:
        claude = ClaudeService(api_key)
        result = claude.refine_template(
            current_subject=current_subject,
            current_body=current_body,
            current_name=current_name,
            feedback=feedback,
            original_purpose=data.get('purpose')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
