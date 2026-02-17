"""Lightweight spam score checker for outbound emails.

Checks generated email content for common spam triggers before sending,
helping avoid deliverability issues.
"""

import re
from typing import Dict, List


# Words/phrases that spam filters commonly flag
SPAM_TRIGGER_WORDS = [
    'act now', 'buy now', 'limited time', 'click here', 'free money',
    'no obligation', 'risk free', 'winner', 'congratulations',
    'you have been selected', 'double your', 'earn extra cash',
    'million dollars', 'once in a lifetime', 'urgent',
    'apply now', 'order now', 'call now', 'don\'t delete',
    'this isn\'t spam', 'not spam', 'as seen on',
    'cash bonus', 'guarantee', '100% free', 'no cost',
    'no fees', 'lowest price', 'best price', 'incredible deal',
    'special promotion', 'exclusive deal', 'act immediately',
    'what are you waiting for', 'don\'t hesitate',
    'while supplies last', 'for instant access', 'get it now',
    'click below', 'sign up free',
]

# Money/currency patterns
MONEY_PATTERNS = [
    r'\$\d{1,3}(?:,\d{3})+',         # $1,000 or $1,000,000
    r'\$\d+[kKmMbB]\b',               # $50K, $1M
    r'\b\d+%\s*off\b',                # 50% off
    r'\b(?:save|earn|win|make)\s+\$',  # save $, earn $, etc.
]


def check_spam_score(subject: str, body: str) -> Dict:
    """Analyse email content for spam indicators.

    Returns:
        {
            'score': int 0-100 (higher = spammier),
            'level': 'low' | 'medium' | 'high',
            'reasons': list of human-readable reason strings,
        }
    """
    reasons: List[str] = []
    score = 0

    if not subject and not body:
        return {'score': 0, 'level': 'low', 'reasons': []}

    combined = f'{subject or ""} {body or ""}'.lower()
    subject_lower = (subject or '').lower()
    body_lower = (body or '').lower()

    # Strip HTML tags for text analysis
    text_only = re.sub(r'<[^>]+>', ' ', combined)
    text_only = re.sub(r'\s+', ' ', text_only).strip()

    # --- 1. Spam trigger words ---
    found_triggers = []
    for word in SPAM_TRIGGER_WORDS:
        if word in text_only:
            found_triggers.append(word)
    if found_triggers:
        count = len(found_triggers)
        penalty = min(count * 8, 30)
        score += penalty
        reasons.append(
            f'Contains spam trigger phrases: {", ".join(found_triggers[:5])}'
            + (f' (+{count - 5} more)' if count > 5 else '')
        )

    # --- 2. ALL CAPS words ---
    words = re.findall(r'\b[A-Z]{2,}\b', f'{subject or ""} {re.sub(r"<[^>]+>", " ", body or "")}')
    # Filter out common abbreviations
    caps_words = [w for w in words if w not in ('CEO', 'CTO', 'CFO', 'COO', 'VP',
                                                  'AI', 'ML', 'API', 'SaaS', 'B2B',
                                                  'B2C', 'ROI', 'KPI', 'USA', 'UK',
                                                  'HTML', 'CSS', 'JS', 'PM', 'AM',
                                                  'CRM', 'ERP', 'HR', 'IT', 'PR',
                                                  'Q1', 'Q2', 'Q3', 'Q4', 'YC',
                                                  'II', 'III', 'IV')]
    if len(caps_words) > 3:
        score += min(len(caps_words) * 3, 20)
        reasons.append(f'Excessive ALL CAPS words ({len(caps_words)} found)')

    # --- 3. Excessive exclamation marks ---
    excl_count = text_only.count('!')
    if excl_count > 2:
        score += min(excl_count * 5, 20)
        reasons.append(f'Too many exclamation marks ({excl_count} found)')

    # --- 4. Too many links ---
    link_count = len(re.findall(r'https?://', combined))
    href_count = len(re.findall(r'href\s*=', combined))
    total_links = max(link_count, href_count)
    if total_links > 3:
        score += min((total_links - 3) * 5, 15)
        reasons.append(f'High number of links ({total_links} found)')

    # --- 5. Money language ---
    money_hits = 0
    for pattern in MONEY_PATTERNS:
        money_hits += len(re.findall(pattern, text_only, re.IGNORECASE))
    if money_hits > 0:
        score += min(money_hits * 8, 20)
        reasons.append(f'Money/discount language detected ({money_hits} instances)')

    # --- 6. Fake Re:/Fwd: in subject ---
    if subject_lower.startswith(('re:', 'fwd:', 'fw:')):
        score += 15
        reasons.append('Subject starts with Re:/Fwd: — looks like a fake reply which spam filters flag')

    # --- 7. Subject in ALL CAPS ---
    if subject and subject == subject.upper() and len(subject) > 10:
        score += 15
        reasons.append('Entire subject line is in ALL CAPS')

    # --- 8. No unsubscribe / excessive length check ---
    if body and len(body) > 5000:
        word_count = len(text_only.split())
        if word_count > 800:
            score += 10
            reasons.append(f'Very long email body ({word_count} words) — shorter emails perform better')

    # Clamp to 0-100
    score = max(0, min(100, score))

    if score >= 50:
        level = 'high'
    elif score >= 25:
        level = 'medium'
    else:
        level = 'low'

    return {
        'score': score,
        'level': level,
        'reasons': reasons,
    }
