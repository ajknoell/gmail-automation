import threading
import time
from typing import List
from datetime import datetime


class StepRunner:
    """Sends emails for a campaign step, respecting thread continuity.

    For step 1, sends new emails (like CampaignRunner).
    For steps > 1, sends replies in the same Gmail thread.
    """
    _instances = {}  # key: (campaign_id, step_id)
    _lock = threading.Lock()

    @classmethod
    def start(cls, campaign_id, step_id, step_recipient_ids, delay_seconds, account_id):
        """Start sending a step in a background thread."""
        key = (campaign_id, step_id)
        with cls._lock:
            if key in cls._instances:
                return False
            cls._instances[key] = True

        thread = threading.Thread(
            target=cls._run_step,
            args=(campaign_id, step_id, step_recipient_ids, delay_seconds, account_id),
            daemon=True,
        )
        thread.start()
        return True

    @classmethod
    def _run_step(cls, campaign_id, step_id, step_recipient_ids, delay_seconds, account_id):
        from app import db, create_app
        from app.models import Campaign, EmailLog, Recipient
        from app.models.campaign_step import CampaignStep
        from app.models.step_recipient import StepRecipient
        from app.services.gmail_service import GmailService
        from app.services.tracking_service import TrackingService
        import json as json_module

        app = create_app()
        with app.app_context():
            base_url = app.config.get('TRACKING_BASE_URL', 'http://localhost:5001')
            gmail = GmailService(account_id=account_id)
            if not gmail.connect():
                app.logger.error(f'StepRunner: Gmail connect failed for step {step_id}')
                return

            step = CampaignStep.query.get(step_id)
            campaign = Campaign.query.get(campaign_id)
            if not step or not campaign:
                return

            step.status = 'running'
            step.started_at = datetime.utcnow()
            db.session.commit()

            for sr_id in step_recipient_ids:
                sr = StepRecipient.query.get(sr_id)
                if not sr or sr.status not in ('ready', 'approved'):
                    continue

                recipient = Recipient.query.get(sr.recipient_id)
                if not recipient:
                    continue

                try:
                    subject = sr.personalized_subject or 'Follow-up'
                    body = sr.personalized_body or ''

                    if not body:
                        sr.status = 'skipped'
                        sr.skip_reason = 'no_content'
                        step.skipped_count = (step.skipped_count or 0) + 1
                        db.session.commit()
                        continue

                    tracking_id = TrackingService.generate_tracking_id()

                    if step.position > 1:
                        # Find original email log to get thread_id for reply
                        original_log = (
                            EmailLog.query
                            .filter_by(campaign_id=campaign_id, recipient_id=recipient.id)
                            .filter(EmailLog.gmail_thread_id.isnot(None))
                            .order_by(EmailLog.created_at.asc())
                            .first()
                        )
                        if original_log and original_log.gmail_thread_id:
                            result = gmail.send_reply(
                                thread_id=original_log.gmail_thread_id,
                                message_id=original_log.gmail_message_id,
                                to=recipient.email,
                                subject=subject,
                                body=body,
                                html=True,
                            )
                        else:
                            # Fallback: send as new email if no thread found
                            result = gmail.send_email(
                                to=recipient.email,
                                subject=subject,
                                body=body,
                                html=True,
                                tracking_id=tracking_id,
                                base_url=base_url,
                            )
                    else:
                        result = gmail.send_email(
                            to=recipient.email,
                            subject=subject,
                            body=body,
                            html=True,
                            tracking_id=tracking_id,
                            base_url=base_url,
                        )

                    if result.get('success'):
                        sr.status = 'sent'
                        sr.sent_at = datetime.utcnow()
                        step.sent_count = (step.sent_count or 0) + 1

                        log = EmailLog(
                            workspace_id=campaign.workspace_id,
                            recipient_id=recipient.id,
                            campaign_id=campaign_id,
                            step_id=step_id,
                            gmail_message_id=result.get('message_id'),
                            gmail_thread_id=result.get('thread_id'),
                            gmail_account_id=account_id,
                            recipient_email=recipient.email,
                            tracking_id=tracking_id,
                            subject=subject,
                            body=body,
                            status='sent',
                            is_html=True,
                            link_map=json_module.dumps(result.get('link_map') or {}),
                        )
                        db.session.add(log)
                        db.session.flush()
                        sr.email_log_id = log.id

                        # Update contact directory
                        from app.models.contact import Contact
                        Contact.upsert_from_send(
                            email=recipient.email,
                            name=recipient.name,
                            company=recipient.company,
                            workspace_id=campaign.workspace_id,
                        )
                    else:
                        sr.status = 'failed'
                        sr.error_message = result.get('error', 'Unknown error')
                        step.failed_count = (step.failed_count or 0) + 1

                    db.session.commit()

                except Exception as e:
                    sr.status = 'failed'
                    sr.error_message = str(e)
                    step.failed_count = (step.failed_count or 0) + 1
                    db.session.commit()

                if delay_seconds and delay_seconds > 0:
                    time.sleep(delay_seconds)

            # Mark step completed
            step.status = 'completed'
            step.completed_at = datetime.utcnow()
            db.session.commit()

            # Check if all steps are done
            cls._check_campaign_completion(campaign_id)

        # Cleanup
        key = (campaign_id, step_id)
        with cls._lock:
            cls._instances.pop(key, None)

    @classmethod
    def _check_campaign_completion(cls, campaign_id):
        """Check if all steps are completed and mark campaign as completed."""
        from app import db
        from app.models import Campaign
        from app.models.campaign_step import CampaignStep

        campaign = Campaign.query.get(campaign_id)
        if not campaign or campaign.status != 'sequence_active':
            return

        incomplete = CampaignStep.query.filter_by(campaign_id=campaign_id).filter(
            CampaignStep.status.notin_(['completed', 'cancelled'])
        ).count()

        if incomplete == 0:
            campaign.status = 'completed'
            campaign.completed_at = datetime.utcnow()
            db.session.commit()

    @classmethod
    def is_running(cls, campaign_id, step_id):
        key = (campaign_id, step_id)
        with cls._lock:
            return key in cls._instances
