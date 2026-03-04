"""
Report routes — structured reports for Cowork consumption.
"""
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g

from app.services.report_service import ReportService

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/weekly-deal-flow', methods=['GET'])
def weekly_deal_flow() -> tuple:
    """Generate weekly deal flow report.

    Query params:
        week: ISO week string (e.g., '2024-W09'). Defaults to current week.
        start: ISO date for custom range start
        end: ISO date for custom range end
    """
    start_date = None
    end_date = None

    # Parse week parameter (ISO week format)
    week_str = request.args.get('week')
    if week_str:
        try:
            # Parse ISO week: "2024-W09" -> Monday of that week
            year, week_num = week_str.split('-W')
            start_date = datetime.strptime(f'{year}-W{week_num}-1', '%Y-W%W-%w')
            end_date = start_date + timedelta(days=7)
        except (ValueError, AttributeError):
            return jsonify({'error': 'Invalid week format. Use YYYY-WNN (e.g., 2024-W09)'}), 400

    # Or parse explicit date range
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if start_str:
        try:
            start_date = datetime.fromisoformat(start_str)
        except ValueError:
            return jsonify({'error': 'Invalid start date format. Use ISO format.'}), 400
    if end_str:
        try:
            end_date = datetime.fromisoformat(end_str)
        except ValueError:
            return jsonify({'error': 'Invalid end date format. Use ISO format.'}), 400

    report = ReportService.generate_weekly_report(
        workspace_id=g.workspace_id,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify(report)
