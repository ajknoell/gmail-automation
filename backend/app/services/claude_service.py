from anthropic import Anthropic
from typing import Dict
import json
import re


def _strip_business_suffixes(name: str) -> str:
    """Remove legal/business suffixes like LLC, Inc., Corp, etc."""
    # Remove trailing suffixes (with optional commas, dots, spaces)
    name = re.sub(
        r'[,\s]+(LLC|L\.L\.C\.|INC\.?|INCORPORATED|CORP\.?|CORPORATION|LTD\.?|LIMITED|LP|L\.P\.|PLLC|P\.?C\.?|DBA)\s*$',
        '', name, flags=re.IGNORECASE
    ).strip()
    # Clean up any trailing comma or period left behind
    name = name.rstrip(',. ')
    return name


def clean_company_name(company: str) -> str:
    """Extract a human-readable company name from a URL or domain.

    Examples:
        'blglass.com'                  -> 'Blglass'
        'https://www.acme-corp.com'    -> 'Acme Corp'
        'blue-sky.io/about'            -> 'Blue Sky'
        'Acme Inc.'                    -> 'Acme'
        'VE BUILDERS, LLC'             -> 'VE BUILDERS'
    """
    if not company:
        return company

    cleaned = company.strip()
    # Strip protocol
    cleaned = re.sub(r'^https?://', '', cleaned)
    # Strip www.
    cleaned = re.sub(r'^www\.', '', cleaned)
    # Strip path, query, and fragment
    cleaned = re.sub(r'[/?#].*$', '', cleaned)

    # If it looks like a domain (has a TLD), strip the TLD to get the name
    domain_match = re.match(
        r'^([^.]+)\.'
        r'(com|net|org|io|co|biz|info|us|uk|de|fr|ca|au|gov|edu|dev|app|ai|tech)'
        r'(\.[a-z]{2,3})?$',
        cleaned, re.IGNORECASE
    )
    if domain_match:
        cleaned = domain_match.group(1)
    elif cleaned == company.strip():
        # Nothing was stripped, not a URL — just strip business suffixes
        return _strip_business_suffixes(company.strip())

    # Make the extracted name readable:
    # Insert spaces before capitals in camelCase (e.g. "blueGlass" -> "blue Glass")
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    # Replace hyphens and underscores with spaces
    cleaned = cleaned.replace('-', ' ').replace('_', ' ')
    return _strip_business_suffixes(cleaned.title())


def _looks_like_company_name(name: str) -> bool:
    """Detect if a 'name' value is actually a company/business name.

    Returns True for things like "B & L Glass", "Home at Home LLC",
    "Smith Plumbing Services", etc. — anything that shouldn't be used
    as a personal greeting.
    """
    if not name:
        return False
    n = name.strip()
    lower = n.lower()

    # Common company suffixes / indicators
    company_words = {
        'llc', 'inc', 'corp', 'co', 'ltd', 'llp', 'lp',
        'glass', 'plumbing', 'roofing', 'electric', 'electrical',
        'construction', 'contracting', 'landscaping', 'painting',
        'cleaning', 'flooring', 'fencing', 'paving', 'masonry',
        'services', 'solutions', 'group', 'agency', 'studio',
        'enterprises', 'associates', 'partners', 'consulting',
        'company', 'properties', 'realty', 'restoration',
        'industries', 'innovations', 'technologies', 'tech',
        'design', 'designs', 'interiors', 'exteriors',
        'home', 'homes', 'builders', 'building',
        'supply', 'supplies', 'equipment',
        'auto', 'automotive', 'motors',
        'media', 'digital', 'creative',
    }
    words = lower.split()
    if any(w.rstrip('.,') in company_words for w in words):
        return True

    # Contains "&" — very common in business names, rare in personal names
    if '&' in n:
        return True

    # Contains "and" between words (like "Smith and Sons")
    if ' and ' in lower:
        return True

    # Ends with a period-abbreviated suffix (like "Inc." or "Co.")
    if re.search(r'\b(inc|corp|co|ltd|llc)\.$', lower):
        return True

    return False


def _extract_contact_name(custom_fields: dict) -> str:
    """Try to find a real contact/person name from custom fields.

    CSVs often have a 'name' column with the business name and a separate
    column like 'contact_name', 'first_name', 'contact', or 'person' with
    the actual human's name.  These extra columns end up in custom_fields.

    Key matching is case-insensitive and treats spaces/underscores as
    equivalent (so 'First Name', 'first_name', and 'first name' all match).
    """
    if not custom_fields:
        return ''

    # Patterns to match (normalized: lowercase, underscores)
    contact_patterns = [
        'contact_name', 'contact', 'first_name', 'firstname',
        'person', 'contact_person', 'owner', 'owner_name',
        'full_name', 'fullname',
    ]

    # Build a lookup: normalized_key -> original_key
    normalized = {}
    for orig_key in custom_fields:
        norm = orig_key.lower().strip().replace(' ', '_')
        normalized[norm] = orig_key

    for pattern in contact_patterns:
        orig_key = normalized.get(pattern)
        if orig_key:
            val = custom_fields[orig_key]
            if val and isinstance(val, str) and val.strip():
                # Don't use it if it also looks like a company name
                if not _looks_like_company_name(val.strip()):
                    return val.strip()
    return ''


def _name_from_email(email: str) -> str:
    """Try to extract a first name from an email prefix.

    'jeff@blglass.com'  →  'Jeff'
    'sarah.jones@...'   →  'Sarah'
    'info@...'          →  ''  (generic, skip)
    """
    if not email or '@' not in email:
        return ''
    prefix = email.split('@')[0].lower()
    # Skip generic / role-based prefixes
    generic = {
        'info', 'admin', 'hello', 'contact', 'support', 'sales',
        'office', 'service', 'team', 'billing', 'help', 'mail',
        'noreply', 'no-reply', 'webmaster', 'postmaster',
        'enquiries', 'inquiries', 'marketing', 'hr',
    }
    # Take first part if separated by dots or underscores
    first = re.split(r'[._]', prefix)[0]
    if first in generic or len(first) < 2:
        return ''
    # Only use if it looks like a real name (all alpha)
    if first.isalpha():
        return first.capitalize()
    return ''


def resolve_recipient_fields(recipient_name: str, cleaned_company: str,
                             email: str, custom_fields: dict) -> tuple:
    """Resolve the best name and company for a recipient.

    Handles the common case where a CSV puts the business name in the
    'name' column and the actual contact person in a secondary column
    like 'First Name' or 'contact_name'.

    Returns (name, company) with the best values found.
    """
    name = (recipient_name or '').strip()
    company = (cleaned_company or '').strip()

    # First, check if the CSV has an explicit contact name field.
    # If it does, the 'name' column is almost certainly the business name.
    contact_from_fields = _extract_contact_name(custom_fields or {})
    if contact_from_fields:
        # Check if the main name is just the full version of the contact name
        # (e.g., name="Frances Brunelle", First Name="Frances" — same person)
        contact_lower = contact_from_fields.lower()
        name_lower = name.lower() if name else ''
        same_person = (
            (contact_lower in name_lower or name_lower in contact_lower)
            and not _looks_like_company_name(name)  # "Gappsi, Inc." is still a company
        )
        if not company and name and not same_person:
            company = name  # The main 'name' field is the company
        name = contact_from_fields
    elif _looks_like_company_name(name):
        # No contact name in custom fields, but main name looks like a company
        if not company:
            company = name
        name = ''

    # Last resort: derive from email prefix
    if not name:
        name = _name_from_email(email or '')

    return name, company


def _strip_ai_dashes(text: str) -> str:
    """Replace em dashes, en dashes, and double hyphens with commas.

    These punctuation marks are a telltale sign of AI-generated text
    and should never appear in outreach emails.
    """
    if not text:
        return text
    # Em dash (—) and en dash (–) → comma
    text = text.replace('\u2014', ',')   # em dash
    text = text.replace('\u2013', ',')   # en dash
    # Double hyphen (--) → comma
    text = re.sub(r'(?<!\-)--(?!\-)', ',', text)
    # Clean up any double commas or comma-space issues from replacements
    text = re.sub(r',\s*,', ',', text)
    # Fix double periods (e.g. "trust.." → "trust.")
    text = re.sub(r'\.{2,}', '.', text)
    return text


def _strip_ai_dashes_from_analysis(analysis: dict):
    """Apply _strip_ai_dashes to all text fields in a structured analysis dict."""
    if not analysis:
        return
    for issue in analysis.get('issues', []):
        issue['title'] = _strip_ai_dashes(issue.get('title', ''))
        issue['description'] = _strip_ai_dashes(issue.get('description', ''))
        if issue.get('example'):
            issue['example'] = _strip_ai_dashes(issue['example'])
    if analysis.get('recommendation'):
        analysis['recommendation'] = _strip_ai_dashes(analysis['recommendation'])


