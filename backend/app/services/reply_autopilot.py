"""
Reply Autopilot — automatically handles routine replies based on
workspace-configured rules. Generates and sends appropriate responses
for positive, negative, and neutral replies, flagging sensitive topics
for human review.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReplyAutopilot:
    """Handles automatic reply processing based on workspace rules."""

    HUMAN_REVIEW_KEYWORDS_DEFAULT = [
        'price', 'cost', 'contract', 'legal', 'urgent', 'budget',
        'invoice', 'payment', 'proposal', 'quote', 'lawsuit', 'attorney',
        'discount', 'negotiate', 'terms', 'agreement',
    ]

    DEFAULT_CONFIG = {
        'enabled': False,
        'auto_respond_positive': False,
        'auto_respond_negative': False,
        'auto_respond_neutral': False,
        'auto_schedule_enabled': False,
        'human_review_keywords': HUMAN_REVIEW_KEYWORDS_DEFAULT,
        'positive_auto_action': 'meeting_followup',
        'negative_auto_action': 'graceful_close',
        'neutral_auto_action': 'acknowledge',
    }

    @classmethod
    def get_config(cls, workspace_id):
        """Load autopilot config from WorkspaceSettings."""
        from app.models.settings import WorkspaceSettings

        raw = WorkspaceSettings.get(workspace_id, 'reply_autopilot_config')
        if raw:
            try:
                config = json.loads(raw)
                # Merge with defaults for any missing keys
                merged = dict(cls.DEFAULT_CONFIG)
                merged.update(config)
                return merged
            except (json.JSONDecodeError, TypeError):
                pass
        return dict(cls.DEFAULT_CONFIG)

    @classmethod
    def save_config(cls, workspace_id, config):
        """Save autopilot config to WorkspaceSettings."""
        from app.models.settings import WorkspaceSettings
        WorkspaceSettings.set(workspace_id, 'reply_autopilot_config', json.dumps(config))

    @classmethod
    def process_reply(cls, reply_msg, email_log, workspace_id):
        """
        Main entry point: decide whether to auto-respond or flag for review.

        Called from ReplyChecker after sentiment classification.
        Non-blocking — exceptions should be caught by caller.
        """
        from app import db

        config = cls.get_config(workspace_id)
        if not config.get('enabled'):
            return  # Autopilot off

        sentiment = reply_msg.sentiment
        if not sentiment:
            return  # Can't auto-respond without classification

        # Check for human review keywords
        review_keywords = config.get('human_review_keywords', cls.HUMAN_REVIEW_KEYWORDS_DEFAULT)
        body_lower = (reply_msg.body_text or '').lower()
        flagged_keywords = [kw for kw in review_keywords if kw.lower() in body_lower]

        if flagged_keywords:
            reply_msg.flagged_for_review = True
            reply_msg.flag_reason = f"Contains keywords: {', '.join(flagged_keywords[:5])}"
            db.session.commit()
            logger.info(f'Reply {reply_msg.id} flagged for review: {reply_msg.flag_reason}')
            return

        # Route by sentiment
        should_auto = False
        response_type = None

        if sentiment == 'positive' and config.get('auto_respond_positive'):
            should_auto = True
            response_type = config.get('positive_auto_action', 'meeting_followup')
        elif sentiment == 'negative' and config.get('auto_respond_negative'):
            should_auto = True
            response_type = config.get('negative_auto_action', 'graceful_close')
        elif sentiment == 'neutral' and config.get('auto_respond_neutral'):
            should_auto = True
            response_type = config.get('neutral_auto_action', 'acknowledge')

        if not should_auto:
            return

        # Generate and send
        try:
            cls._auto_generate_and_send(reply_msg, email_log, workspace_id, response_type, config)
        except Exception as e:
            logger.error(f'Auto-response failed for reply {reply_msg.id}: {e}')
            reply_msg.flagged_for_review = True
            reply_msg.flag_reason = f'Auto-response error: {str(e)[:150]}'
            db.session.commit()

    @classmethod
    def _auto_generate_and_send(cls, reply_msg, email_log, workspace_id, response_type, config):
        """Generate response via Claude and send via Gmail."""
        from app import db
        from app.models.settings import Settings, WorkspaceSettings
        from app.services.claude_service import ClaudeService
        from app.services.gmail_service import GmailService

        # Get API key
        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            raise ValueError('No Anthropic API key configured')

        claude = ClaudeService(api_key)

        # Get contact info
        contact_name = reply_msg.from_name or ''
        contact_email = reply_msg.from_email or ''
        company = ''

        # Try to get company from contact record
        try:
            from app.models.contact import Contact
            contact = Contact.query.filter_by(
                email=contact_email,
                workspace_id=workspace_id,
            ).first()
            if contact:
                company = contact.company or ''
                if not contact_name:
                    contact_name = contact.name or ''
        except Exception:
            pass

        # Get writing style
        writing_style = None
        raw_style = WorkspaceSettings.get(workspace_id, 'writing_style')
        if raw_style:
            try:
                writing_style = json.loads(raw_style)
            except Exception:
                pass

        # Generate response based on type
        subject = None
        body = None

        if response_type == 'meeting_followup':
            # Get calendar availability if enabled
            availability_text = ''
            if config.get('auto_schedule_enabled'):
                try:
                    from app.services.calendar_service import CalendarService
                    cal = CalendarService(account_id=email_log.gmail_account_id)
                    slots = cal.get_available_slots(days_ahead=5)
                    if slots:
                        availability_text = '\n'.join([s['display'] for s in slots[:4]])
                except Exception as e:
                    logger.warning(f'Calendar availability error: {e}')

            result = claude.generate_meeting_followup(
                contact_name=contact_name,
                contact_email=contact_email,
                company=company,
                original_body=email_log.body or '',
                reply_body=reply_msg.body_text or '',
                availability=availability_text,
                writing_style=writing_style,
            )
            subject = result.get('subject', f'Re: {email_log.subject}')
            body = result.get('body', '')

        elif response_type == 'graceful_close':
            result = claude.generate_rebuttal(
                contact_name=contact_name,
                contact_email=contact_email,
                company=company,
                original_body=email_log.body or '',
                reply_body=reply_msg.body_text or '',
                writing_style=writing_style,
            )
            subject = result.get('subject', f'Re: {email_log.subject}')
            body = result.get('body', '')

        elif response_type == 'acknowledge':
            # Simple acknowledgment
            result = claude.generate_rebuttal(
                contact_name=contact_name,
                contact_email=contact_email,
                company=company,
                original_body=email_log.body or '',
                reply_body=reply_msg.body_text or '',
                writing_style=writing_style,
            )
            subject = result.get('subject', f'Re: {email_log.subject}')
            body = result.get('body', '')

        if not body:
            raise ValueError(f'Empty response generated for type {response_type}')

        # Send via Gmail
        gmail = GmailService(account_id=email_log.gmail_account_id)
        if not gmail.connect():
            raise ValueError('Could not connect to Gmail')

        gmail.send_reply(
            thread_id=email_log.gmail_thread_id,
            message_id=reply_msg.gmail_message_id,
            to=contact_email,
            subject=subject,
            body=body,
        )

        # Update reply message
        reply_msg.auto_responded = True
        reply_msg.auto_response_type = response_type
        reply_msg.ai_response_subject = subject
        reply_msg.ai_response_body = body
        reply_msg.response_sent_at = datetime.utcnow()
        db.session.commit()

        logger.info(f'Auto-responded to reply {reply_msg.id} with {response_type}')

        # Auto-advance contact status for positive replies
        if reply_msg.sentiment == 'positive':
            try:
                from app.models.contact import Contact
                contact = Contact.query.filter_by(
                    email=contact_email,
                    workspace_id=workspace_id,
                ).first()
                if contact and contact.status in ('new', 'contacted', 'replied'):
                    contact.status = 'interested'
                    db.session.commit()
            except Exception:
                pass
