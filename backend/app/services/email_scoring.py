"""
Email Scoring Service

Assigns a deterministic engagement score to each sent email based on
tracking outcomes (opens, clicks, replies, sentiment).

Scores are relative within a workspace — percentile-based tiers adapt
to each workspace's own data distribution.
"""

from app.models.email_log import EmailLog
from app.models.reply_message import ReplyMessage
from app import db


# ── Scoring weights ──────────────────────────────────────────────────
WEIGHT_POSITIVE_REPLY = 15
WEIGHT_NEUTRAL_REPLY = 8
WEIGHT_NEGATIVE_REPLY = 3
WEIGHT_LINK_CLICKED = 5
WEIGHT_EMAIL_OPENED = 2


def score_email(email_log, reply_messages=None):
    """
    Score a single EmailLog based on engagement signals.

    Returns:
        {
            "email_log_id": int,
            "score": float,
            "breakdown": {"opened": 2, "clicked": 5, "replied": 15, ...},
            "tier": "winner" | "loser" | "middle"   (set later by caller)
        }
    """
    breakdown = {}
    score = 0.0

    # ── Opens ────────────────────────────────────────────────────────
    if email_log.opened_at is not None:
        score += WEIGHT_EMAIL_OPENED
        breakdown['opened'] = WEIGHT_EMAIL_OPENED

    # ── Clicks ───────────────────────────────────────────────────────
    if email_log.clicked_at is not None:
        score += WEIGHT_LINK_CLICKED
        breakdown['clicked'] = WEIGHT_LINK_CLICKED

    # ── Replies ──────────────────────────────────────────────────────
    if reply_messages is None:
        reply_messages = ReplyMessage.query.filter_by(
            email_log_id=email_log.id
        ).all()

    if reply_messages:
        # Use the best sentiment among replies
        sentiments = [r.sentiment for r in reply_messages if r.sentiment]
        if 'positive' in sentiments:
            score += WEIGHT_POSITIVE_REPLY
            breakdown['replied'] = WEIGHT_POSITIVE_REPLY
            breakdown['sentiment'] = 'positive'
        elif 'neutral' in sentiments:
            score += WEIGHT_NEUTRAL_REPLY
            breakdown['replied'] = WEIGHT_NEUTRAL_REPLY
            breakdown['sentiment'] = 'neutral'
        elif 'negative' in sentiments:
            score += WEIGHT_NEGATIVE_REPLY
            breakdown['replied'] = WEIGHT_NEGATIVE_REPLY
            breakdown['sentiment'] = 'negative'
        else:
            # Reply exists but no sentiment classification yet
            score += WEIGHT_NEUTRAL_REPLY
            breakdown['replied'] = WEIGHT_NEUTRAL_REPLY
            breakdown['sentiment'] = 'unknown'
    elif email_log.replied_at is not None:
        # replied_at is set but no ReplyMessage records — treat as neutral
        score += WEIGHT_NEUTRAL_REPLY
        breakdown['replied'] = WEIGHT_NEUTRAL_REPLY
        breakdown['sentiment'] = 'unknown'

    return {
        'email_log_id': email_log.id,
        'subject': email_log.subject,
        'body': email_log.body,
        'recipient_email': email_log.recipient_email,
        'sent_at': email_log.created_at.isoformat() if email_log.created_at else None,
        'open_count': email_log.open_count or 0,
        'click_count': email_log.click_count or 0,
        'score': score,
        'breakdown': breakdown,
        'tier': 'middle',  # assigned later by get_winners_and_losers
    }


def score_emails_for_workspace(workspace_id):
    """
    Score every sent email in a workspace.

    Returns a list of score dicts sorted by score descending.
    """
    email_logs = (
        EmailLog.query
        .filter_by(workspace_id=workspace_id, status='sent')
        .order_by(EmailLog.created_at.desc())
        .all()
    )

    if not email_logs:
        return []

    # Batch-load all reply messages for these logs
    log_ids = [e.id for e in email_logs]
    replies = ReplyMessage.query.filter(
        ReplyMessage.email_log_id.in_(log_ids)
    ).all()

    # Group replies by email_log_id
    replies_by_log = {}
    for r in replies:
        replies_by_log.setdefault(r.email_log_id, []).append(r)

    scored = []
    for log in email_logs:
        log_replies = replies_by_log.get(log.id, [])
        scored.append(score_email(log, reply_messages=log_replies))

    # Sort by score descending
    scored.sort(key=lambda x: x['score'], reverse=True)

    return scored


def get_winners_and_losers(scored_emails, percentile=0.25):
    """
    Split scored emails into winners (top percentile) and losers (bottom percentile).
    Assigns tier labels to each email in the full list.

    Returns (winners, losers) — each a list of score dicts.
    """
    if not scored_emails:
        return [], []

    n = len(scored_emails)
    cutoff = max(1, int(n * percentile))

    # Already sorted by score desc
    winners = scored_emails[:cutoff]
    losers = scored_emails[-cutoff:]

    # Tag tiers on the full list
    winner_ids = {e['email_log_id'] for e in winners}
    loser_ids = {e['email_log_id'] for e in losers}

    for e in scored_emails:
        if e['email_log_id'] in winner_ids:
            e['tier'] = 'winner'
        elif e['email_log_id'] in loser_ids:
            e['tier'] = 'loser'
        else:
            e['tier'] = 'middle'

    return winners, losers
