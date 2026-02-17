import re
import requests


class WebSearchService:
    """Web search via Tavily API for recipient/company research."""

    TAVILY_API_URL = 'https://api.tavily.com/search'

    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query, max_results=5, search_depth='basic', include_answer=True):
        """Execute a web search and return structured results.

        Returns:
            {
                'answer': str,
                'results': [{'title': str, 'url': str, 'content': str}],
                'query': str,
            }
        """
        try:
            response = requests.post(
                self.TAVILY_API_URL,
                json={
                    'api_key': self.api_key,
                    'query': query,
                    'max_results': max_results,
                    'search_depth': search_depth,
                    'include_answer': include_answer,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            return {
                'answer': data.get('answer', ''),
                'results': [
                    {
                        'title': r.get('title', ''),
                        'url': r.get('url', ''),
                        'content': r.get('content', '')[:500],
                    }
                    for r in data.get('results', [])[:max_results]
                ],
                'query': query,
            }
        except Exception as e:
            print(f"Web search error: {e}")
            return {
                'answer': '',
                'results': [],
                'query': query,
                'error': str(e),
            }

    def research_company(self, company='', industry=None, custom_query=None, recipient_name=None):
        """Research a company/recipient for follow-up email context.

        Builds a smart search query from available info, or uses a custom query
        with {{variable}} substitution.
        """
        if custom_query:
            query = custom_query
            query = query.replace('{{company}}', company or '')
            query = query.replace('{{industry}}', industry or '')
            query = query.replace('{{name}}', recipient_name or '')
            query = re.sub(r'\{\{\w+\}\}', '', query).strip()
        else:
            parts = [company or '']
            if industry:
                parts.append(industry)
            parts.append('recent news OR trends OR updates')
            query = ' '.join(parts).strip()

        return self.search(query, max_results=5, search_depth='basic', include_answer=True)

    @staticmethod
    def format_for_prompt(research, max_chars=1500):
        """Format web research results into a text block suitable for a Claude prompt."""
        parts = []

        if research.get('answer'):
            parts.append(f"SUMMARY: {research['answer']}")

        for r in research.get('results', []):
            title = r.get('title', '')
            content = r.get('content', '')
            if content:
                parts.append(f"- {title}: {content}")

        text = '\n'.join(parts)
        if len(text) > max_chars:
            text = text[:max_chars] + '\n[...truncated]'
        return text
