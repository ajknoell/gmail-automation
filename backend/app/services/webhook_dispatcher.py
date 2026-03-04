"""
Webhook Dispatcher — fire-and-forget HTTP POST to subscribed webhook endpoints.
Dispatches in a background thread to avoid blocking request handlers.
HMAC-signs payloads when a secret is configured.
"""
import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime

import requests

from app import db
from app.models.webhook_subscription import WebhookSubscription

logger = logging.getLogger(__name__)

# Timeout for webhook HTTP calls (seconds)
WEBHOOK_TIMEOUT = 10


def dispatch(workspace_id: int, event: str, payload: dict) -> None:
    """Dispatch a webhook event to all active subscribers.

    Fire-and-forget in a background thread. Logs failures but does not retry.

    Args:
        workspace_id: Workspace that generated the event
        event: Event type (e.g., 'reply.positive')
        payload: Event data to send as JSON body
    """
    thread = threading.Thread(
        target=_dispatch_sync,
        args=(workspace_id, event, payload),
        daemon=True,
    )
    thread.start()


def _dispatch_sync(workspace_id: int, event: str, payload: dict) -> None:
    """Synchronous dispatch to all matching subscribers.

    Args:
        workspace_id: Workspace context
        event: Event type
        payload: Event data
    """
    try:
        # Import app context for database access in thread
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        # If no app context, we can't query subscriptions
        logger.warning("Webhook dispatch called outside app context")
        return

    with app.app_context():
        subs = WebhookSubscription.query.filter_by(
            workspace_id=workspace_id,
            is_active=True,
        ).all()

        for sub in subs:
            if event not in sub.get_events():
                continue

            body = {
                'event': event,
                'workspace_id': workspace_id,
                'timestamp': datetime.utcnow().isoformat(),
                'data': payload,
            }

            try:
                headers = {'Content-Type': 'application/json'}

                # HMAC signing if secret is configured
                if sub.secret:
                    body_bytes = json.dumps(body, sort_keys=True).encode()
                    signature = hmac.new(
                        sub.secret.encode(),
                        body_bytes,
                        hashlib.sha256,
                    ).hexdigest()
                    headers['X-Webhook-Signature'] = f'sha256={signature}'

                resp = requests.post(
                    sub.url,
                    json=body,
                    headers=headers,
                    timeout=WEBHOOK_TIMEOUT,
                )

                sub.last_triggered_at = datetime.utcnow()
                sub.trigger_count = (sub.trigger_count or 0) + 1

                if resp.status_code >= 400:
                    sub.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning(f"Webhook {sub.id} returned {resp.status_code}")
                else:
                    sub.last_error = None

            except requests.RequestException as e:
                sub.last_triggered_at = datetime.utcnow()
                sub.last_error = str(e)[:500]
                logger.warning(f"Webhook {sub.id} failed: {e}")

        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update webhook status: {e}")
            db.session.rollback()
