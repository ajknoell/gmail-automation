"""
Prospect Research Agent — takes a lead with a website URL and autonomously
builds a comprehensive company research profile using Firecrawl and web search.
"""
import json
import logging
import threading
from datetime import datetime

from app import db
from app.models.agent_task import AgentTask
from app.models.lead import Lead
from app.services.agent_framework import AgentTool, AgentRunner

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a prospect research agent. Your job is to deeply research a company
and build a comprehensive profile for sales outreach.

You have access to:
- firecrawl_map: Discover all pages on a website
- firecrawl_scrape: Scrape a specific page for its content
- web_search: Search the web for recent news and information (if available)
- save_research_profile: Save your structured research findings

## Research Process:
1. First, use firecrawl_map to discover the site structure
2. Identify the most valuable pages (about, team, services, blog, case studies)
3. Scrape up to 5 key pages to gather information
4. Optionally search the web for recent news about the company
5. Synthesize everything into a structured research profile using save_research_profile

## What to look for:
- Company overview (what they do, industry, size)
- Key people (founders, executives, decision makers)
- Products/services offered
- Target customers/market
- Company culture and values
- Recent news, achievements, or milestones
- Technology stack or tools they use
- Pain points or challenges they might face
- Potential talking points for outreach

Be thorough but efficient. Focus on information that would be useful for
personalizing a sales email to this company.

