import threading
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CampaignState:
    campaign_id: int
    account_id: Optional[int] = None
    thread: Optional[threading.Thread] = None
    pause_event: threading.Event = field(default_factory=threading.Event)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    progress: dict = field(default_factory=lambda: {'sent': 0, 'failed': 0, 'total': 0})

class CampaignRunner:
    _instances: Dict[int, CampaignState] = {}
    _lock = threading.Lock()

    @classmethod
    def start(cls, campaign_id: int, recipient_ids: List[int], delay: int, account_id: Optional[int] = None):
        """Start a campaign in background thread."""
        with cls._lock:
            if campaign_id in cls._instances:
                return False

            state = CampaignState(
                campaign_id=campaign_id,
                account_id=account_id,
                progress={'sent': 0, 'failed': 0, 'total': len(recipient_ids)}
            )
            state.pause_event.set()  # Start unpaused

            thread = threading.Thread(
                target=cls._run_campaign,
                args=(state, recipient_ids, delay),
                daemon=True
            )
            state.thread = thread
            cls._instances[campaign_id] = state
            thread.start()
            return True

    @staticmethod
    def _substitute_variables(text: str, recipient) -> str:
        """Replace {{variable}} placeholders with recipient data."""
        from app.services.claude_service import clean_company_name, resolve_recipient_fields
        import re

        custom = recipient.get_custom_fields() or {}
        name, company = resolve_recipient_fields(
            recipient.name, clean_company_name(recipient.company or ''),
            recipient.email, custom,
        )
        variables = {
            'name': name or 'there',
            'email': recipient.email or '',
            'company': company or '',
        }
        # Include custom fields
        if custom:
            variables.update(custom)

        def replace_var(match):
            key = match.group(1)
            return variables.get(key, match.group(0))

        return re.sub(r'\{\{(\w+)\}\}', replace_var, text)

    @classmethod
    def _run_campaign(cls, state: CampaignState, recipient_ids: List[int], delay: int):
        """Run the campaign - send emails one by one."""
        # Import here to avoid circular imports
        from app import db, create_app
        from app.models import Campaign, Recipient, EmailLog
        from app.services.gmail_service import GmailService
        from app.services.tracking_service import TrackingService
        import json as json_module

        app = create_app()
        with app.app_context():
            base_url = app.config.get('TRACKING_BASE_URL', 'http://localhost:5001')
            gmail = GmailService(account_id=state.account_id)
            if not gmail.connect():
                cls._finish_campaign(state.campaign_id, 'failed')
                return

            # Load campaign and its workspace_id once
            campaign_obj = Campaign.query.get(state.campaign_id)
            campaign_workspace_id = campaign_obj.workspace_id if campaign_obj else None
            template = campaign_obj.template if campaign_obj else None
            campaign_attachments = None
            if campaign_obj:
                att_list = campaign_obj.get_attachments()
                if att_list:
                    from app.routes.quick_send import _resolve_attachments
                    campaign_attachments = _resolve_attachments(att_list) or None

            for recipient_id in recipient_ids:
                # Check for cancellation
                if state.cancel_event.is_set():
                    break

                # Wait if paused
                state.pause_event.wait()

                # Get recipient
                recipient = Recipient.query.get(recipient_id)
                if not recipient:
                    continue

                # Send email: use personalized content if available,
                # otherwise fall back to template with variable substitution.
                # Skip recipients that have no content and no template fallback.
                try:
                    if recipient.personalized_subject:
                        subject = recipient.personalized_subject
                    elif template:
                        subject = cls._substitute_variables(template.subject, recipient)
                    else:
                        subject = 'No subject'

                    if recipient.personalized_body:
                        body = recipient.personalized_body
                    elif template:
                        body = cls._substitute_variables(template.body, recipient)
                    else:
                        # No content and no template — skip this recipient
                        recipient.status = 'skipped'
                        recipient.error_message = 'No personalized content generated and no template available'
                        state.progress['failed'] += 1

                        campaign = Campaign.query.get(state.campaign_id)
                        if campaign:
                            campaign.failed_count += 1
                        db.session.commit()
                        continue

                    tracking_id = TrackingService.generate_tracking_id()

                    result = gmail.send_email(
                        to=recipient.email,
                        subject=subject,
                        body=body,
                        html=True,
                        tracking_id=tracking_id,
                        base_url=base_url,
                        attachments=campaign_attachments,
                    )

                    if result.get('success'):
                        recipient.status = 'sent'
                        recipient.sent_at = datetime.utcnow()
                        state.progress['sent'] += 1

                        # Update campaign counts
                        campaign = Campaign.query.get(state.campaign_id)
                        if campaign:
                            campaign.sent_count += 1

                        # Log with tracking data
                        log = EmailLog(
                            workspace_id=campaign_workspace_id,
                            recipient_id=recipient.id,
                            campaign_id=state.campaign_id,
                            gmail_message_id=result.get('message_id'),
                            gmail_thread_id=result.get('thread_id'),
                            gmail_account_id=state.account_id,
                            recipient_email=recipient.email,
                            tracking_id=tracking_id,
                            subject=subject,
                            body=body,
                            status='sent',
                            is_html=True,
                            link_map=json_module.dumps(result.get('link_map') or {}),
                        )
                        db.session.add(log)
                        db.session.flush()  # Get log.id

                        # Link website analysis log to this email for learning
                        from app.models.website_analysis_log import WebsiteAnalysisLog
                        wa_log = (
                            WebsiteAnalysisLog.query
                            .filter_by(
                                workspace_id=campaign_workspace_id,
                                recipient_id=recipient.id,
                                email_log_id=None,
                            )
                            .order_by(WebsiteAnalysisLog.created_at.desc())
                            .first()
                        )
                        if wa_log:
                            wa_log.email_log_id = log.id

                        # Auto-add/update contact directory
                        from app.models.contact import Contact
                        Contact.upsert_from_send(
                            email=recipient.email,
                            name=recipient.name,
                            company=recipient.company,
                            workspace_id=campaign_workspace_id,
                        )
                    else:
                        recipient.status = 'failed'
                        recipient.error_message = result.get('error', 'Unknown error')
                        state.progress['failed'] += 1

                        campaign = Campaign.query.get(state.campaign_id)
                        if campaign:
                            campaign.failed_count += 1

                        log = EmailLog(
                            workspace_id=campaign_workspace_id,
                            recipient_id=recipient.id,
                            campaign_id=state.campaign_id,
                            recipient_email=recipient.email,
                            subject=subject,
                            status='failed',
                            error_details=result.get('error')
                        )
                        db.session.add(log)

                    db.session.commit()

                except Exception as e:
                    recipient.status = 'failed'
                    recipient.error_message = str(e)
                    state.progress['failed'] += 1
                    db.session.commit()

                # Delay between emails
                if delay > 0:
                    time.sleep(delay)

            # Mark campaign as completed
            status = 'cancelled' if state.cancel_event.is_set() else 'completed'
            cls._finish_campaign(state.campaign_id, status)

    @classmethod
    def _finish_campaign(cls, campaign_id: int, status: str):
        """Mark campaign as finished. If follow-up steps exist, enter sequence mode."""
        from app import create_app
        from app.models import Campaign

        app = create_app()
        with app.app_context():
            from app import db
            from app.models.campaign_step import CampaignStep

            campaign = Campaign.query.get(campaign_id)
            if campaign:
                # Check if there are follow-up steps ready
                if status == 'completed':
                    next_steps = CampaignStep.query.filter(
                        CampaignStep.campaign_id == campaign_id,
                        CampaignStep.position > 1,
                        CampaignStep.status.in_(['ready', 'draft']),
                    ).count()
                    if next_steps > 0:
                        campaign.status = 'sequence_active'
                    else:
                        campaign.status = status
                        campaign.completed_at = datetime.utcnow()
                else:
                    campaign.status = status
                    campaign.completed_at = datetime.utcnow()
                db.session.commit()

        # Clean up state
        with cls._lock:
            if campaign_id in cls._instances:
                del cls._instances[campaign_id]

    @classmethod
    def pause(cls, campaign_id: int) -> bool:
        """Pause a running campaign."""
        with cls._lock:
            if campaign_id in cls._instances:
                cls._instances[campaign_id].pause_event.clear()
                return True
            return False

    @classmethod
    def resume(cls, campaign_id: int) -> bool:
        """Resume a paused campaign."""
        with cls._lock:
            if campaign_id in cls._instances:
                cls._instances[campaign_id].pause_event.set()
                return True
            return False

    @classmethod
    def cancel(cls, campaign_id: int) -> bool:
        """Cancel a running campaign."""
        with cls._lock:
            if campaign_id in cls._instances:
                state = cls._instances[campaign_id]
                state.cancel_event.set()
                state.pause_event.set()  # Unpause to allow thread to exit
                return True
            return False

    @classmethod
    def get_state(cls, campaign_id: int) -> Optional[CampaignState]:
        """Get current state of a campaign."""
        with cls._lock:
            return cls._instances.get(campaign_id)

    @classmethod
    def get_progress(cls, campaign_id: int) -> Optional[dict]:
        """Get progress of a campaign."""
        with cls._lock:
            state = cls._instances.get(campaign_id)
            if state:
                return state.progress.copy()
            return None
