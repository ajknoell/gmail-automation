"""
Signal Engine — orchestrates all signal collectors, runs background
polling, and coordinates signal collection across workspaces.
"""
import threading
import time
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class SignalEngine:
    """Orchestrates signal collection across all sources and workspaces."""

    _thread = None

    @classmethod
    def collect_for_workspace(cls, workspace_id):
        """Run all active signal sources for a workspace."""
        from app import db
        from app.models.signal_source import SignalSource
        from app.models.contact import Contact
        from app.services.signals import get_collector
        from app.services.profile_service import ProfileService

        sources = SignalSource.query.filter_by(
            workspace_id=workspace_id,
            is_active=True,
        ).all()

        total_signals = 0

        for source in sources:
            collector = get_collector(source.source_type)
            if not collector:
                logger.warning(f'No collector registered for source type: {source.source_type}')
                continue

            try:
                # Get contacts with relevant data for this source type
                contacts_query = Contact.query.filter(
                    Contact.workspace_id == workspace_id,
                    Contact.status.notin_(['lost']),
                )

                # Website collector needs contacts with websites
                if source.source_type == 'website':
                    contacts_query = contacts_query.filter(
                        Contact.website.isnot(None),
                        Contact.website != '',
                    )
                # Job and news collectors need contacts with company names
                elif source.source_type in ('job_posting', 'news'):
                    contacts_query = contacts_query.filter(
                        Contact.company.isnot(None),
                        Contact.company != '',
                    )

                contacts = contacts_query.limit(50).all()
                config = source.get_config()

                for contact in contacts:
                    try:
                        new_signals = collector.collect(contact, workspace_id, config)
                        for signal in new_signals:
                            # Score relevance against business profile
                            signal.relevance_score = ProfileService.score_relevance(
                                signal, workspace_id
                            )
                            db.session.add(signal)
                            total_signals += 1
                        time.sleep(2)  # Rate limiting
                    except Exception as e:
                        logger.error(f'Signal collection failed for contact {contact.id} '
                                     f'with {source.source_type}: {e}')

                source.last_checked_at = datetime.utcnow()
                source.last_error = None
                db.session.commit()

            except Exception as e:
                source.last_error = str(e)[:500]
                db.session.commit()
                logger.error(f'Signal source {source.name} ({source.source_type}) failed: {e}')

        return total_signals

    @classmethod
    def check_all_due(cls):
        """Check all workspaces for signal sources that are due."""
        from app.models.workspace import Workspace
        from app.models.signal_source import SignalSource
        from datetime import timedelta

        workspaces = Workspace.query.all()
        total = 0

        for ws in workspaces:
            # Get sources due for checking
            sources = SignalSource.query.filter_by(
                workspace_id=ws.id,
                is_active=True,
            ).all()

            now = datetime.utcnow()
            any_due = False

            for source in sources:
                if source.last_checked_at:
                    next_check = source.last_checked_at + timedelta(hours=source.check_interval_hours)
                    if now < next_check:
                        continue
                any_due = True
                break

            if any_due:
                count = cls.collect_for_workspace(ws.id)
                total += count
                if count > 0:
                    logger.info(f'Signal engine found {count} new signals for workspace {ws.id}')

        return total

    @classmethod
    def start_background_polling(cls, app, interval=3600):
        """Start a daemon thread for periodic signal collection."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        count = cls.check_all_due()
                        if count > 0:
                            app.logger.info(f'Signal engine collected {count} new signals')
                    except Exception as e:
                        app.logger.error(f'Signal engine error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Signal engine started (interval={interval}s)')
