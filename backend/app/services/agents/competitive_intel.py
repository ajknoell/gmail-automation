"""
Competitive Intelligence Agent — monitors competitor websites for changes,
scrapes key pages, and produces intelligence reports.
"""
import json
import logging
import threading
from datetime import datetime

from app import db
from app.models.agent_task import AgentTask
from app.models.signal import Signal
from app.services.agent_framework import AgentTool, AgentRunner

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a competitive intelligence agent. Your job is to research a competitor
company and produce an intelligence report.

You have access to:
- firecrawl_map: Discover all pages on the competitor's website
- firecrawl_scrape: Scrape specific pages for their content
- web_search: Search for recent news about the competitor
- save_intelligence_report: Save your structured intelligence findings

## Research Process:
1. Map the competitor's site structure
2. Scrape key pages: pricing, features/products, about, blog (latest posts)
3. Search the web for recent news, product launches, and press releases
4. Synthesize into a structured intelligence report

## What to analyze:
- Products/services and pricing model
- Recent product changes or launches
- Market positioning and messaging
- Target customer segments
- Technology and platform details
- Strengths and weaknesses
- Recent news and announcements
- Key differentiators from your user's business

Be thorough but focus on actionable intelligence that would help with
competitive positioning and outreach strategy.

IMPORTANT: Always end by calling save_intelligence_report with your findings."""


def _build_tools(firecrawl_service, web_search_service=None):
    """Build the tool list for the competitive intelligence agent."""
    pages_scraped = {'count': 0}

    def firecrawl_map(params):
        url = params.get('url', '')
        result = firecrawl_service.map_site(url, limit=30)
        if result['success']:
            return json.dumps({'links': result['links'][:30]})
        return json.dumps({'error': result.get('error', 'Map failed')})

    def firecrawl_scrape(params):
        url = params.get('url', '')
        result = firecrawl_service.scrape_url(url)
        pages_scraped['count'] += 1
        if result['success']:
            markdown = result['markdown']
            if len(markdown) > 10000:
                markdown = markdown[:10000] + '\n\n[...page truncated]'
            return json.dumps({'markdown': markdown, 'metadata': result['metadata']})
        return json.dumps({'error': result.get('error', 'Scrape failed')})

    def web_search(params):
        if not web_search_service:
            return json.dumps({'error': 'Web search not configured'})
        query = params.get('query', '')
        result = web_search_service.search(query, max_results=5)
        return json.dumps(result)

    saved_report = {'data': None}

    def save_intelligence_report(params):
        saved_report['data'] = params
        return json.dumps({'success': True, 'message': 'Intelligence report saved.'})

    tools = [
        AgentTool(
            name='firecrawl_map',
            description='Discover all URLs on the competitor website.',
            input_schema={
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'description': 'The base URL to map'},
                },
                'required': ['url'],
            },
            executor=firecrawl_map,
        ),
        AgentTool(
            name='firecrawl_scrape',
            description='Scrape a specific page for its content.',
            input_schema={
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'description': 'The URL to scrape'},
                },
                'required': ['url'],
            },
            executor=firecrawl_scrape,
        ),
        AgentTool(
            name='web_search',
            description='Search the web for recent news and information about the competitor.',
            input_schema={
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'The search query'},
                },
                'required': ['query'],
            },
            executor=web_search,
        ),
        AgentTool(
            name='save_intelligence_report',
            description='Save the structured competitive intelligence report.',
            input_schema={
                'type': 'object',
                'properties': {
                    'competitor_name': {
                        'type': 'string',
                        'description': 'The competitor company name',
                    },
                    'overview': {
                        'type': 'string',
                        'description': 'Brief overview of the competitor',
                    },
                    'products_services': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Key products or services',
                    },
                    'pricing_model': {
                        'type': 'string',
                        'description': 'How they price (freemium, subscription, per-seat, etc.)',
                    },
                    'pricing_details': {
                        'type': 'string',
                        'description': 'Specific pricing tiers or numbers if found',
                    },
                    'target_market': {
                        'type': 'string',
                        'description': 'Who they sell to',
                    },
                    'positioning': {
                        'type': 'string',
                        'description': 'How they position themselves in the market',
                    },
                    'strengths': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Key competitive strengths',
                    },
                    'weaknesses': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Potential weaknesses or gaps',
                    },
                    'recent_changes': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Recent product changes, launches, or news',
                    },
                    'tech_stack': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Technologies they use or offer',
                    },
                    'key_takeaways': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Actionable insights for competitive strategy',
                    },
                },
                'required': ['competitor_name', 'overview', 'key_takeaways'],
            },
            executor=save_intelligence_report,
        ),
    ]

    return tools, saved_report, pages_scraped


def run_competitive_intel(app, task_id, cancel_event=None):
    """Execute competitive intelligence research. Designed to run in a background thread.

    Args:
        app: Flask app instance (for app context).
        task_id: AgentTask ID to update with results.
        cancel_event: Optional threading.Event to signal cancellation.
    """
    with app.app_context():
        task = AgentTask.query.get(task_id)
        if not task:
            logger.error(f'Competitive intel: task {task_id} not found')
            return

        config = task.get_config()
        competitor_url = config.get('competitor_url', '')
        competitor_name = config.get('competitor_name', '')

        if not competitor_url:
            task.status = 'failed'
            task.error_message = 'No competitor URL specified'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            return

        # Mark as running
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()

        if cancel_event is None:
            cancel_event = threading.Event()

        try:
            from app.services.firecrawl_service import FirecrawlService
            firecrawl = FirecrawlService.from_settings()

            web_search = None
            from app.models.settings import Settings
            tavily_key = Settings.get('tavily_api_key')
            if tavily_key:
                from app.services.web_search import WebSearchService
                web_search = WebSearchService(tavily_key)

            tools, saved_report, pages_scraped = _build_tools(firecrawl, web_search)

            if not competitor_url.startswith('http'):
                competitor_url = f'https://{competitor_url}'

            user_message = (
                f'Research this competitor and produce an intelligence report:\n'
                f'- Competitor: {competitor_name or "Unknown"}\n'
                f'- Website: {competitor_url}\n\n'
                f'Analyze their products, pricing, positioning, and recent activity.'
            )

            runner = AgentRunner(tools, SYSTEM_PROMPT, cancel_event=cancel_event)
            result = runner.run(user_message)

            task.input_tokens = result.input_tokens
            task.output_tokens = result.output_tokens
            task.firecrawl_pages_scraped = pages_scraped['count']
            task.set_execution_log(result.execution_log)

            if result.success and saved_report['data']:
                report = saved_report['data']
                task.status = 'completed'
                task.set_result(report)
                task.result_summary = report.get('overview', '')[:500]

                # Create a Signal record for the intelligence report
                signal = Signal(
                    workspace_id=task.workspace_id,
                    source_type='competitive_intel',
                    signal_type='competitor_report',
                    title=f'Competitive Intel: {report.get("competitor_name", competitor_name or "Unknown")}',
                    summary=report.get('overview', ''),
                    raw_data=json.dumps(report),
                    source_url=competitor_url,
                    severity='important',
                    intent_category='competitive_intel',
                )
                db.session.add(signal)

            elif result.success:
                task.status = 'completed'
                task.result_summary = result.output[:500]
                task.set_result({'raw_output': result.output})
            else:
                task.status = 'failed'
                task.error_message = result.error or 'Agent did not produce results'

            task.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            logger.error(f'Competitive intel failed for task {task_id}: {e}')
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
