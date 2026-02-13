from flask import Blueprint, request, jsonify, g
from app import db
from app.models.workspace import Workspace
import re

workspaces_bp = Blueprint('workspaces', __name__)


def _slugify(name):
    """Convert name to URL-friendly slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'workspace'


@workspaces_bp.route('', methods=['GET'])
@workspaces_bp.route('/', methods=['GET'])
def list_workspaces():
    workspaces = Workspace.query.order_by(Workspace.is_default.desc(), Workspace.name).all()
    return jsonify([ws.to_dict() for ws in workspaces])


@workspaces_bp.route('', methods=['POST'])
@workspaces_bp.route('/', methods=['POST'])
def create_workspace():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    color = data.get('color', '#3B82F6')

    # Generate unique slug
    base_slug = _slugify(name)
    slug = base_slug
    counter = 1
    while Workspace.query.filter_by(slug=slug).first():
        slug = f'{base_slug}-{counter}'
        counter += 1

    ws = Workspace(name=name, slug=slug, color=color)
    db.session.add(ws)
    db.session.commit()

    return jsonify(ws.to_dict()), 201


@workspaces_bp.route('/<int:ws_id>', methods=['PUT'])
def update_workspace(ws_id):
    ws = Workspace.query.get_or_404(ws_id)
    data = request.get_json()

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        ws.name = name

    if 'color' in data:
        ws.color = data['color']

    db.session.commit()
    return jsonify(ws.to_dict())


@workspaces_bp.route('/<int:ws_id>', methods=['DELETE'])
def delete_workspace(ws_id):
    ws = Workspace.query.get_or_404(ws_id)

    if ws.is_default:
        return jsonify({'error': 'Cannot delete the default workspace'}), 400

    # Delete all workspace data
    from app.models import Contact, Campaign, Template, Tag, EmailLog
    from app.models.tag import contact_tags
    from sqlalchemy import text

    # Remove contact_tags associations for contacts in this workspace
    contact_ids = [c.id for c in Contact.query.filter_by(workspace_id=ws_id).all()]
    if contact_ids:
        db.session.execute(
            contact_tags.delete().where(contact_tags.c.contact_id.in_(contact_ids))
        )

    # Delete workspace data
    EmailLog.query.filter_by(workspace_id=ws_id).delete()
    Campaign.query.filter_by(workspace_id=ws_id).delete()
    Template.query.filter_by(workspace_id=ws_id).delete()
    Contact.query.filter_by(workspace_id=ws_id).delete()
    Tag.query.filter_by(workspace_id=ws_id).delete()

    # Delete workspace settings
    from app.models.settings import WorkspaceSettings
    WorkspaceSettings.query.filter_by(workspace_id=ws_id).delete()

    db.session.delete(ws)
    db.session.commit()

    return jsonify({'success': True})
