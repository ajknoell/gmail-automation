import threading
import time
from datetime import datetime, timedelta


class SequenceScheduler:
    """Background poller that checks for campaign steps ready to execute.

    Runs every N minutes. For each campaign in 'sequence_active' status,
    checks if any recipient is due for their next step based on delay_days.
    """
    _thread = None

    @classmethod
    def check_due_steps(cls):
        """Find steps with due recipients and trigger sending."""
        from app import db
        from app.models import Campaign, EmailLog
        from app.models.campaign_step import CampaignStep
        from app.models.step_recipient import StepRecipient

        now = datetime.utcnow()

        campaigns = Campaign.query.filter(
            Campaign.status == 'sequence_active'
        ).all()

        results = {'campaigns_checked': 0, 'steps_triggered': 0, 'recipients_queued': 0}

        for campaign in campaigns:
            results['campaigns_checked'] += 1

            steps = (
                CampaignStep.query
                .filter_by(campaign_id=campaign.id)
                .filter(CampaignStep.position > 1)
                .filter(CampaignStep.status.in_(['ready', 'generating']))
                .order_by(CampaignStep.position)
                .all()
            )

            for step in steps:
                # Find all steps at previous position (supports A/B tests with multiple steps at same position)
                prev_steps = (
                    CampaignStep.query
                    .filter_by(campaign_id=campaign.id, position=step.position - 1)
                    .all()
                )
                if not prev_steps:
                    continue

                # At least one previous step must be completed or running
                if not any(ps.status in ('completed', 'running') for ps in prev_steps):
                    continue

                cutoff = now - timedelta(minutes=step.effective_delay_minutes)

                # Find recipients from ANY previous step at that position sent before cutoff
                prev_step_ids = [ps.id for ps in prev_steps]
                prev_sent = (
                    StepRecipient.query
                    .filter(StepRecipient.step_id.in_(prev_step_ids))
                    .filter_by(status='sent')
                    .filter(StepRecipient.sent_at <= cutoff)
                    .all()
                )

                due_sr_ids = []
                for prev_sr in prev_sent:
                    # Get corresponding StepRecipient for current step
                    current_sr = StepRecipient.query.filter_by(
                        step_id=step.id,
                        recipient_id=prev_sr.recipient_id,
                    ).first()

                    if not current_sr:
                        continue

                    # Already processed?
                    if current_sr.status in ('sent', 'failed', 'skipped'):
                        continue

                    # Check: has this recipient replied or bounced?
                    has_reply_or_bounce = (
                        EmailLog.query
                        .filter_by(campaign_id=campaign.id, recipient_id=prev_sr.recipient_id)
                        .filter(
                            db.or_(
                                EmailLog.replied_at.isnot(None),
                                EmailLog.bounced_at.isnot(None),
                            )
                        )
                        .first()
                    )

                    if has_reply_or_bounce:
                        current_sr.status = 'skipped'
                        current_sr.skip_reason = 'replied' if has_reply_or_bounce.replied_at else 'bounced'
                        step.skipped_count = (step.skipped_count or 0) + 1
                        continue

                    # For auto_send steps: auto-approve if content is ready
                    if step.auto_send and current_sr.personalized_body and current_sr.status == 'ready':
                        current_sr.approved = True
                        current_sr.status = 'approved'

                    # Only send approved recipients
                    if current_sr.approved and current_sr.status in ('ready', 'approved') and current_sr.personalized_body:
                        due_sr_ids.append(current_sr.id)

                db.session.commit()

                if due_sr_ids:
                    from app.services.step_runner import StepRunner
                    StepRunner.start(
                        campaign.id, step.id, due_sr_ids,
                        campaign.delay_seconds, campaign.gmail_account_id,
                    )
                    results['steps_triggered'] += 1
                    results['recipients_queued'] += len(due_sr_ids)

        return results

    @classmethod
    def start_background_polling(cls, app, interval=300):
        """Start a daemon thread that checks for due steps periodically."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        cls.check_due_steps()
                    except Exception as e:
                        app.logger.error(f'Sequence scheduler error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Sequence scheduler started (interval={interval}s)')