class ClaudeService:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def analyze_website(
        self,
        website_text: str,
        company_name: str,
        url: str,
        screenshot_b64: str = None,
        mobile_screenshot_b64: str = None,
        health_issues: list = None,
        learned_website_insights: dict = None,
        previous_observations: str = None,
    ) -> dict:
        """Analyze a website and return structured analysis with severity classifications.

        Returns a dict with 'issues' (list of dicts with title, description,
        severity, example) and 'recommendation' (str).

        When ``health_issues`` are provided they take priority — the first
        issue will address the critical problem.  When a screenshot is
        provided, uses Claude's vision capabilities for accurate visual
        analysis.  Falls back to text-only analysis otherwise.

        When ``previous_observations`` is provided (on regeneration), the
        model is instructed to find completely different observations.
        """

        if screenshot_b64:
            return self._analyze_website_visual(
                screenshot_b64, website_text, company_name, url,
                mobile_screenshot_b64=mobile_screenshot_b64,
                health_issues=health_issues,
                learned_website_insights=learned_website_insights,
                previous_observations=previous_observations,
            )
        return self._analyze_website_text(
            website_text, company_name, url,
            health_issues=health_issues,
            learned_website_insights=learned_website_insights,
            previous_observations=previous_observations,
        )

    @staticmethod
    def _build_learned_guidance(learned_website_insights: dict = None) -> str:
        """Build data-driven guidance string from learned website analysis patterns."""
        if not learned_website_insights:
            return ""
        parts = []
        if learned_website_insights.get('observation_types_that_work'):
            parts.append(f"WHAT WORKS: {learned_website_insights['observation_types_that_work']}")
        if learned_website_insights.get('observation_types_to_avoid'):
            parts.append(f"WHAT TO AVOID: {learned_website_insights['observation_types_to_avoid']}")
        if learned_website_insights.get('framing_patterns'):
            parts.append(f"FRAMING: {learned_website_insights['framing_patterns']}")
        if learned_website_insights.get('priority_focus_areas'):
            parts.append(f"FOCUS AREAS: {learned_website_insights['priority_focus_areas']}")
        if learned_website_insights.get('personalization_depth'):
            parts.append(f"PERSONALIZATION: {learned_website_insights['personalization_depth']}")
        if learned_website_insights.get('length_and_detail'):
            parts.append(f"DETAIL LEVEL: {learned_website_insights['length_and_detail']}")
        if learned_website_insights.get('top_recommendation'):
            parts.append(f"TOP PRIORITY: {learned_website_insights['top_recommendation']}")
        if parts:
            confidence = learned_website_insights.get('confidence', 'medium')
            return (
                f"\nDATA-DRIVEN GUIDANCE (learned from analyzing which website observations actually "
                f"drive email replies — confidence: {confidence} — apply these patterns):\n"
                + "\n".join(parts) + "\n"
            )
        return ""

    # ------------------------------------------------------------------
    # Visual (screenshot) analysis — primary path
    # ------------------------------------------------------------------

    def _analyze_website_visual(
        self,
        screenshot_b64: str,
        website_text: str,
        company_name: str,
        url: str,
        mobile_screenshot_b64: str = None,
        health_issues: list = None,
        learned_website_insights: dict = None,
        previous_observations: str = None,
    ) -> str:
        """Analyze a website screenshot (with optional supplementary text) via vision."""

        learned_guidance = self._build_learned_guidance(learned_website_insights)

        text_supplement = ""
        if website_text:
            trimmed = website_text[:3000]
            text_supplement = f"""
SUPPLEMENTARY TEXT (scraped from the HTML source WITHOUT JavaScript — use ONLY
to catch details not visible in the screenshot, such as meta descriptions or
hidden content.  The screenshot is the primary source of truth for what
visitors actually see.  Animated counters/stats may show "0" in this text
even though the screenshot shows real numbers; always trust the screenshot):
{trimmed}
"""

        # Build the critical-issues block when health checks found problems.
        # Filter out BOT_BLOCKED_403 when we have a screenshot — the screenshot
        # proves the site loads fine; the 403 was just bot/Cloudflare protection.
        issues_block = ""
        if health_issues:
            real_issues = [
                issue for issue in health_issues
                if not issue.startswith('BOT_BLOCKED_403')
            ]
            if real_issues:
                formatted = "\n".join(f"  - {issue}" for issue in real_issues)
                issues_block = f"""
CRITICAL ISSUES DETECTED BY OUR AUTOMATED CHECKS (these are real problems
that visitors experience RIGHT NOW — they MUST be your #1 priority):
{formatted}

IMPORTANT: Your observation MUST address the most critical issue above.
Frame it helpfully — show the impact on their business and how fixing
it would help.
"""

        mobile_note = ""
        if mobile_screenshot_b64:
            mobile_note = "\nYou are also seeing a MOBILE SCREENSHOT — compare the desktop and mobile views. If the mobile layout is broken, unusable, or missing key content, that's a strong observation."

        previous_block = ""
        if previous_observations:
            previous_block = f"""
PREVIOUS OBSERVATIONS (the user clicked "Regenerate" because these weren't good enough — you MUST pick completely different observations this time):
{previous_observations}

DO NOT repeat or rephrase any of the above. Find entirely new issues to highlight.
"""

        prompt = f"""You're a web designer reviewing a potential client's website. You are looking at a SCREENSHOT of their live site — this is exactly what a visitor sees.{mobile_note}

COMPANY: {company_name}
URL: {url}
{learned_guidance}{issues_block}{text_supplement}{previous_block}
YOUR TASK: Find the single most impactful opportunity where a small improvement could bring them more customers, more trust, or a stronger first impression. This goes into a friendly cold outreach email. Quality over quantity: one genuinely insightful observation beats two generic ones.

BEFORE YOU WRITE ANYTHING, silently inventory what the site IS doing well: What services are listed? Where? Is there a clear hero message? Navigation with service categories? Phone number visible? Reviews section? Gallery? CTA buttons? Only AFTER cataloging what exists should you look for a genuine gap. If the site already shows its services clearly in the header, nav, or hero, do NOT claim the messaging is "general" or services are "unclear."

ANALYZE LIKE A MARKETING STRATEGIST AND WEB EXPERT, NOT JUST A DESIGNER:
Think about the site through the lens of conversion rate optimization (CRO), proven marketing principles, and modern web development best practices:

MARKETING & CRO:
- 5-SECOND TEST: Can a visitor tell what this business does, why they're different, and what to do next within 5 seconds? If not, that's the #1 issue.
- ABOVE-THE-FOLD HIERARCHY: The most important message, differentiator, or call-to-action should be visible without scrolling. What's currently above the fold? Is it the right thing?
- VISUAL CREDIBILITY: Modern visitors judge trustworthiness in milliseconds. Dated design patterns (pre-2018 aesthetics, outdated fonts, old-school gradients) erode trust even if the content is strong.
- SOCIAL PROOF PLACEMENT: Reviews and testimonials convert best when placed near decision points (next to CTAs, on service pages), not buried at the bottom.
- SCANNABILITY: 79% of web users scan rather than read. Short paragraphs, bullet points, clear headers, and visual breaks make content digestible.
- MOBILE-FIRST: Over 60% of local service searches happen on mobile. If the mobile screenshot shows issues, that's high-impact.
- CLEAR NEXT STEP: Every page should have one obvious thing the visitor should do (call, get a quote, book online). Multiple competing CTAs dilute conversions.

WEB DEVELOPMENT & UX:
- PAGE SPEED: If the screenshot shows lots of heavy elements (massive hero images, unoptimized galleries, tons of widgets/scripts), the site likely loads slowly. Slow sites lose 53% of visitors on mobile.
- MODERN WEB STANDARDS: Sites using outdated frameworks, table-based layouts, or Flash look broken on modern browsers. A site that hasn't been updated in years may have compatibility issues visitors notice.
- RESPONSIVE DESIGN: If the mobile screenshot shows content overflowing, tiny unreadable text, or elements overlapping, that's a real problem affecting the majority of their visitors.
- ACCESSIBILITY: Low contrast text, tiny font sizes, or missing alt text on images hurts both users and search rankings.
- CLUTTERED OR SLOW-LOADING ELEMENTS: Excessive third-party widgets, auto-playing videos, pop-ups stacking on top of each other, or chat widgets covering key content all hurt user experience.

PRIORITY ORDER (follow this strictly):
1. CRITICAL ISSUES FIRST: Site not showing their actual business (generic/blank page), fake virus/security warnings or scam popups, real security warnings scaring visitors away, site not loading at all. If a critical issue was detected above, it MUST be observation #1.
   - PARKED / NOT-CONNECTED / BLANK PAGES: If the screenshot shows a generic "this domain isn't connected" page, a hosting provider's default page, or a blank/empty page, keep BOTH observations extremely short and concrete. Do NOT speculate about what the site could look like or suggest features for a site that doesn't exist yet. Example:
     1. Your web address just shows a generic page, so anyone searching for you sees nothing
     2. Even a simple one-page site with your number and services would start turning searches into calls
   - SCAM/MALWARE: If you see fake antivirus warnings, pop-up alerts about "viruses detected", or "your computer is infected" messages, this is CRITICAL. Frame it as: "When someone visits your website, they're seeing a fake virus warning instead of your business, that's scaring away every potential customer"
2. DESIGN & CONVERSION ISSUES: Look at the screenshot through both a design AND marketing lens:
   - OUTDATED DESIGN: If the site looks like it was built 5+ years ago (old design patterns, dated typography, boxy layouts), a modern refresh would increase trust and conversions. Frame it as helping the site match the quality of their work.
   - POOR VISUAL HIERARCHY: Everything looks the same size/weight, nothing stands out, no clear path for the eye to follow. Headers that don't pop, sections that blur together.
   - TEXT-HEAVY SECTIONS: Too much text, not enough visual breathing room. Visitors scan, not read. If text blocks dominate, suggest tightening the copy.
   - WEAK ABOVE-THE-FOLD: The first screen should sell. If the hero section is generic, vague, or doesn't communicate what makes this business special, that's a high-impact observation.
   - BURIED DIFFERENTIATORS: If the business has something genuinely unique (specific specialization, years of experience, guarantees) but it's not prominent, that's worth noting. But ONLY if you can clearly see it's buried — don't guess.
   - HARD TO SCAN: No bullet points, no short paragraphs, no visual breaks.
   - PHOTOS: Almost NEVER flag photos as stock. Portfolio/gallery photos are the business's own work. Family/team photos are their real people. Only flag stock if you see watermarks or obviously unrelated generic subjects. When in doubt, skip this entirely.
   - DATED/STALE FEEL: NEVER cite a specific copyright year — you cannot reliably read small footer text from screenshots. If the health checks above flagged OUTDATED_COPYRIGHT, use that as a signal that the design likely needs a refresh, but frame it as the design looking dated, NOT as "your copyright says 20XX." NEVER question whether the business is still active, directly OR indirectly. Saying "visitors might wonder if you're still booking projects" or "homeowners may question if you're still in business" is just as offensive as saying it yourself. Every business you're analyzing IS active.
3. FUNCTIONAL ISSUES: Broken layouts, pages that don't render, missing content sections.
4. FEATURE SUGGESTIONS: Only suggest adding new features if the existing content and layout are already clean. A messy site doesn't need more stuff.

ACCURACY RULES (these are non-negotiable):

1. VERIFY BEFORE YOU CLAIM: For every observation, ask: "If the owner checks their site right now, will they see exactly what I described?" If there's ANY chance the answer is no, throw it out. One wrong claim ruins the entire email. A vague but true observation is infinitely better than a specific but wrong one. Never cite copyright years, specific mobile layout issues, or page structure details unless the evidence is unmistakable.

2. DON'T ASSUME THINGS ARE MISSING: Most sites already show their services, have contact info, organize their content, and explain what makes them different. Never suggest adding or reorganizing something without confirming it's actually lacking. If the site already has reviews, galleries, or CTAs visible, do NOT suggest adding them.

3. RESPECT THEIR WORK: Never call their branding "generic" (especially if it contains their company name or a pun on it). Never question their stats, credentials, or claims. Never say something is "your biggest" or "your most important" anything. Never imply they might be inactive or not booking, directly or indirectly. They know their business better than you.

4. SKIP UNRELIABLE DETAILS: Never cite specific copyright years (screenshots misread footer text). Never claim specific mobile layout issues ("logos stack on mobile") unless extremely obvious. Never describe specific page structure ("the homepage focuses on explaining X") unless you can clearly verify it. When in doubt, focus on design polish, visual appeal, or content presentation.

5. BANNED GENERIC OBSERVATIONS — these sound safe but are almost always WRONG:
   - "organize/categorize your services better"
   - "lead with your specific services" or "show what you offer"
   - "show visitors what makes you different"
   - "the messaging is general/unclear"
   - "content needs better structure/categories"
   - "add contact information / phone number / social links"
   - "add testimonials / reviews / a blog"
   If the owner would read it and think "but we already do that," don't say it.

PREFER observations about HOW the site presents content over suggestions to ADD new content. Name the opportunity and the benefit in one sentence. Lead positive:
   - Good: "You've got great project work; making those photos the centerpiece would let your craftsmanship sell itself"
   - Good: "A quick-quote form could turn browsers into actual leads"
   - Bad: "Your photos look generic" (negative, no benefit)
   - Bad: "Your SSL certificate is expired" (too technical)
Tie every suggestion to a business outcome: more calls, more trust, more conversions.

LANGUAGE RULE — NO TECH JARGON:
- The recipient is a business owner, NOT a web developer. Write like you're explaining to a friend.
- NEVER use terms like: "parked domain", "SSL certificate", "DNS", "redirect loop", "server error", "placeholder page", "meta tags", "SEO", "rendering", "viewport", "responsive", "CMS", "hosting"
- INSTEAD translate to plain English:
  - "parked domain" → "your web address isn't showing your actual business yet — visitors just see a generic page"
  - "SSL certificate expired" → "visitors get a scary security warning before they can even see your site"
  - "site not loading" → "when people go to your website, nothing comes up"
  - "placeholder page" → "your website shows a generic template instead of your actual business"
- Always describe the VISITOR EXPERIENCE, not the technical cause

TONE:
- Lead with what's WORKING, then suggest the upgrade. The pattern is: acknowledge the good → suggest how to make it even better.
- BAD: "Your hero image looks generic; swapping it for real project photos would build more trust." (Negative, critical, puts them on the defensive.)
- BAD: "The text block is pretty dense, and breaking it into bullets would help. People scan, they don't read." (TWO sentences and negative. WRONG.)
- GOOD: "You've clearly got strong work, showcasing those finished projects front and center would let it sell itself"
- GOOD: "The content is solid; breaking it into scannable bullets would help visitors find what they need fast"
- EXACTLY ONE SENTENCE per issue description. If your description has a period followed by more words, you wrote too much.
- MAX 25 words per issue description. Count them. If over 25, rewrite shorter.
- Frame everything as an OPPORTUNITY to level up, not a problem to fix. These are businesses that are already doing well.
- NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead.

SEVERITY CLASSIFICATION:
- "critical": Issues that directly harm conversions, user trust, or usability RIGHT NOW. Examples: broken navigation, unclear value proposition, mobile rendering issues, outdated/unprofessional design, missing contact information, security warnings, site down.
- "important": Issues that diminish effectiveness but don't completely block results. Examples: slow load times, weak calls-to-action, poor content structure, inconsistent branding.
- Do NOT include minor/nice-to-have issues. Only critical and important.
- A single solid critical issue is better than padding with weak points.

YOUR RESPONSE MUST BE ONLY a valid JSON object, nothing else. No markdown fences, no extra text:
{{"issues": [{{"title": "Brief 5-7 word title", "description": "One sentence, max 25 words, explaining impact on their business", "severity": "critical", "example": "Optional specific example from the site"}}], "recommendation": "One sentence on the most impactful fix"}}

Return exactly 1 issue. Focus on the single most compelling observation. """

        try:
            content_blocks = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64,
                    },
                },
            ]
            if mobile_screenshot_b64:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": mobile_screenshot_b64,
                    },
                })
            content_blocks.append({
                "type": "text",
                "text": prompt,
            })

            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=250,
                messages=[{
                    "role": "user",
                    "content": content_blocks,
                }],
            )
            result = self._parse_analysis_json(message.content[0].text)
            _strip_ai_dashes_from_analysis(result)
            return result
        except Exception as e:
            print(f"Visual website analysis error: {e}")
            # Fall back to text-only if vision call fails
            if website_text or health_issues:
                return self._analyze_website_text(
                    website_text, company_name, url,
                    health_issues=health_issues,
                    learned_website_insights=learned_website_insights,
                )
            return None

    # ------------------------------------------------------------------
    # Text-only analysis — fallback path
    # ------------------------------------------------------------------

    def _analyze_website_text(
        self, website_text: str, company_name: str, url: str,
        health_issues: list = None,
        learned_website_insights: dict = None,
        previous_observations: str = None,
    ) -> str:
        """Analyze a website from scraped text only (fallback when no screenshot)."""

        learned_guidance = self._build_learned_guidance(learned_website_insights)

        # Build the critical-issues block when health checks found problems.
        # Filter out BOT_BLOCKED_403 — a 403 from our requests library is
        # almost always bot/Cloudflare protection, not a real visitor issue.
        issues_block = ""
        if health_issues:
            real_issues = [
                issue for issue in health_issues
                if not issue.startswith('BOT_BLOCKED_403')
            ]
            if real_issues:
                formatted = "\n".join(f"  - {issue}" for issue in real_issues)
                issues_block = f"""
CRITICAL ISSUES DETECTED BY OUR AUTOMATED CHECKS (these are real problems
that visitors experience RIGHT NOW — they MUST be your #1 priority):
{formatted}

IMPORTANT: Your observation MUST address the most critical issue above.
Frame it helpfully — show the impact on their business and how fixing
it would help.
"""

        text_block = ""
        if website_text:
            text_block = f"""
SCRAPED TEXT (raw HTML text extraction — NOT what a visitor actually sees):
{website_text}

CRITICAL CONTEXT: This text was scraped from the raw HTML source. You cannot see the actual visual design, layout, or images. Be cautious about suggesting things that may already exist on the site visually but aren't captured in the raw text.
"""

        previous_block = ""
        if previous_observations:
            previous_block = (
                "\nPREVIOUS OBSERVATIONS (the user clicked Regenerate because these "
                "were not good enough, you MUST pick completely different observations "
                f"this time):\n{previous_observations}\n\n"
                "DO NOT repeat or rephrase any of the above. Find entirely new issues "
                "to highlight.\n"
            )

        prompt = f"""You're a web designer who genuinely wants to help a potential client. Find the single most impactful opportunity where a small improvement to their site could bring them more customers, more trust, or a stronger first impression. This goes into a friendly cold outreach email — the goal is to show the VALUE of what better looks like, not to point out what's wrong. Quality over quantity: one genuinely insightful observation beats two generic ones.

COMPANY: {company_name}
URL: {url}
{learned_guidance}{issues_block}{text_block}{previous_block}
PRIORITY ORDER (follow this strictly):
1. CRITICAL ISSUES FIRST: Site not showing their actual business (generic/blank page), security warnings scaring visitors away, site not loading at all. If a critical issue was detected above, it MUST be observation #1.
   - PARKED / NOT-CONNECTED / BLANK PAGES: If the text is mostly boilerplate from a hosting provider or domain registrar, keep BOTH observations extremely short and concrete. Do NOT speculate about what the site could look like. Example:
     1. Your web address just shows a generic page, so anyone searching for you sees nothing
     2. Even a simple one-page site with your number and services would start turning searches into calls
2. CONTENT & STRUCTURE PROBLEMS: These are the most common real issues. Even from text alone, you can detect:
   - CONTENT OVERLOAD: Massive amounts of text, paragraphs that go on forever, too many topics crammed together. If the scraped text feels overwhelming to read, imagine how a visitor feels.
   - UNCLEAR STRUCTURE: Sections that blur together, no clear hierarchy of information, everything competing for attention.
   - UNCLEAR VALUE PROPOSITION: If you can't tell in the first few sentences what this business does best and why someone should call them, that's the #1 issue.
   - HARD TO SCAN: No clear sections, everything runs together, no concise messaging.
   - DATED/STALE FEEL: If the health checks flagged OUTDATED_COPYRIGHT, use it as a signal the design likely needs a refresh. NEVER cite a specific copyright year in your observations — just frame it as the design looking dated. NEVER say the business looks inactive or question whether they're still operating, directly OR indirectly (e.g. "visitors might wonder if you're still booking" is just as bad). Every business you're analyzing IS active.
   These content quality issues are MORE impactful than suggesting new features.
3. FUNCTIONAL ISSUES: Broken layouts, pages that don't render, missing content sections.
4. FEATURE SUGGESTIONS: Only suggest adding new features if the existing content is already clean and focused.

IMPORTANT — AVOID FALSE SUGGESTIONS:
- If the text mentions reviews, testimonials, ratings, or social proof, the site likely ALREADY has them — do NOT suggest adding them.
- If the text mentions galleries, portfolios, or project showcases, the site likely ALREADY has them — do NOT suggest adding them.
- If you're unsure whether something exists on the site, do NOT suggest adding it. Find a different suggestion you're confident about.
- PREFER observations about content QUALITY over suggestions to add new content. "Tightening up the homepage so visitors immediately see your top services" beats "add a photo gallery."
- NEVER suggest "adding contact information," "making it easier to get in touch," "adding a phone number," or any variation. Every business site has contact info. This is lazy filler. Similarly, never suggest adding "social media links," "testimonials," "reviews," "a blog," or other generic features.

IMPORTANT — TEXT SCRAPING LIMITATIONS:
- This text was scraped WITHOUT JavaScript execution. Animated counters and stats that use JavaScript to count up from 0 will appear as "0" in this text even though they display real numbers on the live site. Do NOT flag counters showing "0" as a problem.
- Navigation menus have been stripped, but some nav labels may still appear in the text. Do not treat stray menu labels as page content or filing decisions.

RED FLAGS THAT THE SITE IS BROKEN/NON-FUNCTIONAL (check these FIRST, even without health-check data):
- Content that reads like a template dump (every section present but no visual hierarchy) — the site framework exists but isn't working
- If you see these signs, the #1 issue is: the site isn't loading properly for visitors. Frame it helpfully, not harshly.

IF THE SITE APPEARS FUNCTIONAL AND NO CRITICAL ISSUES WERE DETECTED, then look for:
- Content quality: Is there too much text? Is the messaging clear? Can a visitor quickly understand what makes this business special?
- Value opportunities: "Streamlining your homepage to highlight your top 3 services would help visitors find what they need fast" — tie back to business results
- Quick wins that paint a picture
- Frame each point as a BENEFIT they'd gain, not a problem they have

LANGUAGE RULE — NO TECH JARGON:
- The recipient is a business owner, NOT a web developer. Write like you're explaining to a friend.
- NEVER use terms like: "parked domain", "SSL certificate", "DNS", "redirect loop", "server error", "placeholder page", "meta tags", "SEO", "rendering", "viewport", "responsive", "CMS", "hosting"
- INSTEAD translate to plain English:
  - "parked domain" → "your web address isn't showing your actual business yet — visitors just see a generic page"
  - "SSL certificate expired" → "visitors get a scary security warning before they can even see your site"
  - "site not loading" → "when people go to your website, nothing comes up"
  - "placeholder page" → "your website shows a generic template instead of your actual business"
- Always describe the VISITOR EXPERIENCE, not the technical cause

TONE:
- Lead with what's WORKING, then suggest the upgrade. Acknowledge the good → suggest how to make it even better.
- EXACTLY ONE SENTENCE per issue description. If your description has a period followed by more words, you wrote too much.
- BAD: "Right now visitors see a generic error page instead of your business. That means you're losing every potential customer." (TWO sentences and negative. WRONG.)
- GOOD: "The content is solid; tightening it into scannable sections would help visitors find what they need fast"
- MAX 25 words per issue description. Count them. If over 25, rewrite shorter.
- Frame everything as an OPPORTUNITY to level up, not a problem to fix.
- NEVER speculate about a site that doesn't exist. If the page is parked/blank, just state the problem and a simple next step.
- NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead.

SEVERITY CLASSIFICATION:
- "critical": Issues that directly harm conversions, user trust, or usability RIGHT NOW. Examples: broken navigation, unclear value proposition, mobile rendering issues, outdated/unprofessional design, missing contact information, security warnings, site down.
- "important": Issues that diminish effectiveness but don't completely block results. Examples: slow load times, weak calls-to-action, poor content structure, inconsistent branding.
- Do NOT include minor/nice-to-have issues. Only critical and important.
- A single solid critical issue is better than padding with weak points.

YOUR RESPONSE MUST BE ONLY a valid JSON object, nothing else. No markdown fences, no extra text:
{{"issues": [{{"title": "Brief 5-7 word title", "description": "One sentence, max 25 words, explaining impact on their business", "severity": "critical", "example": "Optional specific example from the site"}}], "recommendation": "One sentence on the most impactful fix"}}

Return exactly 1 issue. Focus on the single most compelling observation. """

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}]
            )
            result = self._parse_analysis_json(message.content[0].text)
            _strip_ai_dashes_from_analysis(result)
            return result
        except Exception as e:
            print(f"Website analysis error: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_analysis_json(raw_text: str) -> dict:
        """Parse structured JSON analysis from model output.

        Returns a dict with 'issues' list and 'recommendation' string.
        Falls back to legacy text format parsing if JSON parsing fails.
        """
        raw = raw_text.strip()
        # Try to extract JSON object
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if 'issues' in data and isinstance(data['issues'], list):
                    for issue in data['issues']:
                        issue.setdefault('severity', 'important')
                        issue.setdefault('title', '')
                        issue.setdefault('description', '')
                    data.setdefault('recommendation', '')
                    return data
            except json.JSONDecodeError:
                pass

        # Fallback: parse legacy "1." format or plain text
        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        for l in lines:
            if l.startswith('1.'):
                text = l[2:].strip()
                return {
                    'issues': [{'title': text[:50], 'description': text, 'severity': 'important', 'example': None}],
                    'recommendation': '',
                }
        # Last resort: use the entire text as the observation
        return {
            'issues': [{'title': raw[:50], 'description': raw, 'severity': 'important', 'example': None}] if raw else [],
            'recommendation': '',
        }

    @staticmethod
    def format_analysis_as_text(analysis: dict) -> str:
        """Convert structured analysis dict to plain text for email templates."""
        if not analysis or not analysis.get('issues'):
            return ''
        # Single observation — no numbering needed
        return analysis['issues'][0].get('description', '')

    @staticmethod
    def get_max_severity(analysis: dict) -> str:
        """Extract the highest severity from analysis issues."""
        if not analysis or not analysis.get('issues'):
            return None
        severities = [i.get('severity', 'important') for i in analysis['issues']]
        if 'critical' in severities:
            return 'critical'
        if 'important' in severities:
            return 'important'
        return None

    def personalize_email(
        self,
        template_subject: str,
        template_body: str,
        recipient: Dict,
        custom_prompt: str = None,
        writing_style: Dict = None,
        campaign_context: str = None,
        website_insights: str = None,
        learned_insights: Dict = None,
        team_contacts: list = None,
    ) -> Dict[str, str]:
        """Generate personalized email using Claude."""

        # Build rich context from custom fields
        custom_fields = recipient.get('custom_fields', {})

        # Extract key founder/business details if present
        context_parts = []

        # Personal context/notes (highest priority - manual research)
        if custom_fields.get('context') or custom_fields.get('notes') or custom_fields.get('research_notes'):
            notes = custom_fields.get('context') or custom_fields.get('notes') or custom_fields.get('research_notes')
            context_parts.append(f"PERSONAL RESEARCH NOTES: {notes}")

        # Role/Title
        if custom_fields.get('title') or custom_fields.get('role') or custom_fields.get('job_title'):
            title = custom_fields.get('title') or custom_fields.get('role') or custom_fields.get('job_title')
            context_parts.append(f"Role: {title}")

        # Industry
        if custom_fields.get('industry') or custom_fields.get('sector'):
            industry = custom_fields.get('industry') or custom_fields.get('sector')
            context_parts.append(f"Industry: {industry}")

        # Company details
        if custom_fields.get('company_size') or custom_fields.get('employees'):
            size = custom_fields.get('company_size') or custom_fields.get('employees')
            context_parts.append(f"Company Size: {size}")

        if custom_fields.get('funding_stage') or custom_fields.get('funding'):
            funding = custom_fields.get('funding_stage') or custom_fields.get('funding')
            context_parts.append(f"Funding Stage: {funding}")

        if custom_fields.get('revenue') or custom_fields.get('arr'):
            revenue = custom_fields.get('revenue') or custom_fields.get('arr')
            context_parts.append(f"Revenue/ARR: {revenue}")

        # Recent activity/news
        if custom_fields.get('recent_news') or custom_fields.get('news'):
            news = custom_fields.get('recent_news') or custom_fields.get('news')
            context_parts.append(f"Recent News: {news}")

        if custom_fields.get('recent_launch') or custom_fields.get('product_launch'):
            launch = custom_fields.get('recent_launch') or custom_fields.get('product_launch')
            context_parts.append(f"Recent Product Launch: {launch}")

        # Pain points/challenges
        if custom_fields.get('pain_points') or custom_fields.get('challenges'):
            pains = custom_fields.get('pain_points') or custom_fields.get('challenges')
            context_parts.append(f"Known Pain Points: {pains}")

        # Social presence
        if custom_fields.get('linkedin') or custom_fields.get('linkedin_url'):
            linkedin = custom_fields.get('linkedin') or custom_fields.get('linkedin_url')
            context_parts.append(f"LinkedIn: {linkedin}")

        if custom_fields.get('twitter') or custom_fields.get('twitter_handle'):
            twitter = custom_fields.get('twitter') or custom_fields.get('twitter_handle')
            context_parts.append(f"Twitter: {twitter}")

        # Mutual connections or referrals
        if custom_fields.get('referral') or custom_fields.get('mutual_connection') or custom_fields.get('referred_by'):
            referral = custom_fields.get('referral') or custom_fields.get('mutual_connection') or custom_fields.get('referred_by')
            context_parts.append(f"Referral/Mutual Connection: {referral}")

        # Previous interactions
        if custom_fields.get('previous_interaction') or custom_fields.get('met_at'):
            interaction = custom_fields.get('previous_interaction') or custom_fields.get('met_at')
            context_parts.append(f"Previous Interaction: {interaction}")

        # Any remaining custom fields
        known_fields = {
            'context', 'notes', 'research_notes', 'title', 'role', 'job_title',
            'industry', 'sector', 'company', 'company_size', 'employees',
            'funding_stage', 'funding', 'revenue', 'arr', 'recent_news', 'news',
            'recent_launch', 'product_launch', 'pain_points', 'challenges',
            'linkedin', 'linkedin_url', 'twitter', 'twitter_handle', 'referral',
            'mutual_connection', 'referred_by', 'previous_interaction', 'met_at',
            'name', 'email', 'website', 'url', 'site', 'website_url',
            'company_url', 'domain', 'company_domain', 'web',
        }
        other_fields = {k: v for k, v in custom_fields.items() if k.lower() not in known_fields and v}
        if other_fields:
            context_parts.append(f"Additional Details: {json.dumps(other_fields)}")

        # Team contacts detected on the recipient's website
        if team_contacts:
            people = ", ".join(f"{c['name']} ({c['role']})" for c in team_contacts)
            context_parts.append(f"TEAM MEMBERS ON THEIR WEBSITE: {people}")

        rich_context = "\n".join(context_parts) if context_parts else "No additional context available"

        # Build writing style instructions
        style_instructions = ""
        if writing_style:
            style_parts = []

            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")

            if writing_style.get('opening_style'):
                style_parts.append(f"OPENING APPROACH: {writing_style['opening_style']}")

            if writing_style.get('value_prop_style'):
                style_parts.append(f"VALUE PROPOSITION STYLE: {writing_style['value_prop_style']}")

            if writing_style.get('length'):
                style_parts.append(f"LENGTH: {writing_style['length']}")

            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING/CTA STYLE: {writing_style['closing_style']}")

            if writing_style.get('phrases_to_use'):
                style_parts.append(f"PHRASES/PATTERNS TO USE: {writing_style['phrases_to_use']}")

            if writing_style.get('phrases_to_avoid'):
                style_parts.append(f"PHRASES TO AVOID: {writing_style['phrases_to_avoid']}")

            if writing_style.get('additional_notes'):
                style_parts.append(f"ADDITIONAL STYLE NOTES: {writing_style['additional_notes']}")

            if style_parts:
                style_instructions = "WRITER'S PERSONAL STYLE (THIS IS CRITICAL - match this voice exactly):\n" + "\n".join(style_parts)

        # Pre-substitute template variables with actual recipient data.
        # Resolve name vs company — handles CSVs where the business name
        # is in the 'name' column and the real contact is elsewhere.
        raw_name = (recipient.get('name') or '').strip()
        cleaned_company = clean_company_name(recipient.get('company', '')) or ''
        recipient_name, cleaned_company = resolve_recipient_fields(
            raw_name, cleaned_company, recipient.get('email', ''), custom_fields
        )

        variable_map = {
            'email': recipient.get('email') or '',
            'company': cleaned_company or 'your company',
            'name': recipient_name or 'there',
        }

        # Add all custom fields as available variables
        for k, v in custom_fields.items():
            if v:
                variable_map[k] = str(v)

        # Handle website_insights separately from the variable_map.
        # When available: pre-substitute directly into the template body.
        # When not available: remove the placeholder entirely and flag it.
        has_website_insights = bool(website_insights)
        template_has_wi_placeholder = '{{website_insights}}' in template_body or '{{ website_insights }}' in template_body

        # Replace {{variable}} placeholders in template
        import re as _re
        def _replace_var(match):
            raw = match.group(1).strip()
            # Support fallback syntax: {{city|state}} tries city first, then state
            for part in raw.split('|'):
                var_name = part.strip()
                # website_insights: pre-substitute directly when available
                if var_name == 'website_insights':
                    if has_website_insights:
                        return website_insights
                    continue
                val = variable_map.get(var_name)
                if val is not None and val != '':
                    return val
            # For any truly missing variable, use empty string —
            # never insert markers that Claude might echo
            return ''

        resolved_subject = _re.sub(r'\{\{([\s\w|]+)\}\}', _replace_var, template_subject)
        resolved_body = _re.sub(r'\{\{([\s\w|]+)\}\}', _replace_var, template_body)

        # Clean up empty lines left by removed placeholders
        resolved_body = _re.sub(r'\n\s*\n\s*\n', '\n\n', resolved_body)

        # Build data-driven insights block
        insights_instructions = ""
        if learned_insights:
            parts = []
            if learned_insights.get('subject_line_patterns'):
                parts.append(f"SUBJECT LINES: {learned_insights['subject_line_patterns']}")
            if learned_insights.get('opening_patterns'):
                parts.append(f"OPENINGS: {learned_insights['opening_patterns']}")
            if learned_insights.get('personalization_depth'):
                parts.append(f"PERSONALIZATION: {learned_insights['personalization_depth']}")
            if learned_insights.get('length_insights'):
                parts.append(f"LENGTH: {learned_insights['length_insights']}")
            if learned_insights.get('cta_patterns'):
                parts.append(f"CALLS TO ACTION: {learned_insights['cta_patterns']}")
            if learned_insights.get('tone_insights'):
                parts.append(f"TONE: {learned_insights['tone_insights']}")
            if learned_insights.get('avoid_patterns'):
                parts.append(f"AVOID: {learned_insights['avoid_patterns']}")
            if parts:
                confidence = learned_insights.get('confidence', 'medium')
                insights_instructions = (
                    f"DATA-DRIVEN INSIGHTS (learned from analyzing which of your emails actually get replies — "
                    f"confidence: {confidence} — apply these patterns):\n" + "\n".join(parts)
                )

        # Build website observations note outside f-string (Python 3.9 doesn't allow backslashes in f-string expressions)
        if website_insights:
            _wi_note = (
                "WEBSITE OBSERVATION NOTE: The template body already contains a website observation "
                "(pre-filled from analysis). Rewrite it in your own words so it sounds natural and "
                "conversational. It should show the VALUE of improving (more customers, more trust, "
                "stronger first impression). Keep it in the same position in the email."
            )
        else:
            _wi_note = ""

        # Build team contact note outside f-string (Python 3.9 backslash restriction)
        _team_note = ""
        if team_contacts:
            people = ", ".join(f"{c['name']} ({c['role']})" for c in team_contacts)
            _team_note = (
                "TEAM CONTACT DETECTED: We found these people on their website "
                "who handle marketing or related work: " + people + "\n"
                "If their role is relevant to the service being offered (e.g. you offer "
                "web design and they have a Marketing Manager), casually reference them "
                "by first name in the email. For example: 'I'm sure [Name] has thought "
                "about this...' or 'This might be something [Name] would find interesting.' "
                "Keep it natural, not stalkerish. Only mention them if their role clearly "
                "connects to what you're offering. If the connection is weak, skip it."
            )

        prompt = f"""You are ghostwriting personalized outreach emails for a specific person. Your job is to write exactly like them - matching their voice, tone, and style perfectly.

{style_instructions if style_instructions else "Write in a casual but professional tone. Keep it brief and human."}

{insights_instructions}

RECIPIENT PROFILE:
- Name: {recipient_name or 'there'}
- Email: {recipient.get('email')}
- Company: {cleaned_company or 'unknown'}

RICH CONTEXT (use this to personalize):
{rich_context}

TEMPLATE TO PERSONALIZE (variables have been pre-filled where data was available):
Subject: {resolved_subject}
Body:
{resolved_body}

TEMPLATE STRUCTURE RULE (THIS IS THE MOST IMPORTANT RULE):
- PRESERVE the template's exact paragraph structure, flow, and sequence
- Each paragraph/section of the template must appear in the same order in the output
- Pre-filled content (where variables were replaced with real data) should stay IN PLACE — do not move it to a different paragraph or rewrite around it
- You may lightly adjust wording for natural flow, but the skeleton of the template MUST remain intact
- If there is a section with website insights or bullet points, keep it exactly where it appears in the template — do not relocate that content to the opening or anywhere else
- Think of yourself as filling in a form, not rewriting a letter


STYLE REQUIREMENTS:
1. Match the writer's personal style EXACTLY
2. Use specific details from the research notes to show genuine interest
3. Keep the tone casual and human
4. Lead with VALUE — show what's possible for their business, not what's wrong with it
5. Every observation should tie back to a business benefit (more customers, more trust, stronger brand)
6. Close casually, not with aggressive sales language
7. NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

GREETING RULE (CRITICAL):
- The greeting must use the recipient's PERSONAL first name (e.g. "Hi Sarah,")
- If the name is "there" or looks like a company/business name (e.g. "B & L Glass", "Home at Home"), use "Hi there," instead
- NEVER greet someone by their company name. "Hi B & L Glass," is wrong. "Hi there," is correct.
- Company names typically contain: LLC, Inc, Corp, Co, Glass, Home, Services, Solutions, Group, Agency, Studio, etc.

ABSOLUTE RULE - NEVER FABRICATE:
- ONLY reference facts explicitly provided in the context above
- NEVER invent meetings, events, mutual connections, or interactions that aren't in the data
- If context is limited, keep the email genuine but more general — don't fill gaps with fiction

HUMILITY RULE:
- NEVER try to sound smarter than the recipient about their own business
- NEVER contradict what their website clearly states (e.g. don't say "visitors won't know what you do" if the site explains it)
- NEVER call their tagline, slogan, or headline "generic" if it contains their company name or a play on it. Businesses use puns and wordplay in branding (e.g. "Abodie" → "Your Humble Abodie Awaits"). Criticizing branded wordplay shows you didn't understand their name.
- NEVER imply the business might be inactive, closed, or not booking — directly or indirectly. Phrases like "visitors might wonder if you're still taking on projects" or "homeowners may question if you're still in business" are just as insulting as saying it yourself. The business IS active. Focus on helping them look their best, not casting doubt.
- Show you've done homework, but stay humble — they're the expert
- Keep observations respectful and accurate. When in doubt, acknowledge what they're doing well before suggesting opportunities

NO TECH JARGON RULE:
- Write for a business owner, NOT a developer. Zero technical terms.
- NEVER say: "parked domain", "SSL", "DNS", "redirect", "server error", "placeholder", "meta tags", "SEO", "rendering", "responsive", "CMS", "hosting"
- Describe problems as the VISITOR EXPERIENCE: "when someone visits your site, they see a generic page instead of your business" — not "your domain is parked"
- If the website observations contain technical language, REWRITE them in plain English in the final email

COPYRIGHT YEAR RULE:
- NEVER mention a specific copyright year in the email (e.g. "your copyright says 2016"). Copyright years in website analysis are often misread and citing them makes you look careless.
- If the research notes mention an outdated design or dated feel, say the site "looks like it could use a refresh" or "the design feels a few years behind" — never cite a year.

{_wi_note}

{_team_note}

{f"CAMPAIGN MUST-INCLUDE (weave this into EVERY email naturally): {campaign_context}" if campaign_context else ""}

{f"SPECIAL INSTRUCTIONS (these are meta-instructions about how to write the email — use them to guide your tone/approach, but do NOT insert this text verbatim into the email body): {custom_prompt}" if custom_prompt else ""}

IMPORTANT: Return ONLY valid JSON in this exact format, nothing else:
{{"subject": "personalized subject line", "body": "personalized email body"}}
"""

        # Build content warnings for the caller
        content_warnings = []
        if template_has_wi_placeholder and not has_website_insights:
            content_warnings.append('Website insights unavailable — observations section removed from email')

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                body = _strip_ai_dashes(result.get('body', resolved_body))
                # Strip business suffixes (LLC, Inc, etc.) from body too
                body = re.sub(
                    r'[,\s]+(LLC|L\.L\.C\.|INC\.?|INCORPORATED|CORP\.?|CORPORATION|LTD\.?|LIMITED|PLLC)\b\.?',
                    '', body, flags=re.IGNORECASE
                )

                # Normalize line breaks for HTML rendering:
                # 1. Convert any remaining \n to <br> (model may return mixed formats)
                if '<p' not in body:
                    body = body.replace('\n', '<br>')
                # 2. Strip whitespace between <br> tags so they're adjacent for collapsing
                body = re.sub(r'(<br\s*/?\s*>)\s+(?=<br)', r'\1', body)
                # 3. Collapse runs of 3+ <br> tags down to 2 (one blank line max)
                body = re.sub(r'(<br\s*/?\s*>){3,}', '<br><br>', body)

                subject = _strip_ai_dashes(result.get('subject', resolved_subject))
                # Strip business suffixes (LLC, Inc, etc.) that may have leaked into the subject
                subject = re.sub(
                    r'[,\s]+(LLC|L\.L\.C\.|INC\.?|INCORPORATED|CORP\.?|CORPORATION|LTD\.?|LIMITED|PLLC)\b\.?',
                    '', subject, flags=re.IGNORECASE
                )
                out = {
                    'subject': subject,
                    'body': body
                }
                if content_warnings:
                    out['content_warnings'] = content_warnings
                return out

            # Fallback if JSON parsing fails — return resolved template (variables filled in)
            print(f"JSON parse failed, returning resolved template. Response was: {response_text[:200]}")
            out = {
                'subject': resolved_subject,
                'body': resolved_body
            }
            if content_warnings:
                out['content_warnings'] = content_warnings
            return out

        except Exception as e:
            print(f"Claude API error: {e}")
            # Even on error, return the resolved template so variables are filled in
            out = {
                'subject': resolved_subject,
                'body': resolved_body
            }
            if content_warnings:
                out['content_warnings'] = content_warnings
            return out

    def generate_email(
        self,
        recipient: Dict,
        context: str,
        tone: str = 'professional'
    ) -> Dict[str, str]:
        """Generate a completely new email for a recipient."""

        company = clean_company_name(recipient.get('company', '')) or 'their company'

        prompt = f"""Write a {tone} outreach email for:

RECIPIENT:
- Name: {recipient.get('name') or 'there'}
- Company: {company}
- Details: {json.dumps(recipient.get('custom_fields', {}))}

CONTEXT/PURPOSE:
{context}

IMPORTANT STYLE RULES:
- NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead.
- Sound human and natural, not AI-generated.

Return ONLY valid JSON:
{{"subject": "email subject", "body": "email body"}}
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': _strip_ai_dashes(result.get('subject', '')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'subject': 'Hello', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Claude API error: {e}")
            raise

    def generate_template(
        self,
        purpose: str,
        target_audience: str = None,
        tone: str = "professional but casual",
        key_points: str = None,
        call_to_action: str = None,
        length: str = "short"
    ) -> Dict[str, str]:
        """Generate a reusable email template using Claude."""

        prompt = f"""Create a reusable email template for outreach campaigns.

PURPOSE/GOAL:
{purpose}

{f"TARGET AUDIENCE: {target_audience}" if target_audience else ""}

TONE: {tone}

{f"KEY POINTS TO INCLUDE: {key_points}" if key_points else ""}

{f"CALL TO ACTION: {call_to_action}" if call_to_action else ""}

LENGTH: {length} (short = 2-3 sentences, medium = 4-5 sentences, long = 6+ sentences)

TEMPLATE REQUIREMENTS:
1. Use {{{{name}}}} for recipient's first name
2. Use {{{{company}}}} for recipient's company name
3. You can also use other variables like {{{{title}}}}, {{{{industry}}}}, etc. where appropriate
4. Make it feel personal, not like a mass email
5. Keep the subject line compelling and under 50 characters
6. Don't use cliché phrases like "I hope this email finds you well"
7. Lead with genuine interest in them — show you care about their work
8. Frame any suggestions as opportunities, not problems
9. End with a clear but soft call to action — friendly, not pushy
10. NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

Return ONLY valid JSON in this exact format:
{{"name": "template name (2-4 words)", "subject": "email subject line with {{{{company}}}} variable if relevant", "body": "email body with {{{{name}}}} and {{{{company}}}} variables"}}
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'name': result.get('name', 'Generated Template'),
                    'subject': _strip_ai_dashes(result.get('subject', '')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'name': 'Generated Template', 'subject': '', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Claude API error: {e}")
            raise

    def refine_template(
        self,
        current_subject: str,
        current_body: str,
        current_name: str,
        feedback: str,
        original_purpose: str = None
    ) -> Dict[str, str]:
        """Refine an existing template based on user feedback."""

        prompt = f"""You previously generated this email template. The user wants changes.

CURRENT TEMPLATE:
Name: {current_name}
Subject: {current_subject}
Body:
{current_body}

{f"ORIGINAL PURPOSE: {original_purpose}" if original_purpose else ""}

USER FEEDBACK (apply these changes):
{feedback}

RULES:
1. Keep {{{{name}}}}, {{{{company}}}}, and other template variables intact
2. Apply the feedback precisely — don't change things the user didn't ask about
3. If the feedback is about tone, adjust tone throughout
4. If the feedback is about length, adjust accordingly
5. If the feedback asks to add/remove content, do exactly that
6. Keep the template feeling personal and human
7. NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

Return ONLY valid JSON in this exact format:
{{"name": "template name", "subject": "updated subject line", "body": "updated email body"}}
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'name': result.get('name', current_name),
                    'subject': _strip_ai_dashes(result.get('subject', current_subject)),
                    'body': _strip_ai_dashes(result.get('body', current_body))
                }

            return {'name': current_name, 'subject': current_subject, 'body': current_body}

        except Exception as e:
            print(f"Claude API error: {e}")
            raise

    def generate_quick_email(
        self,
        recipient: Dict,
        context: str,
        writing_style: str = None,
        learned_insights: Dict = None
    ) -> Dict[str, str]:
        """Generate a quick one-off email with writing style support."""

        # Parse writing style if it's a JSON string
        style_dict = None
        if writing_style:
            try:
                style_dict = json.loads(writing_style) if isinstance(writing_style, str) else writing_style
            except:
                pass

        # Build writing style instructions
        style_instructions = ""
        if style_dict:
            style_parts = []
            if style_dict.get('tone'):
                style_parts.append(f"TONE: {style_dict['tone']}")
            if style_dict.get('opening_style'):
                style_parts.append(f"OPENING APPROACH: {style_dict['opening_style']}")
            if style_dict.get('value_prop_style'):
                style_parts.append(f"VALUE PROPOSITION STYLE: {style_dict['value_prop_style']}")
            if style_dict.get('length'):
                style_parts.append(f"LENGTH: {style_dict['length']}")
            if style_dict.get('closing_style'):
                style_parts.append(f"CLOSING/CTA STYLE: {style_dict['closing_style']}")
            if style_dict.get('phrases_to_use'):
                style_parts.append(f"PHRASES/PATTERNS TO USE: {style_dict['phrases_to_use']}")
            if style_dict.get('phrases_to_avoid'):
                style_parts.append(f"PHRASES TO AVOID: {style_dict['phrases_to_avoid']}")
            if style_dict.get('additional_notes'):
                style_parts.append(f"ADDITIONAL STYLE NOTES: {style_dict['additional_notes']}")
            if style_parts:
                style_instructions = "WRITER'S PERSONAL STYLE (match this voice exactly):\n" + "\n".join(style_parts)

        # Build data-driven insights block for quick email
        insights_instructions = ""
        if learned_insights:
            li_parts = []
            if learned_insights.get('subject_line_patterns'):
                li_parts.append(f"SUBJECT LINES: {learned_insights['subject_line_patterns']}")
            if learned_insights.get('opening_patterns'):
                li_parts.append(f"OPENINGS: {learned_insights['opening_patterns']}")
            if learned_insights.get('personalization_depth'):
                li_parts.append(f"PERSONALIZATION: {learned_insights['personalization_depth']}")
            if learned_insights.get('length_insights'):
                li_parts.append(f"LENGTH: {learned_insights['length_insights']}")
            if learned_insights.get('cta_patterns'):
                li_parts.append(f"CALLS TO ACTION: {learned_insights['cta_patterns']}")
            if learned_insights.get('tone_insights'):
                li_parts.append(f"TONE: {learned_insights['tone_insights']}")
            if learned_insights.get('avoid_patterns'):
                li_parts.append(f"AVOID: {learned_insights['avoid_patterns']}")
            if li_parts:
                confidence = learned_insights.get('confidence', 'medium')
                insights_instructions = (
                    f"DATA-DRIVEN INSIGHTS (learned from analyzing which of your emails actually get replies — "
                    f"confidence: {confidence} — apply these patterns):\n" + "\n".join(li_parts)
                )

        prompt = f"""You are ghostwriting a personalized outreach email. Write exactly like the person whose style is described below.

{style_instructions if style_instructions else "Write in a casual but professional tone. Keep it brief and human."}

{insights_instructions}

RECIPIENT:
- Name: {recipient.get('name') or 'there'}
- Email: {recipient.get('email')}
- Company: {clean_company_name(recipient.get('company', '')) or 'their company'}
- Research Notes: {recipient.get('notes') or 'None provided'}

PURPOSE/CONTEXT:
{context or 'General outreach'}

CRITICAL REQUIREMENTS:
1. Match the writer's personal style EXACTLY
2. Use specific details from research notes if provided
3. Keep it the specified length (default: 2-4 sentences)
4. Sound human, not like a mass email
5. Lead with genuine interest in THEIR work — acknowledge what they're building
6. Show the VALUE you can bring — paint a picture of how their business benefits (more customers, stronger online presence, more trust from visitors)
7. Close casually and warmly, not aggressively
8. NEVER use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

TONE GUIDANCE:
- Be friendly and respectful — you're reaching out to help them grow, not to point out problems
- Always tie suggestions to business outcomes: "could help you get more leads", "give homeowners confidence to call"
- Focus on what's POSSIBLE for them, not what's currently wrong
- Sound like a helpful neighbor who sees potential, not a salesperson looking for flaws

ABSOLUTE RULES:
- NEVER fabricate facts, meetings, or connections not in the notes
- NEVER claim expertise in their industry — stay humble and curious
- NEVER just point out a problem — always pair it with the benefit of fixing it
- NEVER use tech jargon — no "parked domain", "SSL", "DNS", "server error", "placeholder", "SEO", "rendering", "CMS". Describe what a VISITOR experiences in plain English: "your web address shows a generic page instead of your business" not "your domain is parked"
- If context is limited, keep it genuine but general
- Better to be vague than to lie

Return ONLY valid JSON:
{{"subject": "email subject line", "body": "email body"}}
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': _strip_ai_dashes(result.get('subject', '')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'subject': 'Quick note', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Claude API error: {e}")
            raise

    def classify_sentiment(
        self,
        original_subject: str,
        original_body: str,
        reply_text: str,
    ) -> Dict:
        """Classify a reply's sentiment as positive, negative, or neutral."""

        prompt = f"""You are analyzing a reply to a cold outreach email. Classify the reply sentiment.

ORIGINAL EMAIL SENT:
Subject: {original_subject}
Body: {original_body}

THEIR REPLY:
{reply_text}

CLASSIFICATION RULES:
- POSITIVE: They express interest, ask questions about services, want to learn more, suggest meeting, say nice things about the offer
- NEGATIVE: They say not interested, ask to be removed, decline, express annoyance, say they already have someone
- NEUTRAL: Out of office, auto-reply, vague acknowledgment, asks a clarifying question without clear interest direction

Return ONLY valid JSON:
{{"sentiment": "positive" or "negative" or "neutral", "reason": "one sentence explaining why"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {'sentiment': 'neutral', 'reason': 'Could not classify'}

        except Exception as e:
            print(f"Sentiment classification error: {e}")
            return None

    def generate_rebuttal(
        self,
        original_subject: str,
        original_body: str,
        reply_text: str,
        contact_info: Dict,
        writing_style: Dict = None,
    ) -> Dict[str, str]:
        """Generate a warm, relationship-building response to a not-interested reply."""

        style_instructions = ""
        if writing_style:
            style_parts = []
            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")
            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING STYLE: {writing_style['closing_style']}")
            if style_parts:
                style_instructions = "WRITER'S STYLE:\n" + "\n".join(style_parts)

        contact_name = contact_info.get('name') or 'there'
        contact_company = contact_info.get('company') or 'their company'

        prompt = f"""You are ghostwriting a reply to someone who responded to a cold outreach email. They are NOT interested (or at least not right now). Your job is to write a response that makes them glad they replied — one that builds a genuine human connection.

{style_instructions if style_instructions else "Write in a casual, warm, genuine tone."}

THE ORIGINAL EMAIL WE SENT:
Subject: {original_subject}
Body: {original_body}

THEIR REPLY:
{reply_text}

ABOUT THEM:
- Name: {contact_name}
- Company: {contact_company}

YOUR RESPONSE MUST:
1. Acknowledge their reply with genuine warmth — thank them for taking the time
2. Completely respect their decision — zero pushback, zero objection handling
3. If possible, offer something genuinely useful with NO strings attached — a quick tip about their website, an industry insight, a resource they might find helpful. Something that shows you actually care, not that you're trying to stay in their inbox
4. Close warmly and briefly — leave the door open naturally, like you would with a neighbor ("If anything ever comes up, I'm around")
5. Keep it SHORT — 2-3 sentences max. Don't over-explain or over-apologize

YOUR RESPONSE MUST NOT:
- Try to overcome their objection in any way
- Pitch again or mention your services
- Ask for a referral or introduction
- Say "I understand" then pivot to another angle
- Use phrases like "just in case", "when you're ready", "circle back"
- Sound like a sales playbook — sound like a human being
- Use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

THE GOAL: If they read your reply, they should think "that was actually really nice" — not "they're still trying to sell me."

Return ONLY valid JSON:
{{"subject": "Re: {original_subject}", "body": "your response"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': _strip_ai_dashes(result.get('subject', f'Re: {original_subject}')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'subject': f'Re: {original_subject}', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Rebuttal generation error: {e}")
            raise

    def generate_meeting_followup(
        self,
        original_subject: str,
        original_body: str,
        reply_text: str,
        contact_info: Dict,
        available_slots: list,
        writing_style: Dict = None,
    ) -> Dict[str, str]:
        """Generate a follow-up proposing meeting times for a positive reply."""

        style_instructions = ""
        if writing_style:
            style_parts = []
            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")
            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING STYLE: {writing_style['closing_style']}")
            if style_parts:
                style_instructions = "WRITER'S STYLE:\n" + "\n".join(style_parts)

        slot_text = ""
        if available_slots:
            slot_lines = []
            for slot in available_slots[:5]:
                slot_lines.append(f"- {slot.get('display', slot.get('start', 'TBD'))}")
            slot_text = "\n".join(slot_lines)
        else:
            slot_text = "No specific calendar slots available — suggest they pick a time that works."

        contact_name = contact_info.get('name') or 'there'
        contact_company = contact_info.get('company') or 'their company'

        prompt = f"""You are ghostwriting a reply to someone who responded POSITIVELY to a cold outreach email. They're interested! Your job is to move toward a meeting naturally.

{style_instructions if style_instructions else "Write in a casual, warm, professional tone."}

THE ORIGINAL EMAIL WE SENT:
Subject: {original_subject}
Body: {original_body}

THEIR POSITIVE REPLY:
{reply_text}

ABOUT THEM:
- Name: {contact_name}
- Company: {contact_company}

AVAILABLE TIME SLOTS:
{slot_text}

YOUR RESPONSE MUST:
1. Match their energy — if they're enthusiastic, be warm and excited. If they're measured, stay professional
2. Briefly acknowledge what they said — show you read their reply
3. Propose 2-3 specific time slots in a natural, human-readable way (e.g., "How about Tuesday the 14th around 2pm, or Thursday morning?")
4. Make it easy to say yes — "Just let me know what works and I'll send over a calendar invite"
5. Keep it SHORT and action-oriented — 3-4 sentences max

YOUR RESPONSE MUST NOT:
- Over-explain what the meeting will cover
- List times in a rigid/robotic format
- Sound overly excited or desperate
- Use corporate phrases like "let's find synergies" or "I'd love to explore"
- Use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

Return ONLY valid JSON:
{{"subject": "Re: {original_subject}", "body": "your response"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': _strip_ai_dashes(result.get('subject', f'Re: {original_subject}')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'subject': f'Re: {original_subject}', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Meeting followup generation error: {e}")
            raise

    def generate_sequence_followup(
        self,
        step_number: int,
        original_subject: str,
        conversation_history: list,
        contact_info: Dict,
        ai_prompt: str = None,
        campaign_context: str = None,
        web_research: str = None,
        writing_style: Dict = None,
        learned_insights: Dict = None,
    ) -> Dict[str, str]:
        """Generate a follow-up email for a multi-step campaign sequence.

        Takes full conversation history, optional web research, and adjusts
        tone based on step number (later steps = shorter/more casual).
        """
        # Build conversation history block
        history_block = ""
        for i, msg in enumerate(conversation_history, 1):
            history_block += f"\n--- Email #{i} (sent {msg.get('sent_at', 'unknown')}) ---\n"
            history_block += f"Subject: {msg['subject']}\n"
            history_block += f"Body: {msg['body']}\n"

        # Build web research block
        research_block = ""
        if web_research:
            research_block = f"""
WEB RESEARCH (recent information about their company/industry — use this to add VALUE):
{web_research}

Use this research to mention something timely and relevant — a recent development,
industry trend, or company news that connects naturally to your follow-up.
Do NOT dump all the research into the email. Pick ONE relevant detail.
"""

        # Build writing style instructions
        style_instructions = ""
        if writing_style:
            style_parts = []
            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")
            if writing_style.get('opening_style'):
                style_parts.append(f"OPENING APPROACH: {writing_style['opening_style']}")
            if writing_style.get('length'):
                style_parts.append(f"LENGTH: {writing_style['length']}")
            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING/CTA STYLE: {writing_style['closing_style']}")
            if writing_style.get('phrases_to_use'):
                style_parts.append(f"PHRASES/PATTERNS TO USE: {writing_style['phrases_to_use']}")
            if writing_style.get('phrases_to_avoid'):
                style_parts.append(f"PHRASES TO AVOID: {writing_style['phrases_to_avoid']}")
            if style_parts:
                style_instructions = "WRITER'S PERSONAL STYLE (match this voice exactly):\n" + "\n".join(style_parts)

        # Build data-driven insights block
        insights_instructions = ""
        if learned_insights:
            li_parts = []
            if learned_insights.get('subject_line_patterns'):
                li_parts.append(f"SUBJECT LINES: {learned_insights['subject_line_patterns']}")
            if learned_insights.get('opening_patterns'):
                li_parts.append(f"OPENINGS: {learned_insights['opening_patterns']}")
            if learned_insights.get('cta_patterns'):
                li_parts.append(f"CALLS TO ACTION: {learned_insights['cta_patterns']}")
            if learned_insights.get('avoid_patterns'):
                li_parts.append(f"AVOID: {learned_insights['avoid_patterns']}")
            if li_parts:
                confidence = learned_insights.get('confidence', 'medium')
                insights_instructions = (
                    f"DATA-DRIVEN INSIGHTS (confidence: {confidence}):\n" + "\n".join(li_parts)
                )

        contact_name = contact_info.get('name') or 'there'
        contact_company = contact_info.get('company') or 'their company'

        prompt = f"""You are ghostwriting follow-up #{step_number} in a multi-step outreach sequence.
This is NOT the first time reaching out — there have been {len(conversation_history)} previous email(s) in this thread.

{style_instructions if style_instructions else "Write in a casual, warm, genuine tone."}

{insights_instructions}

PREVIOUS EMAILS IN THIS THREAD:
{history_block}

ABOUT THEM:
- Name: {contact_name}
- Company: {contact_company}
{research_block}
{f'CAMPAIGN CONTEXT: {campaign_context}' if campaign_context else ''}
{f'SPECIAL INSTRUCTIONS: {ai_prompt}' if ai_prompt else ''}

FOLLOW-UP #{step_number} RULES:
1. This goes in the SAME email thread — do NOT re-introduce yourself or repeat your pitch
2. Each follow-up must add NEW value — never just "checking in"
3. Step 2: Light nudge with one new angle or insight
4. Step 3+: Even shorter, more casual, possibly a simple question
5. Reference something specific from the research if available
6. Max 2-3 sentences. Brevity increases with each step.
7. Never guilt-trip about not replying
8. No "circling back", "bumping this", "just following up" — find a more natural way

ABSOLUTE RULES:
- NEVER fabricate facts, meetings, or connections
- NEVER use tech jargon — write for a business owner
- Sound human, not automated

Return ONLY valid JSON:
{{"subject": "Re: {original_subject}", "body": "your follow-up"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': result.get('subject', f'Re: {original_subject}'),
                    'body': result.get('body', ''),
                }

            return {'subject': f'Re: {original_subject}', 'body': response_text}

        except Exception as e:
            print(f"Sequence follow-up generation error: {e}")
            raise

    def generate_sequence_followup(
        self,
        step_number: int,
        original_subject: str,
        conversation_history: list,
        contact_info: Dict,
        ai_prompt: str = None,
        campaign_context: str = None,
        web_research: str = None,
        writing_style: Dict = None,
        learned_insights: Dict = None,
    ) -> Dict[str, str]:
        """Generate a follow-up email for a multi-step campaign sequence.

        Takes full conversation history, optional web research, and adjusts
        tone based on step number (later steps = shorter/more casual).
        """
        # Build conversation history block
        history_block = ""
        for i, msg in enumerate(conversation_history, 1):
            history_block += f"\n--- Email #{i} (sent {msg.get('sent_at', 'unknown')}) ---\n"
            history_block += f"Subject: {msg['subject']}\n"
            history_block += f"Body: {msg['body']}\n"

        # Build web research block
        research_block = ""
        if web_research:
            research_block = f"""
WEB RESEARCH (recent information about their company/industry — use this to add VALUE):
{web_research}

Use this research to mention something timely and relevant — a recent development,
industry trend, or company news that connects naturally to your follow-up.
Do NOT dump all the research into the email. Pick ONE relevant detail.
"""

        # Build writing style instructions
        style_instructions = ""
        if writing_style:
            style_parts = []
            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")
            if writing_style.get('opening_style'):
                style_parts.append(f"OPENING APPROACH: {writing_style['opening_style']}")
            if writing_style.get('length'):
                style_parts.append(f"LENGTH: {writing_style['length']}")
            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING/CTA STYLE: {writing_style['closing_style']}")
            if writing_style.get('phrases_to_use'):
                style_parts.append(f"PHRASES/PATTERNS TO USE: {writing_style['phrases_to_use']}")
            if writing_style.get('phrases_to_avoid'):
                style_parts.append(f"PHRASES TO AVOID: {writing_style['phrases_to_avoid']}")
            if style_parts:
                style_instructions = "WRITER'S PERSONAL STYLE (match this voice exactly):\n" + "\n".join(style_parts)

        # Build data-driven insights block
        insights_instructions = ""
        if learned_insights:
            li_parts = []
            if learned_insights.get('subject_line_patterns'):
                li_parts.append(f"SUBJECT LINES: {learned_insights['subject_line_patterns']}")
            if learned_insights.get('opening_patterns'):
                li_parts.append(f"OPENINGS: {learned_insights['opening_patterns']}")
            if learned_insights.get('cta_patterns'):
                li_parts.append(f"CALLS TO ACTION: {learned_insights['cta_patterns']}")
            if learned_insights.get('avoid_patterns'):
                li_parts.append(f"AVOID: {learned_insights['avoid_patterns']}")
            if li_parts:
                confidence = learned_insights.get('confidence', 'medium')
                insights_instructions = (
                    f"DATA-DRIVEN INSIGHTS (confidence: {confidence}):\n" + "\n".join(li_parts)
                )

        contact_name = contact_info.get('name') or 'there'
        contact_company = contact_info.get('company') or 'their company'

        prompt = f"""You are ghostwriting follow-up #{step_number} in a multi-step outreach sequence.
This is NOT the first time reaching out — there have been {len(conversation_history)} previous email(s) in this thread.

{style_instructions if style_instructions else "Write in a casual, warm, genuine tone."}

{insights_instructions}

PREVIOUS EMAILS IN THIS THREAD:
{history_block}

ABOUT THEM:
- Name: {contact_name}
- Company: {contact_company}
{research_block}
{f'CAMPAIGN CONTEXT: {campaign_context}' if campaign_context else ''}
{f'SPECIAL INSTRUCTIONS: {ai_prompt}' if ai_prompt else ''}

FOLLOW-UP #{step_number} RULES:
1. This goes in the SAME email thread — do NOT re-introduce yourself or repeat your pitch
2. Each follow-up must add NEW value — never just "checking in"
3. Step 2: Light nudge with one new angle or insight
4. Step 3+: Even shorter, more casual, possibly a simple question
5. Reference something specific from the research if available
6. Max 2-3 sentences. Brevity increases with each step.
7. Never guilt-trip about not replying
8. No "circling back", "bumping this", "just following up" — find a more natural way

ABSOLUTE RULES:
- NEVER fabricate facts, meetings, or connections
- NEVER use tech jargon — write for a business owner
- Sound human, not automated

Return ONLY valid JSON:
{{"subject": "Re: {original_subject}", "body": "your follow-up"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': result.get('subject', f'Re: {original_subject}'),
                    'body': result.get('body', ''),
                }

            return {'subject': f'Re: {original_subject}', 'body': response_text}

        except Exception as e:
            print(f"Sequence follow-up generation error: {e}")
            raise

    def generate_followup_email(
        self,
        original_subject: str,
        original_body: str,
        contact_info: Dict,
        follow_up_note: str = None,
        days_since_last: int = None,
        writing_style: Dict = None,
    ) -> Dict[str, str]:
        """Generate a natural follow-up email for a contact who hasn't replied."""

        style_instructions = ""
        if writing_style:
            style_parts = []
            if writing_style.get('tone'):
                style_parts.append(f"TONE: {writing_style['tone']}")
            if writing_style.get('closing_style'):
                style_parts.append(f"CLOSING STYLE: {writing_style['closing_style']}")
            if style_parts:
                style_instructions = "WRITER'S STYLE:\n" + "\n".join(style_parts)

        contact_name = contact_info.get('name') or 'there'
        contact_company = contact_info.get('company') or 'their company'
        days_context = f"\nIt's been about {days_since_last} days since the original email." if days_since_last else ""
        note_context = f"\nFOLLOW-UP CONTEXT (your note to yourself about why you're following up): {follow_up_note}" if follow_up_note else ""

        prompt = f"""You are ghostwriting a follow-up email to someone who hasn't replied to your original outreach. This is a gentle check-in, NOT a second pitch.

{style_instructions if style_instructions else "Write in a casual, warm, genuine tone."}

THE ORIGINAL EMAIL YOU SENT:
Subject: {original_subject}
Body: {original_body}

ABOUT THEM:
- Name: {contact_name}
- Company: {contact_company}{days_context}{note_context}

YOUR FOLLOW-UP MUST:
1. Be SHORT — 2-3 sentences max. Busy people appreciate brevity
2. Acknowledge they're busy — don't guilt them for not replying
3. Add something NEW of value — don't just say "circling back." Give them a reason to engage: a quick insight, a relevant observation, or a simple question
4. Keep it human and light — like texting a friend you haven't heard from
5. One clear, easy-to-answer question or soft CTA at the end

YOUR FOLLOW-UP MUST NOT:
- Repeat the original pitch verbatim
- Say "just following up" or "circling back" or "bumping this" — find a more natural way
- Sound passive-aggressive about them not replying
- Be longer than the original email
- Include multiple questions or CTAs
- Use guilt language ("I noticed you didn't respond", "still haven't heard back")
- Use em dashes (—), en dashes (–), or double hyphens (--). Use commas, periods, or semicolons instead. Dashes are a telltale sign of AI-generated text.

THE GOAL: They should feel like this is a helpful nudge from someone genuine, not another automated follow-up. If they're going to reply to anything, make it this.

Return ONLY valid JSON:
{{"subject": "Re: {original_subject}", "body": "your follow-up"}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'subject': _strip_ai_dashes(result.get('subject', f'Re: {original_subject}')),
                    'body': _strip_ai_dashes(result.get('body', ''))
                }

            return {'subject': f'Re: {original_subject}', 'body': _strip_ai_dashes(response_text)}

        except Exception as e:
            print(f"Follow-up generation error: {e}")
            raise
