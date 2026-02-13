from anthropic import Anthropic
from typing import Dict
import json
import re


def clean_company_name(company: str) -> str:
    """Extract a human-readable company name from a URL or domain.

    Examples:
        'blglass.com'                  -> 'Blglass'
        'https://www.acme-corp.com'    -> 'Acme Corp'
        'blue-sky.io/about'            -> 'Blue Sky'
        'Acme Inc.'                    -> 'Acme Inc.' (unchanged, not a URL)
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
        # Nothing was stripped, not a URL — return as-is
        return company

    # Make the extracted name readable:
    # Insert spaces before capitals in camelCase (e.g. "blueGlass" -> "blue Glass")
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    # Replace hyphens and underscores with spaces
    cleaned = cleaned.replace('-', ' ').replace('_', ' ')
    return cleaned.title()


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

        company = clean_company_name(recipient.get('company', '')) or 'their company'

        prompt = f"""You are an expert email writer. Personalize the following email template for the recipient.
Keep the core message but make it feel personal and tailored to them.

RECIPIENT INFO:
- Name: {recipient.get('name') or 'there'}
- Email: {recipient.get('email')}
- Company: {company}
- Additional Info: {json.dumps(recipient.get('custom_fields', {}))}

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

        company = clean_company_name(recipient.get('company', '')) or 'their company'

        prompt = f"""Write a {tone} outreach email for:

RECIPIENT:
- Name: {recipient.get('name') or 'there'}
- Company: {company}
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
