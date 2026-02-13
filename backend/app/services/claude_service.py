from anthropic import Anthropic
from typing import Dict
import json
import re

class ClaudeService:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def personalize_email(
        self,
        template_subject: str,
        template_body: str,
        recipient: Dict,
        custom_prompt: str = None
    ) -> Dict[str, str]:
        """Generate personalized email using Claude."""

        prompt = f"""You are an expert email writer. Personalize the following email template for the recipient.
Keep the core message but make it feel personal and tailored to them.

RECIPIENT INFO:
- Name: {recipient.get('name') or 'there'}
- Email: {recipient.get('email')}
- Company: {recipient.get('company') or 'their company'}
- Additional Info: {json.dumps(recipient.get('custom_fields', {}))}

IMPORTANT: When referencing the recipient's company, use only the company name (not a URL or website address). If the company field looks like a URL, extract just the company name from it.

TEMPLATE SUBJECT: {template_subject}

TEMPLATE BODY:
{template_body}

{custom_prompt or ''}

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
                    'subject': result.get('subject', template_subject),
                    'body': result.get('body', template_body)
                }

            # Fallback if JSON parsing fails
            return {
                'subject': template_subject,
                'body': template_body
            }

        except Exception as e:
            print(f"Claude API error: {e}")
            return {
                'subject': template_subject,
                'body': template_body
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
