"""
Agent routes — manage AI-powered agent tasks (research, discovery, competitive intel).
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.agent_task import AgentTask, AGENT_TYPES
import threading

agents_bp = Blueprint('agents', __name__)


@agents_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List agent tasks with optional filters."""
    query = AgentTask.query.filter_by(workspace_id=g.workspace_id)

    agent_type = request.args.get('agent_type')
    if agent_type and agent_type in AGENT_TYPES:
        query = query.filter_by(agent_type=agent_type)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    tasks = query.order_by(AgentTask.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'tasks': [t.to_dict() for t in tasks.items],
        'total': tasks.total,
        'page': tasks.page,
        'pages': tasks.pages,
    })


@agents_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a single task with full details."""
    task = AgentTask.query.filter_by(
        id=task_id, workspace_id=g.workspace_id
    ).first_or_404()
    return jsonify(task.to_dict())


@agents_bp.route('/research', methods=['POST'])
def start_research():
    """Start a prospect research agent for a lead."""
    from flask import current_app
    from app.models.lead import Lead

    data = request.json or {}
    lead_id = data.get('lead_id')

    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400

    lead = Lead.query.filter_by(
        id=lead_id, workspace_id=g.workspace_id
    ).first()
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    if not lead.website:
        return jsonify({'error': 'Lead has no website URL for research'}), 400

    # Create task record
    task = AgentTask(
        workspace_id=g.workspace_id,
        agent_type='prospect_research',
        status='pending',
        lead_id=lead_id,
    )
    task.set_config({
        'lead_id': lead_id,
        'lead_name': lead.name,
        'website': lead.website,
    })
    db.session.add(task)
    db.session.commit()

    # Run in background thread
    app = current_app._get_current_object()
    from app.services.agents.prospect_research import run_prospect_research

    thread = threading.Thread(
        target=run_prospect_research,
        args=(app, task.id, lead_id),
        daemon=True,
    )
    thread.start()

    return jsonify(task.to_dict()), 202


@agents_bp.route('/discover', methods=['POST'])
def start_discovery():
    """Start a lead discovery agent."""
    from flask import current_app

    data = request.json or {}
    industry = data.get('industry', '').strip()
    location = data.get('location', '').strip()
    criteria = data.get('criteria', '').strip()

    if not industry:
        return jsonify({'error': 'industry is required'}), 400

    # Create task record
    task = AgentTask(
        workspace_id=g.workspace_id,
        agent_type='lead_discovery',
        status='pending',
    )
    task.set_config({
        'industry': industry,
        'location': location,
        'criteria': criteria,
    })
    db.session.add(task)
    db.session.commit()

    # Run in background thread
    app = current_app._get_current_object()
    from app.services.agents.lead_discovery import run_lead_discovery

    thread = threading.Thread(
        target=run_lead_discovery,
        args=(app, task.id),
        daemon=True,
    )
    thread.start()

    return jsonify(task.to_dict()), 202


@agents_bp.route('/competitive-intel', methods=['POST'])
def start_competitive_intel():
    """Start a competitive intelligence agent."""
    from flask import current_app

    data = request.json or {}
    competitor_url = data.get('competitor_url', '').strip()
    competitor_name = data.get('competitor_name', '').strip()

    if not competitor_url:
        return jsonify({'error': 'competitor_url is required'}), 400

    # Create task record
    task = AgentTask(
        workspace_id=g.workspace_id,
        agent_type='competitive_intel',
        status='pending',
    )
    task.set_config({
        'competitor_url': competitor_url,
        'competitor_name': competitor_name,
    })
    db.session.add(task)
    db.session.commit()

    # Run in background thread
    app = current_app._get_current_object()
    from app.services.agents.competitive_intel import run_competitive_intel

    thread = threading.Thread(
        target=run_competitive_intel,
        args=(app, task.id),
        daemon=True,
    )
    thread.start()

    return jsonify(task.to_dict()), 202


@agents_bp.route('/tasks/<int:task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """Cancel a running task."""
    task = AgentTask.query.filter_by(
        id=task_id, workspace_id=g.workspace_id
    ).first_or_404()

    if task.status not in ('pending', 'running'):
        return jsonify({'error': f'Cannot cancel task in {task.status} status'}), 400

    task.status = 'cancelled'
    task.completed_at = __import__('datetime').datetime.utcnow()
    db.session.commit()

    return jsonify(task.to_dict())


@agents_bp.route('/stats', methods=['GET'])
def agent_stats():
    """Get agent usage stats for the workspace."""
    from sqlalchemy import func

    ws_id = g.workspace_id

    total = AgentTask.query.filter_by(workspace_id=ws_id).count()
    completed = AgentTask.query.filter_by(workspace_id=ws_id, status='completed').count()
    running = AgentTask.query.filter_by(workspace_id=ws_id, status='running').count()
    failed = AgentTask.query.filter_by(workspace_id=ws_id, status='failed').count()

    # Token usage
    token_stats = db.session.query(
        func.sum(AgentTask.input_tokens),
        func.sum(AgentTask.output_tokens),
        func.sum(AgentTask.firecrawl_pages_scraped),
    ).filter_by(workspace_id=ws_id).first()

    # By type
    by_type = db.session.query(
        AgentTask.agent_type, func.count(AgentTask.id)
    ).filter_by(workspace_id=ws_id).group_by(AgentTask.agent_type).all()

    return jsonify({
        'total': total,
        'completed': completed,
        'running': running,
        'failed': failed,
        'total_input_tokens': token_stats[0] or 0,
        'total_output_tokens': token_stats[1] or 0,
        'total_firecrawl_pages': token_stats[2] or 0,
        'by_type': {t: c for t, c in by_type},
    })
