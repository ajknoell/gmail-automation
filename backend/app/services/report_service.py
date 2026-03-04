"""
Report Service — generates structured reports for Cowork consumption.
Primary output: weekly deal flow report aggregated by thesis.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.acquisition_thesis import AcquisitionThesis
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.contact import Contact
from app.models.reply_message import ReplyMessage

logger = logging.getLogger(__name__)


class ReportService:
    """Generates structured reports for Cowork consumption."""

    @staticmethod
    def generate_weekly_report(
        workspace_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Generate weekly deal flow report aggregated by thesis.

        Args:
            workspace_id: Workspace context
            start_date: Report period start (default: 7 days ago)
            end_date: Report period end (default: now)

        Returns:
            Structured report dict designed for Cowork consumption.
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        theses = AcquisitionThesis.query.filter_by(
            workspace_id=workspace_id,
            status='active',
        ).all()

        thesis_summaries = []
        for thesis in theses:
            summary = _build_thesis_summary(workspace_id, thesis, start_date, end_date)
            thesis_summaries.append(summary)

        # Cross-thesis aggregate stats
        cross_stats = _build_cross_thesis_stats(workspace_id, start_date, end_date)

        return {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'generated_at': datetime.utcnow().isoformat(),
            'thesis_summaries': thesis_summaries,
            'cross_thesis_stats': cross_stats,
        }


def _build_thesis_summary(
    workspace_id: int,
    thesis: AcquisitionThesis,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Build deal flow summary for a single thesis.

    Args:
        workspace_id: Workspace context
        thesis: The thesis to report on
        start_date: Period start
        end_date: Period end

    Returns:
        Dict with thesis metrics and top targets.
    """
    from app.services.thesis_scorer import ThesisScorer

    # New leads discovered in period
    new_leads = Lead.query.filter(
        Lead.workspace_id == workspace_id,
        Lead.created_at >= start_date,
        Lead.created_at <= end_date,
    ).all()

    # Score all new leads against this thesis
    enriched_leads = [l for l in new_leads if l.status not in ('new', 'rejected')]
    scored = ThesisScorer.score_batch(enriched_leads, thesis) if enriched_leads else []
    meeting_criteria = [s for s in scored if s['score'] >= 60]

    # Top targets (highest scoring)
    top_targets = sorted(scored, key=lambda x: x['score'], reverse=True)[:10]
    top_target_dicts = []
    for t in top_targets:
        lead = Lead.query.get(t['lead_id'])
        if lead:
            top_target_dicts.append({
                'lead_id': lead.id,
                'name': lead.name,
                'location': lead.address,
                'employee_count': lead.employee_count,
                'years_in_operation': lead.years_in_operation,
                'review_volume': lead.total_review_volume or lead.review_count,
                'retirement_score': lead.retirement_score,
                'thesis_fit_score': t['score'],
                'status': lead.status,
                'owner_name': lead.owner_name or lead.decision_maker,
            })

    # Outreach stats for this period
    from app.models.email_log import EmailLog
    emails_sent = EmailLog.query.filter(
        EmailLog.workspace_id == workspace_id,
        EmailLog.created_at >= start_date,
        EmailLog.created_at <= end_date,
        EmailLog.status == 'sent',
    ).count()

    opens = EmailLog.query.filter(
        EmailLog.workspace_id == workspace_id,
        EmailLog.opened_at >= start_date,
        EmailLog.opened_at <= end_date,
    ).count()

    # Reply stats
    replies = ReplyMessage.query.filter(
        ReplyMessage.workspace_id == workspace_id,
        ReplyMessage.received_at >= start_date,
        ReplyMessage.received_at <= end_date,
    ).all()

    positive_replies = sum(1 for r in replies if r.sentiment == 'positive')

    # Pipeline movement (deal stage changes)
    stage_changes = []
    deals = Deal.query.filter(
        Deal.workspace_id == workspace_id,
        Deal.stage_changed_at >= start_date,
        Deal.stage_changed_at <= end_date,
    ).all()

    for deal in deals:
        stage_changes.append({
            'deal_id': deal.id,
            'deal_name': deal.name,
            'stage': deal.stage,
            'changed_at': deal.stage_changed_at.isoformat() if deal.stage_changed_at else None,
        })

    return {
        'thesis_id': thesis.id,
        'thesis_name': thesis.name,
        'vertical': thesis.vertical,
        'new_targets_discovered': len(new_leads),
        'targets_enriched': len(enriched_leads),
        'targets_meeting_criteria': len(meeting_criteria),
        'top_targets': top_target_dicts,
        'outreach_stats': {
            'emails_sent': emails_sent,
            'opens': opens,
            'replies': len(replies),
            'positive_replies': positive_replies,
        },
        'pipeline_movement': {
            'stage_changes': stage_changes,
        },
    }


def _build_cross_thesis_stats(
    workspace_id: int,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Build aggregate stats across all theses.

    Args:
        workspace_id: Workspace context
        start_date: Period start
        end_date: Period end

    Returns:
        Dict with cross-thesis aggregate metrics.
    """
    total_new = Lead.query.filter(
        Lead.workspace_id == workspace_id,
        Lead.created_at >= start_date,
        Lead.created_at <= end_date,
    ).count()

    from app.models.email_log import EmailLog
    total_sent = EmailLog.query.filter(
        EmailLog.workspace_id == workspace_id,
        EmailLog.created_at >= start_date,
        EmailLog.created_at <= end_date,
        EmailLog.status == 'sent',
    ).count()

    total_replies = ReplyMessage.query.filter(
        ReplyMessage.workspace_id == workspace_id,
        ReplyMessage.received_at >= start_date,
        ReplyMessage.received_at <= end_date,
    ).count()

    # Active deals and pipeline value
    active_stages = ['interested', 'contacted_broker', 'nda_signed',
                     'reviewing_financials', 'loi_submitted', 'under_contract', 'due_diligence']
    active_deals = Deal.query.filter(
        Deal.workspace_id == workspace_id,
        Deal.stage.in_(active_stages),
    ).all()

    pipeline_value = sum(d.asking_price or 0 for d in active_deals)

    return {
        'total_targets_discovered': total_new,
        'total_emails_sent': total_sent,
        'total_replies': total_replies,
        'active_deals': len(active_deals),
        'pipeline_value': pipeline_value,
    }
