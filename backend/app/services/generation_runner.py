"""Background runner for email generation (preview personalization).

Follows the same pattern as CampaignRunner: a daemon thread that runs
generation in its own Flask app context, with class-level state tracking
so SSE endpoints can report progress.
"""
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerationState:
    campaign_id: int
    thread: Optional[threading.Thread] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    generated: int = 0
    failed: int = 0
    total: int = 0
    done: bool = False
    error: Optional[str] = None


class GenerationRunner:
    _instances: Dict[int, GenerationState] = {}
    _lock = threading.Lock()

    @classmethod
    def start(cls, campaign_id: int, recipient_ids: List[int], workspace_id: int = None) -> dict:
        """Start background generation. Returns immediately with status."""
        with cls._lock:
            existing = cls._instances.get(campaign_id)
            if existing and not existing.done:
                return {'already_running': True, 'generated': existing.generated,
                        'failed': existing.failed, 'total': existing.total}

            total = len(recipient_ids)
            state = GenerationState(campaign_id=campaign_id, total=total)
            thread = threading.Thread(
                target=cls._run_generation,
                args=(state, campaign_id, recipient_ids, workspace_id),
                daemon=True,
            )
            state.thread = thread
            cls._instances[campaign_id] = state
            thread.start()
            return {'started': True, 'total': total}

    @classmethod
    def get_state(cls, campaign_id: int) -> Optional[GenerationState]:
        return cls._instances.get(campaign_id)

    @classmethod
    def cancel(cls, campaign_id: int) -> bool:
        with cls._lock:
            state = cls._instances.get(campaign_id)
            if state and not state.done:
                state.cancel_event.set()
                return True
            return False

    @classmethod
    def cleanup(cls, campaign_id: int):
        """Remove finished state entry."""
        with cls._lock:
            state = cls._instances.get(campaign_id)
            if state and state.done:
                del cls._instances[campaign_id]

    @classmethod
    def _run_generation(cls, state: GenerationState, campaign_id: int, recipient_ids: List[int],
                        workspace_id: int = None):
        """Run generation in background thread with its own app context."""
        from app import db, create_app
        from app.models import Campaign, Recipient, Settings
        from app.models.settings import WorkspaceSettings
        from app.services.claude_service import ClaudeService, clean_company_name, _looks_like_company_name, resolve_recipient_fields
        from app.services.website_analyzer import WebsiteAnalyzer
        from app.services.spam_checker import check_spam_score
        from flask import g

        app = create_app()
        with app.app_context():
            # Set workspace_id on g so helper functions can access it
            g.workspace_id = workspace_id
            try:
                campaign = Campaign.query.get(campaign_id)
                if not campaign or not campaign.template:
                    state.error = 'Campaign or template not found'
                    state.done = True
                    return

                # Load settings
                api_key = Settings.get('anthropic_api_key') if campaign.use_ai_personalization else None
                if campaign.use_ai_personalization and not api_key:
                    state.error = 'Anthropic API key not configured'
                    state.done = True
                    return

                # Import route helpers we need
                from app.routes.campaigns import (
                    _get_writing_style, _get_learned_insights,
                    _get_learned_website_insights, _log_website_analysis,
                    _substitute_template_variables,
                )

                if campaign.use_ai_personalization:
                    cls._run_ai_generation(
                        state, campaign, recipient_ids, api_key,
                        _get_writing_style, _get_learned_insights,
                        _get_learned_website_insights, _log_website_analysis,
                    )
                else:
                    cls._run_simple_generation(
                        state, campaign, recipient_ids,
                        _substitute_template_variables,
                    )

                # Spam check + confidence scoring on generated emails
                from app.services.confidence_scorer import ConfidenceScorer
                import json as _json_mod

                for rid in recipient_ids:
                    if state.cancel_event.is_set():
                        break
                    r = Recipient.query.get(rid)
                    if not r or not r.personalized_body:
                        continue

                    sc = check_spam_score(
                        r.personalized_subject or '', r.personalized_body
                    )

                    try:
                        result = ConfidenceScorer.score(
                            subject=r.personalized_subject or '',
                            body=r.personalized_body,
                            recipient_data={
                                'name': r.name,
                                'company': r.company,
                                'custom_fields': r.get_custom_fields(),
                            },
                            spam_score=sc['score'],
                            workspace_id=campaign.workspace_id,
                        )
                        r.confidence_score = result['confidence']
                        r.confidence_breakdown = _json_mod.dumps(result['breakdown'])

                        # Auto-approve if confidence threshold met
                        if campaign.auto_send_enabled and result['confidence'] >= (campaign.auto_send_threshold or 0.8):
                            r.approved = True
                    except Exception:
                        pass

                db.session.commit()

            except Exception as e:
                logger.error(f"Generation runner error for campaign {campaign_id}: {e}")
                state.error = str(e)
            finally:
                state.done = True

    @classmethod
    def _run_ai_generation(cls, state, campaign, recipient_ids, api_key,
                           get_writing_style, get_learned_insights,
                           get_learned_website_insights, log_website_analysis):
        """AI personalization path."""
        from app import db
        from app.models import Recipient, Settings
        from app.services.claude_service import ClaudeService
        from app.services.website_analyzer import WebsiteAnalyzer
        from flask import g

        claude = ClaudeService(api_key)
        writing_style = get_writing_style()
        learned_insights = get_learned_insights()

        # Load business profile for workspace context
        from app.models.business_profile import BusinessProfile
        business_profile = BusinessProfile.query.filter_by(workspace_id=campaign.workspace_id).first()

        # Competitor discovery
        competitor_service = None
        if campaign.competitor_search_query:
            google_places_key = Settings.get('google_places_api_key')
            if google_places_key:
                from app.services.competitor_discovery import CompetitorService
                competitor_service = CompetitorService(google_places_api_key=google_places_key)

        needs_website_analysis = (
            '{{website_insights}}' in (campaign.template.body or '')
            or '{{ website_insights }}' in (campaign.template.body or '')
        )

        tpl_subject = campaign.template.subject
        tpl_body = campaign.template.body
        ai_prompt = campaign.ai_prompt
        campaign_context = campaign.campaign_context
        workspace_id = campaign.workspace_id

        if needs_website_analysis:
            cls._run_sequential_path(
                state, recipient_ids, claude, tpl_subject, tpl_body,
                ai_prompt, campaign_context, writing_style, learned_insights,
                competitor_service, campaign, workspace_id,
                get_learned_website_insights, log_website_analysis,
                business_profile=business_profile,
            )
        else:
            cls._run_parallel_path(
                state, recipient_ids, claude, tpl_subject, tpl_body,
                ai_prompt, campaign_context, writing_style, learned_insights,
                competitor_service, campaign,
                business_profile=business_profile,
            )

    @classmethod
    def _run_sequential_path(cls, state, recipient_ids, claude,
                              tpl_subject, tpl_body, ai_prompt, campaign_context,
                              writing_style, learned_insights,
                              competitor_service, campaign, workspace_id,
                              get_learned_website_insights, log_website_analysis,
                              business_profile=None):
        """Website analysis path — sequential, one recipient at a time."""
        from app import db
        from app.models import Recipient
        from app.services.website_analyzer import WebsiteAnalyzer
        from app.services.claude_service import ClaudeService

        learned_website_insights = get_learned_website_insights()
        website_analysis_cache = {}

        for rid in recipient_ids:
            if state.cancel_event.is_set():
                break

            recipient = Recipient.query.get(rid)
            if not recipient:
                state.failed += 1
                continue

            try:
                recipient_dict = {
                    'name': recipient.name,
                    'email': recipient.email,
                    'company': recipient.company,
                    'custom_fields': recipient.get_all_context(),
                }

                resolved_url = WebsiteAnalyzer.resolve_url(recipient_dict)
                cache_key = (resolved_url or '').lower().rstrip('/')
                if cache_key and cache_key in website_analysis_cache:
                    wa_result = website_analysis_cache[cache_key]
                else:
                    wa_result = WebsiteAnalyzer.fetch_and_analyze(claude, recipient_dict, learned_website_insights)
                    if cache_key and wa_result:
                        website_analysis_cache[cache_key] = wa_result

                website_insights = wa_result.get('analysis_text') if wa_result else None
                website_analysis_data = wa_result.get('analysis') if wa_result else None
                team_contacts = wa_result.get('team_contacts', []) if wa_result else []

                if wa_result:
                    log_website_analysis(workspace_id, recipient.id, wa_result)

                # Competitor discovery
                competitors = []
                competitor_location = ''
                if competitor_service:
                    custom_fields = recipient_dict.get('custom_fields', {})
                    comp_result = competitor_service.discover_competitors(
                        company=recipient_dict.get('company', ''),
                        industry=custom_fields.get('industry') or custom_fields.get('sector', ''),
                        search_query=campaign.competitor_search_query,
                        custom_fields=custom_fields,
                    )
                    competitors = comp_result.get('competitors', [])
                    competitor_location = comp_result.get('location', '')

                result = claude.personalize_email(
                    template_subject=tpl_subject,
                    template_body=tpl_body,
                    recipient=recipient_dict,
                    custom_prompt=ai_prompt,
                    writing_style=writing_style,
                    campaign_context=campaign_context,
                    website_insights=website_insights,
                    learned_insights=learned_insights,
                    team_contacts=team_contacts,
                    competitors=competitors,
                    competitor_location=competitor_location,
                    business_profile=business_profile,
                )

                recipient.personalized_subject = result.get('subject', tpl_subject)
                recipient.personalized_body = result.get('body', tpl_body)
                content_warnings = result.get('content_warnings', [])
                if website_analysis_data:
                    severity = ClaudeService.get_max_severity(website_analysis_data)
                    if not severity:
                        content_warnings.append('No significant website issues found for outreach')
                if content_warnings:
                    recipient.error_message = ' | '.join(content_warnings)
                else:
                    recipient.error_message = None
                state.generated += 1
            except Exception as e:
                logger.warning(f"Failed to personalize recipient {rid}: {e}")
                state.failed += 1

            db.session.commit()

    @classmethod
    def _run_parallel_path(cls, state, recipient_ids, claude,
                            tpl_subject, tpl_body, ai_prompt, campaign_context,
                            writing_style, learned_insights,
                            competitor_service, campaign,
                            business_profile=None):
        """Fast parallel path — no website analysis, concurrent Claude calls."""
        from app import db
        from app.models import Recipient
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Pre-warm industry cache in main thread
        _template_uses_industry = (
            '{{industry}}' in (tpl_body or '')
            or '{{industry}}' in (tpl_subject or '')
        )
        if _template_uses_industry:
            seen_domains = set()
            for rid in recipient_ids:
                r = Recipient.query.get(rid)
                if not r:
                    continue
                cf = r.get_custom_fields() or {}
                domain = (
                    cf.get('Company Domain', '') or cf.get('company domain', '')
                    or cf.get('domain', '') or cf.get('website', '')
                )
                if not domain and r.email and '@' in r.email:
                    domain = r.email.split('@')[1]
                if domain:
                    domain = domain.lower().strip().replace('https://', '').replace('http://', '').split('/')[0]
                    if domain not in seen_domains:
                        seen_domains.add(domain)
                        claude.detect_industry(domain)

        # Build tasks
        tasks = []
        for rid in recipient_ids:
            if state.cancel_event.is_set():
                break
            r = Recipient.query.get(rid)
            if not r:
                state.failed += 1
                continue
            recipient_dict = {
                'name': r.name,
                'email': r.email,
                'company': r.company,
                'custom_fields': r.get_all_context(),
            }
            competitors = []
            competitor_location = ''
            if competitor_service:
                custom_fields = recipient_dict.get('custom_fields', {})
                comp_result = competitor_service.discover_competitors(
                    company=recipient_dict.get('company', ''),
                    industry=custom_fields.get('industry') or custom_fields.get('sector', ''),
                    search_query=campaign.competitor_search_query,
                    custom_fields=custom_fields,
                )
                competitors = comp_result.get('competitors', [])
                competitor_location = comp_result.get('location', '')
            tasks.append((rid, recipient_dict, competitors, competitor_location))

        def _personalize(task_data):
            _, r_dict, comps, comp_loc = task_data
            return claude.personalize_email(
                template_subject=tpl_subject,
                template_body=tpl_body,
                recipient=r_dict,
                custom_prompt=ai_prompt,
                writing_style=writing_style,
                campaign_context=campaign_context,
                website_insights=None,
                learned_insights=learned_insights,
                team_contacts=[],
                competitors=comps,
                competitor_location=comp_loc,
                business_profile=business_profile,
            )

        # Process in batches of 5 to update progress incrementally
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            if state.cancel_event.is_set():
                break
            batch = tasks[i:i + batch_size]
            results_map = {}

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_task = {
                    executor.submit(_personalize, t): t for t in batch
                }
                for future in as_completed(future_to_task):
                    task_data = future_to_task[future]
                    rid = task_data[0]
                    try:
                        results_map[rid] = future.result()
                    except Exception as e:
                        results_map[rid] = e

            # Apply results in main thread
            for rid, r_dict, _, _ in batch:
                result = results_map.get(rid)
                r = Recipient.query.get(rid)
                if not r:
                    continue
                if isinstance(result, Exception):
                    logger.warning(f"Failed to personalize recipient {rid}: {result}")
                    state.failed += 1
                elif result:
                    r.personalized_subject = result.get('subject', tpl_subject)
                    r.personalized_body = result.get('body', tpl_body)
                    content_warnings = result.get('content_warnings', [])
                    if content_warnings:
                        r.error_message = ' | '.join(content_warnings)
                    else:
                        r.error_message = None
                    state.generated += 1
                else:
                    state.failed += 1
                db.session.commit()

    @classmethod
    def _run_simple_generation(cls, state, campaign, recipient_ids, substitute_fn):
        """Non-AI path — simple variable substitution."""
        from app import db
        from app.models import Recipient, Settings

        non_ai_comp_service = None
        if campaign.competitor_search_query:
            google_places_key = Settings.get('google_places_api_key')
            if google_places_key:
                from app.services.competitor_discovery import CompetitorService
                non_ai_comp_service = CompetitorService(google_places_api_key=google_places_key)

        for rid in recipient_ids:
            if state.cancel_event.is_set():
                break

            recipient = Recipient.query.get(rid)
            if not recipient:
                state.failed += 1
                continue

            extra_vars = None
            if non_ai_comp_service:
                cf = recipient.get_custom_fields()
                comp_result = non_ai_comp_service.discover_competitors(
                    company=recipient.company or '',
                    industry=cf.get('industry') or cf.get('sector', ''),
                    search_query=campaign.competitor_search_query,
                    custom_fields=cf,
                )
                comps = comp_result.get('competitors', [])
                if comps:
                    extra_vars = non_ai_comp_service.build_variable_map(comps)

            recipient.personalized_subject = substitute_fn(
                campaign.template.subject, recipient, extra_vars)
            recipient.personalized_body = substitute_fn(
                campaign.template.body, recipient, extra_vars)
            state.generated += 1
            db.session.commit()