IMPORTANT: Always end by calling save_research_profile with your findings."""


def _build_tools(firecrawl_service, web_search_service=None):
    """Build the tool list for the prospect research agent."""
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
            # Truncate very long pages
            markdown = result['markdown']
            if len(markdown) > 10000:
                markdown = markdown[:10000] + '\n\n[...page truncated]'
            return json.dumps({
                'markdown': markdown,
                'metadata': result['metadata'],
            })
        return json.dumps({'error': result.get('error', 'Scrape failed')})

    def web_search(params):
        if not web_search_service:
            return json.dumps({'error': 'Web search not configured'})
        query = params.get('query', '')
        result = web_search_service.search(query, max_results=5)
        return json.dumps(result)

    # Captured profile data
    saved_profile = {'data': None}

    def save_research_profile(params):
        saved_profile['data'] = params
        return json.dumps({'success': True, 'message': 'Research profile saved.'})

    tools = [
        AgentTool(
            name='firecrawl_map',
            description='Discover all URLs on a website. Returns a list of links found on the site.',
            input_schema={
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'description': 'The base URL of the website to map (e.g., https://example.com)',
                    },
                },
                'required': ['url'],
            },
            executor=firecrawl_map,
        ),
        AgentTool(
            name='firecrawl_scrape',
            description='Scrape a single web page and get its content as markdown. Use this to read specific pages like /about, /team, /services.',
            input_schema={
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'description': 'The full URL of the page to scrape',
                    },
                },
                'required': ['url'],
            },
            executor=firecrawl_scrape,
        ),
        AgentTool(
            name='web_search',
            description='Search the web for recent news and information about a company. Use for finding recent news, funding rounds, press releases.',
            input_schema={
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'The search query',
                    },
                },
                'required': ['query'],
            },
            executor=web_search,
        ),
        AgentTool(
            name='save_research_profile',
            description='Save the structured research profile. Call this once you have gathered enough information.',
            input_schema={
                'type': 'object',
                'properties': {
                    'company_overview': {
                        'type': 'string',
                        'description': '2-3 sentence overview of what the company does',
                    },
                    'industry': {
                        'type': 'string',
                        'description': 'The industry or sector',
                    },
                    'employee_count_estimate': {
                        'type': 'string',
                        'description': 'Estimated number of employees if found',
                    },
                    'key_people': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'title': {'type': 'string'},
                            },
                        },
                        'description': 'Key decision makers, founders, executives',
                    },
                    'products_services': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Main products or services offered',
                    },
                    'target_market': {
                        'type': 'string',
                        'description': 'Who their customers are',
                    },
                    'company_values': {
                        'type': 'string',
                        'description': 'Company culture, values, or mission',
                    },
                    'recent_news': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Recent news items, achievements, or milestones',
                    },
                    'tech_stack': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Technologies or tools they use (if discoverable)',
                    },
                    'talking_points': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Suggested personalization angles for outreach',
                    },
                    'year_founded': {
                        'type': 'string',
                        'description': 'Year the company was founded if found',
                    },
                },
                'required': ['company_overview', 'talking_points'],
            },
            executor=save_research_profile,
        ),
    ]

    return tools, saved_profile, pages_scraped


def run_prospect_research(app, task_id, lead_id, cancel_event=None):
    """Execute prospect research for a lead. Designed to run in a background thread.

    Args:
        app: Flask app instance (for app context).
        task_id: AgentTask ID to update with results.
        lead_id: Lead ID to research.
        cancel_event: Optional threading.Event to signal cancellation.
    """
    with app.app_context():
        task = AgentTask.query.get(task_id)
        lead = Lead.query.get(lead_id)

        if not task or not lead:
            logger.error(f'Prospect research: task {task_id} or lead {lead_id} not found')
            return

        if not lead.website:
            task.status = 'failed'
            task.error_message = 'Lead has no website URL'
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
            # Set up services
            from app.services.firecrawl_service import FirecrawlService
            firecrawl = FirecrawlService.from_settings()

            # Optionally set up web search
            web_search = None
            from app.models.settings import Settings
            tavily_key = Settings.get('tavily_api_key')
            if tavily_key:
                from app.services.web_search import WebSearchService
                web_search = WebSearchService(tavily_key)

            # Build tools and run the agent
            tools, saved_profile, pages_scraped = _build_tools(firecrawl, web_search)

            website = lead.website
            if not website.startswith('http'):
                website = f'https://{website}'

            user_message = (
                f'Research this company for sales outreach:\n'
                f'- Company name: {lead.name}\n'
                f'- Website: {website}\n'
                f'- Category: {lead.business_category or "Unknown"}\n'
                f'- Location: {lead.address or "Unknown"}\n\n'
                f'Build a comprehensive research profile.'
            )

            runner = AgentRunner(tools, SYSTEM_PROMPT, cancel_event=cancel_event)
            result = runner.run(user_message)

            # Update task with results
            task.input_tokens = result.input_tokens
            task.output_tokens = result.output_tokens
            task.firecrawl_pages_scraped = pages_scraped['count']
            task.set_execution_log(result.execution_log)

            if result.success and saved_profile['data']:
                profile = saved_profile['data']
                task.status = 'completed'
                task.set_result(profile)
                task.result_summary = profile.get('company_overview', '')[:500]

                # Update lead with discovered data
                enrichment = lead.get_enrichment_data()
                enrichment['agent_research'] = profile
                enrichment['agent_research_at'] = datetime.utcnow().isoformat()
                lead.set_enrichment_data(enrichment)

                # Update concrete fields if we found new data
                if profile.get('year_founded') and not lead.year_founded:
                    lead.year_founded = profile['year_founded']

                if profile.get('employee_count_estimate') and not lead.employee_count:
                    try:
                        # Try to parse a number from the estimate
                        est = profile['employee_count_estimate']
                        import re
                        nums = re.findall(r'\d+', est.replace(',', ''))
                        if nums:
                            lead.employee_count = int(nums[0])
                            lead.employee_count_source = 'agent_research'
                    except (ValueError, IndexError):
                        pass

                key_people = profile.get('key_people', [])
                if key_people and not lead.decision_maker:
                    lead.decision_maker = key_people[0].get('name', '')

            elif result.success:
                # Agent finished but didn't call save_research_profile
                task.status = 'completed'
                task.result_summary = result.output[:500]
                task.set_result({'raw_output': result.output})
            else:
                task.status = 'failed'
                task.error_message = result.error or 'Agent did not produce results'

            task.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            logger.error(f'Prospect research failed for task {task_id}: {e}')
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
