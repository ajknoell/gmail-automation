"""
Insights API Routes

Endpoints for the email performance analysis feedback loop
and the website analysis learning loop.
"""

import json
from flask import Blueprint, request, jsonify, g
from app.models import Settings
from app.models.settings import WorkspaceSettings
from app.services.email_insights import EmailInsightsService
from app.services.website_insights import WebsiteInsightsService

insights_bp = Blueprint('insights', __name__)


@insights_bp.route('', methods=['GET'])
@insights_bp.route('/', methods=['GET'])
def get_insights():
    """
    GET /api/insights

    Returns current cached insights, analysis metadata, and live performance summary.
    Does NOT trigger a new analysis — that requires POST /analyze.
    """
    # Load cached insights
    insights = None
    insights_raw = WorkspaceSettings.get(g.workspace_id, 'learned_insights')
    if insights_raw:
        try:
            insights = json.loads(insights_raw)
        except Exception:
            pass

    # Load metadata
    metadata = None
    meta_raw = WorkspaceSettings.get(g.workspace_id, 'insights_metadata')
    if meta_raw:
        try:
            metadata = json.loads(meta_raw)
        except Exception:
            pass

    # Compute live summary stats (no Claude call needed)
    summary = {}
    api_key = Settings.get('anthropic_api_key')
    if api_key:
        try:
            service = EmailInsightsService(api_key)
            summary = service.get_performance_summary(g.workspace_id)
        except Exception:
            pass

    return jsonify({
        'insights': insights,
        'metadata': metadata,
        'summary': summary,
    })


@insights_bp.route('/analyze', methods=['POST'])
def trigger_analysis():
    """
    POST /api/insights/analyze

    Run a fresh Claude analysis of email performance.
    Returns the new insights or an insufficient_data status.
    """
    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    service = EmailInsightsService(api_key)
    result = service.analyze_performance(g.workspace_id)

    return jsonify(result)


@insights_bp.route('/email-scores', methods=['GET'])
def get_email_scores():
    """
    GET /api/insights/email-scores

    Returns per-email performance scores for the dashboard table.
    """
    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    service = EmailInsightsService(api_key)
    scores = service.get_email_scores(g.workspace_id)
    return jsonify(scores)


# ── Website Analysis Insights ────────────────────────────────────────────


@insights_bp.route('/website-analysis', methods=['GET'])
def get_website_insights():
    """
    GET /api/insights/website-analysis

    Returns cached website analysis insights and metadata.
    Does NOT trigger a new analysis — that requires POST /website-analysis/analyze.
    """
    insights = None
    raw = WorkspaceSettings.get(g.workspace_id, 'learned_website_insights')
    if raw:
        try:
            insights = json.loads(raw)
        except Exception:
            pass

    metadata = None
    meta_raw = WorkspaceSettings.get(g.workspace_id, 'website_insights_metadata')
    if meta_raw:
        try:
            metadata = json.loads(meta_raw)
        except Exception:
            pass

    return jsonify({
        'insights': insights,
        'metadata': metadata,
    })


@insights_bp.route('/website-analysis/analyze', methods=['POST'])
def trigger_website_analysis():
    """
    POST /api/insights/website-analysis/analyze

    Run a fresh Claude analysis comparing website observations
    that drove engagement vs those that didn't. Extracts patterns
    to improve future website analyses.
    """
    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    service = WebsiteInsightsService(api_key)
    result = service.analyze_performance(g.workspace_id)

    return jsonify(result)
