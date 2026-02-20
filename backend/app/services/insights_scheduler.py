"""
Insights Auto-Refresh Scheduler

Background daemon that periodically checks whether workspaces have
accumulated enough new email engagement data to warrant re-running
the learning loop analysis. Follows the same daemon thread pattern
used by ReplyChecker, SequenceScheduler, etc.
"""

import json
import threading
import time


class InsightsScheduler:
    _thread = None

    # Minimum new data since last analysis to trigger a re-run
    MIN_NEW_EMAILS_FOR_REFRESH = 25
    MIN_NEW_ANALYSES_FOR_REFRESH = 10

    @classmethod
    def check_and_refresh(cls):
        """Check all workspaces and refresh insights where enough new data exists."""
        from app.models.workspace import Workspace
        from app.models import Settings

        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return

        workspaces = Workspace.query.all()
        for ws in workspaces:
            try:
                cls._check_email_insights(ws.id, api_key)
            except Exception as e:
                print(f'Insights scheduler: email insights error for workspace {ws.id}: {e}')

            try:
                cls._check_website_insights(ws.id, api_key)
            except Exception as e:
                print(f'Insights scheduler: website insights error for workspace {ws.id}: {e}')

    @classmethod
    def _check_email_insights(cls, workspace_id, api_key):
        """Refresh email insights if enough new data since last analysis."""
        from app.models.settings import WorkspaceSettings
        from app.models.email_log import EmailLog
        from app.services.email_insights import EmailInsightsService

        meta_raw = WorkspaceSettings.get(workspace_id, 'insights_metadata')
        last_count = 0
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                last_count = meta.get('email_count', 0)
            except Exception:
                pass

        current_count = EmailLog.query.filter_by(
            workspace_id=workspace_id, status='sent'
        ).count()

        new_emails = current_count - last_count
        if new_emails >= cls.MIN_NEW_EMAILS_FOR_REFRESH:
            service = EmailInsightsService(api_key)
            service.analyze_performance(workspace_id)

    @classmethod
    def _check_website_insights(cls, workspace_id, api_key):
        """Refresh website insights if enough new data since last analysis."""
        from app.models.settings import WorkspaceSettings
        from app.models.website_analysis_log import WebsiteAnalysisLog
        from app.services.website_insights import WebsiteInsightsService

        meta_raw = WorkspaceSettings.get(workspace_id, 'website_insights_metadata')
        last_count = 0
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                last_count = meta.get('analysis_count', 0)
            except Exception:
                pass

        current_count = WebsiteAnalysisLog.query.filter(
            WebsiteAnalysisLog.workspace_id == workspace_id,
            WebsiteAnalysisLog.email_log_id.isnot(None),
        ).count()

        new_analyses = current_count - last_count
        if new_analyses >= cls.MIN_NEW_ANALYSES_FOR_REFRESH:
            service = WebsiteInsightsService(api_key)
            service.analyze_performance(workspace_id)

    @classmethod
    def start_background_polling(cls, app, interval=21600):
        """Start a daemon thread that checks for stale insights periodically.

        Default interval: 6 hours (21600 seconds).
        """
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        cls.check_and_refresh()
                    except Exception as e:
                        app.logger.error(f'Insights refresh error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Insights scheduler started (interval={interval}s)')
