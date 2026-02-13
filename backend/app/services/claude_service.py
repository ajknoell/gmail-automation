from anthropic import Anthropic
from typing import Dict
import json
import re

class ClaudeService:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def analyze_website(self, website_text: str, company_name: str, url: str) -> str:
        """Analyze a website and return 2 specific improvement observations for outreach emails."""
        prompt = f"""You're a web designer who genuinely wants to help a potential client. Find 2 opportunities where a small improvement to their site could bring them more customers, more trust, or a stronger first impression. These go into a friendly cold outreach email — the goal is to show the VALUE of what better looks like, not to point out what's wrong.

COMPANY: {company_name}
URL: {url}

SCRAPED TEXT (raw HTML text extraction — NOT what a visitor actually sees):
{website_text}

CRITICAL CONTEXT: This text was scraped from the raw HTML source. Many sites use JavaScript to render, so the raw text may look content-rich even when the actual site is completely broken for visitors. You must read between the lines.

RED FLAGS THAT THE SITE IS BROKEN/NON-FUNCTIONAL (check these FIRST):
- Counters or stats showing "0" — means the JavaScript animations never fire, so the page isn't rendering properly
- A jumble of navigation labels, headings, and body text all mashed together with no clear page structure — means the layout isn't loading
- Content that reads like a template dump (every section present but no visual hierarchy) — the site framework exists but isn't working
- If you see these signs, the #1 issue is: the site isn't loading properly for visitors. Frame it helpfully, not harshly.

IF THE SITE APPEARS FUNCTIONAL, then look for:
- Value opportunities: "Adding X could help you convert more visitors into calls" — always tie back to business results
- Quick wins that paint a picture: "A gallery showcasing your best work could help homeowners feel confident hiring you"
- Frame each point as a BENEFIT they'd gain, not a problem they have

TONE:
- Helpful and respectful — like a neighbor who happens to be a web designer
- ALWAYS lead with the benefit: "Imagine if visitors could see your best projects right when they land" — paint the picture of what's possible
- Never just name a problem — name the OUTCOME of fixing it: more calls, more trust, more customers
- Avoid words like "broken", "failing", "terrible", "nobody", "zero", "missing", "lacking"
- Show you see the potential in their business and want to help them unlock it
- One sentence each, max 25 words
- Warm and conversational

YOUR RESPONSE MUST BE EXACTLY 2 LINES, NOTHING ELSE:
1.
2. """

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            # Parse out the 2 numbered items, rebuilding cleanly
            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            result_lines = []
            for l in lines:
                if l.startswith('1.') or l.startswith('2.'):
                    result_lines.append(l)
            if len(result_lines) >= 2:
                return result_lines[0] + '\n' + result_lines[1]
            return raw
        except Exception as e:
            print(f"Website analysis error: {e}")
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
        learned_insights: Dict = None
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
            'industry', 'sector', 'company_size', 'employees', 'funding_stage',
            'funding', 'revenue', 'arr', 'recent_news', 'news', 'recent_launch',
            'product_launch', 'pain_points', 'challenges', 'linkedin', 'linkedin_url',
            'twitter', 'twitter_handle', 'referral', 'mutual_connection', 'referred_by',
            'previous_interaction', 'met_at'
        }
        other_fields = {k: v for k, v in custom_fields.items() if k.lower() not in known_fields and v}
        if other_fields:
            context_parts.append(f"Additional Details: {json.dumps(other_fields)}")

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

        # Pre-substitute template variables with actual recipient data
        variable_map = {
            'name': recipient.get('name') or '',
            'email': recipient.get('email') or '',
            'company': recipient.get('company') or '',
        }
        # Add all custom fields as available variables
        for k, v in custom_fields.items():
            if v:
                variable_map[k] = str(v)
        # Add website_insights if available
        if website_insights:
            variable_map['website_insights'] = website_insights

        # Track which variables are missing
        missing_vars = []

        # Replace {{variable}} placeholders in template
        import re as _re
        def _replace_var(match):
            var_name = match.group(1).strip()
            val = variable_map.get(var_name)
            if val is not None:
                return val
            missing_vars.append(var_name)
            # Return a Claude-readable instruction instead of raw placeholder
            return f'[GENERATE: write appropriate content for "{var_name}"]'

        resolved_subject = _re.sub(r'\{\{(\s*\w+\s*)\}\}', _replace_var, template_subject)
        resolved_body = _re.sub(r'\{\{(\s*\w+\s*)\}\}', _replace_var, template_body)

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

        prompt = f"""You are ghostwriting personalized outreach emails for a specific person. Your job is to write exactly like them - matching their voice, tone, and style perfectly.

{style_instructions if style_instructions else "Write in a casual but professional tone. Keep it brief and human."}

{insights_instructions}

RECIPIENT PROFILE:
- Name: {recipient.get('name') or 'there'}
- Email: {recipient.get('email')}
- Company: {recipient.get('company') or 'their company'}

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

{"MISSING VARIABLE INSTRUCTIONS: The template contains [GENERATE: ...] markers where data was not available. For each one, write natural-sounding content IN PLACE that fits the surrounding template text. Keep it in the same position — do not move it. For website_insights specifically: write exactly 2 observations about how improving their web presence could help grow their business — each one should show the VALUE of what better looks like (more leads, more trust, stronger first impression), not point out what's wrong." + chr(10) + "Missing variables: " + ", ".join(missing_vars) if missing_vars else ""}

STYLE REQUIREMENTS:
1. Match the writer's personal style EXACTLY
2. Use specific details from the research notes to show genuine interest
3. Keep the tone casual and human
4. Lead with VALUE — show what's possible for their business, not what's wrong with it
5. Every observation should tie back to a business benefit (more customers, more trust, stronger brand)
6. Close casually, not with aggressive sales language

ABSOLUTE RULE - NEVER FABRICATE:
- ONLY reference facts explicitly provided in the context above
- NEVER invent meetings, events, mutual connections, or interactions that aren't in the data
- If context is limited, keep the email genuine but more general — don't fill gaps with fiction

HUMILITY RULE:
- NEVER try to sound smarter than the recipient about their own business
- NEVER contradict what their website clearly states (e.g. don't say "visitors won't know what you do" if the site explains it)
- Show you've done homework, but stay humble — they're the expert
- Keep observations respectful and accurate. When in doubt, acknowledge what they're doing well before suggesting opportunities

{("WEBSITE OBSERVATIONS (these came from reviewing their site — insert them exactly where the website_insights content appears in the template, do NOT move them to another section. Each observation should show the VALUE of improving — tie it to more customers, more trust, or a stronger online presence. We're showing what's possible, not criticizing what exists):" + chr(10) + website_insights) if website_insights else ""}

{f"CAMPAIGN MUST-INCLUDE (weave this into EVERY email naturally): {campaign_context}" if campaign_context else ""}

{f"SPECIAL INSTRUCTIONS (these are meta-instructions about how to write the email — use them to guide your tone/approach, but do NOT insert this text verbatim into the email body): {custom_prompt}" if custom_prompt else ""}

IMPORTANT: Return ONLY valid JSON in this exact format, nothing else:
{{"subject": "personalized subject line", "body": "personalized email body"}}
"""

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
                return {
                    'subject': result.get('subject', resolved_subject),
                    'body': result.get('body', resolved_body)
                }

            # Fallback if JSON parsing fails — return resolved template (variables filled in)
            print(f"JSON parse failed, returning resolved template. Response was: {response_text[:200]}")
            return {
                'subject': resolved_subject,
                'body': resolved_body
            }

        except Exception as e:
            print(f"Claude API error: {e}")
            # Even on error, return the resolved template so variables are filled in
            return {
                'subject': resolved_subject,
                'body': resolved_body
            }

    def generate_email(
        self,
        recipient: Dict,
        context: str,
        tone: str = 'professional'
    ) -> Dict[str, str]:
        """Generate a completely new email for a recipient."""

        prompt = f"""Write a {tone} outreach email for:

RECIPIENT:
- Name: {recipient.get('name') or 'there'}
- Company: {recipient.get('company') or 'their company'}
- Details: {json.dumps(recipient.get('custom_fields', {}))}

CONTEXT/PURPOSE:
{context}

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
                return json.loads(json_match.group())

            return {'subject': 'Hello', 'body': response_text}

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
                    'subject': result.get('subject', ''),
                    'body': result.get('body', '')
                }

            return {'name': 'Generated Template', 'subject': '', 'body': response_text}

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
                    'subject': result.get('subject', current_subject),
                    'body': result.get('body', current_body)
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
- Company: {recipient.get('company') or 'their company'}
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

TONE GUIDANCE:
- Be friendly and respectful — you're reaching out to help them grow, not to point out problems
- Always tie suggestions to business outcomes: "could help you get more leads", "give homeowners confidence to call"
- Focus on what's POSSIBLE for them, not what's currently wrong
- Sound like a helpful neighbor who sees potential, not a salesperson looking for flaws

ABSOLUTE RULES:
- NEVER fabricate facts, meetings, or connections not in the notes
- NEVER claim expertise in their industry — stay humble and curious
- NEVER just point out a problem — always pair it with the benefit of fixing it
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
                return json.loads(json_match.group())

            return {'subject': 'Quick note', 'body': response_text}

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
                return json.loads(json_match.group())

            return {'subject': f'Re: {original_subject}', 'body': response_text}

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
                return json.loads(json_match.group())

            return {'subject': f'Re: {original_subject}', 'body': response_text}

        except Exception as e:
            print(f"Meeting followup generation error: {e}")
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
                return json.loads(json_match.group())

            return {'subject': f'Re: {original_subject}', 'body': response_text}

        except Exception as e:
            print(f"Follow-up generation error: {e}")
            raise
