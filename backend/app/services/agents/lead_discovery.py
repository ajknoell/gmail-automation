"""
Lead Discovery Agent — given industry, location, and criteria, finds new
prospects by searching the web and crawling directory pages with Firecrawl.
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

SYSTEM_PROMPT = """You are a lead discovery agent. Your job is to find new business prospects
that match specific criteria by searching the web and crawling relevant directories.

You have access to:
- web_search: Search the web for businesses, directories, and listings
- firecrawl_scrape: Scrape a web page to extract business information
- firecrawl_map: Discover all pages on a directory site
- save_discovered_leads: Save the leads you've found

## Discovery Process:
1. Use web_search to find relevant directories, association pages, and business listings
   for the given industry and location
2. Scrape the most promising directory pages to extract business listings
3. For each business found, gather: name, website, phone, address, and any description
4. Save all discovered leads using save_discovered_leads

## Guidelines:
- Focus on finding real businesses with websites
- Look for industry-specific directories, trade associations, local business directories
- Search for queries like "[industry] [location] directory", "[industry] businesses in [location]"
- Try to find at least 5-10 businesses
- Only include businesses that seem legitimate and operational
- Deduplicate by company name

IMPORTANT: Always end by calling save_discovered_leads with your findings."""


def _build_tools(firecrawl_service, web_search_service):
    """Build the tool list for the lead discovery agent."""
    pages_scraped = {'count': 0}

    def web_search(params):
        query = params.get('query', '')
        result = web_search_service.search(query, max_results=5)
        return json.dumps(result)

    def firecrawl_scrape(params):
        url = params.get('url', '')
        result = firecrawl_service.scrape_url(url)
        pages_scraped['count'] += 1
        if result['success']:
            markdown = result['markdown']
            if len(markdown) > 12000:
                markdown = markdown[:12000] + '\n\n[...page truncated]'
            return json.dumps({'markdown': markdown, 'metadata': result['metadata']})
        return json.dumps({'error': result.get('error', 'Scrape failed')})

    def firecrawl_map(params):
        url = params.get('url', '')
        result = firecrawl_service.map_site(url, limit=20)
        if result['success']:
            return json.dumps({'links': result['links'][:20]})
        return json.dumps({'error': result.get('error', 'Map failed')})

    saved_leads = {'data': None}

    def save_discovered_leads(params):
        saved_leads['data'] = params
        return json.dumps({'success': True, 'message': f"Saved {len(params.get('leads', []))} leads."})

    tools = [
        AgentTool(
            name='web_search',
            description='Search the web for business directories, listings, and companies in a specific industry/location.',
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
            name='firecrawl_scrape',
            description='Scrape a web page to extract business listings and information.',
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
            name='firecrawl_map',
            description='Discover all pages on a directory site to find listing pages.',
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
            name='save_discovered_leads',
            description='Save the business leads you have discovered.',
            input_schema={
                'type': 'object',
                'properties': {
                    'leads': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string', 'description': 'Business name'},
                                'website': {'type': 'string', 'description': 'Website URL'},
                                'phone': {'type': 'string', 'description': 'Phone number'},
                                'address': {'type': 'string', 'description': 'Business address'},
                                'description': {'type': 'string', 'description': 'Brief description of the business'},
                                'source_url': {'type': 'string', 'description': 'URL where this business was found'},
                            },
                            'required': ['name'],
                        },
                        'description': 'List of discovered business leads',
                    },
                    'search_summary': {
                        'type': 'string',
                        'description': 'Summary of the discovery process and sources used',
                    },
                },
                'required': ['leads'],
            },
            executor=save_discovered_leads,
        ),
    ]

    return tools, saved_leads, pages_scraped


def run_lead_discovery(app, task_id, cancel_event=None):
    """Execute lead discovery. Designed to run in a background thread.

    Args:
        app: Flask app instance (for app context).
        task_id: AgentTask ID to update with results.
        cancel_event: Optional threading.Event to signal cancellation.
    """
    with app.app_context():
        task = AgentTask.query.get(task_id)
        if not task:
            logger.error(f'Lead discovery: task {task_id} not found')
            return

        config = task.get_config()
        industry = config.get('industry', '')
        location = config.get('location', '')
        criteria = config.get('criteria', '')

        if not industry:
            task.status = 'failed'
            task.error_message = 'No industry specified'
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

            from app.models.settings import Settings
            tavily_key = Settings.get('tavily_api_key')
            if not tavily_key:
                task.status = 'failed'
                task.error_message = 'Tavily API key required for lead discovery (web search)'
                task.completed_at = datetime.utcnow()
                db.session.commit()
                return

            from app.services.web_search import WebSearchService
            web_search = WebSearchService(tavily_key)

            tools, saved_leads, pages_scraped = _build_tools(firecrawl, web_search)

            user_message = (
                f'Find businesses in this industry and location:\n'
                f'- Industry: {industry}\n'
                f'- Location: {location or "Any"}\n'
            )
            if criteria:
                user_message += f'- Additional criteria: {criteria}\n'
            user_message += '\nSearch directories and listing sites to find matching businesses.'

            runner = AgentRunner(tools, SYSTEM_PROMPT, cancel_event=cancel_event)
            result = runner.run(user_message)

            task.input_tokens = result.input_tokens
            task.output_tokens = result.output_tokens
            task.firecrawl_pages_scraped = pages_scraped['count']
            task.set_execution_log(result.execution_log)

            if result.success and saved_leads['data']:
                discovered = saved_leads['data']
                leads_data = discovered.get('leads', [])

                # Create Lead records for each discovered business
                created_count = 0
                for lead_data in leads_data:
                    name = lead_data.get('name', '').strip()
                    if not name:
                        continue

                    # Check for duplicates by name in same workspace
                    existing = Lead.query.filter_by(
                        workspace_id=task.workspace_id,
                        name=name,
                    ).first()
                    if existing:
                        continue

                    lead = Lead(
                        workspace_id=task.workspace_id,
                        name=name,
                        website=lead_data.get('website', ''),
                        phone=lead_data.get('phone', ''),
                        address=lead_data.get('address', ''),
                        business_category=industry,
                        source='agent_discovery',
                        status='new',
                    )
                    db.session.add(lead)
                    created_count += 1

                task.status = 'completed'
                task.set_result({
                    'leads_found': len(leads_data),
                    'leads_created': created_count,
                    'search_summary': discovered.get('search_summary', ''),
                    'leads': leads_data,
                })
                task.result_summary = f'Found {len(leads_data)} leads, created {created_count} new records'
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
            logger.error(f'Lead discovery failed for task {task_id}: {e}')
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
