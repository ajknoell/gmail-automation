from flask import Flask, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

# Allow OAuth over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

db = SQLAlchemy()

def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        from config import Config
        config_class = Config

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:5173']))

    # Ensure upload folder exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'data/uploads'), exist_ok=True)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.templates import templates_bp
    from app.routes.campaigns import campaigns_bp
    from app.routes.quick_send import quick_send_bp
    from app.routes.tracking import tracking_bp
    from app.routes.clay import clay_bp
    from app.routes.contacts import contacts_bp
    from app.routes.replies import replies_bp
    from app.routes.workspaces import workspaces_bp
    from app.routes.insights import insights_bp
    from app.routes.attachments import attachments_bp
    from app.routes.listings import listings_bp
    from app.routes.cold_calls import cold_calls_bp
    from app.routes.map_explorer import map_explorer_bp
    from app.routes.discovery import discovery_bp
    from app.routes.brief import brief_bp
    from app.routes.triggers import triggers_bp
    from app.routes.features import features_bp
    from app.routes.pipeline import pipeline_bp
    from app.routes.signals import signals_bp
    from app.routes.profile import profile_bp
    from app.routes.opportunities import opportunities_bp
    from app.routes.agents import agents_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(pipeline_bp, url_prefix='/api/pipeline')
    app.register_blueprint(map_explorer_bp, url_prefix='/api/map-explorer')
    app.register_blueprint(templates_bp, url_prefix='/api/templates')
    app.register_blueprint(campaigns_bp, url_prefix='/api/campaigns')
    app.register_blueprint(quick_send_bp, url_prefix='/api/quick-send')
    app.register_blueprint(tracking_bp)
    app.register_blueprint(clay_bp, url_prefix='/api/clay')
    app.register_blueprint(contacts_bp, url_prefix='/api/contacts')
    app.register_blueprint(replies_bp, url_prefix='/api/replies')
    app.register_blueprint(workspaces_bp, url_prefix='/api/workspaces')
    app.register_blueprint(insights_bp, url_prefix='/api/insights')
    app.register_blueprint(attachments_bp, url_prefix='/api/attachments')
    app.register_blueprint(listings_bp, url_prefix='/api/listings')
    app.register_blueprint(cold_calls_bp, url_prefix='/api/cold-calls')
    app.register_blueprint(discovery_bp, url_prefix='/api/discovery')
    app.register_blueprint(brief_bp, url_prefix='/api/brief')
    app.register_blueprint(triggers_bp, url_prefix='/api/triggers')
    app.register_blueprint(features_bp, url_prefix='/api/features')
    app.register_blueprint(signals_bp, url_prefix='/api/signals')
    app.register_blueprint(profile_bp, url_prefix='/api/profile')
    app.register_blueprint(opportunities_bp, url_prefix='/api/opportunities')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')

    # Create database tables and run migrations
    with app.app_context():
        db.create_all()

        # Run simple migrations for new columns
        _run_migrations(app)

        # Backfill contacts from existing email logs (one-time)
        _backfill_contacts(app)

        # Ensure default workspace exists and backfill workspace_id
        _ensure_default_workspace(app)

        # Migrate unique constraints for workspace scoping
        _migrate_unique_constraints(app)

        # Backfill campaign steps for existing campaigns (one-time)
        _ensure_campaign_steps(app)

    # Workspace resolution middleware
    @app.before_request
    def resolve_workspace():
        # Skip for tracking endpoints (no workspace context needed)
        if request.path.startswith('/t/'):
            g.workspace = None
            g.workspace_id = None
            return

        from app.models.workspace import Workspace

        ws_id = request.headers.get('X-Workspace-Id')
        if ws_id:
            try:
                ws = Workspace.query.get(int(ws_id))
                if ws:
                    g.workspace = ws
                    g.workspace_id = ws.id
                    return
            except (ValueError, TypeError):
                pass

        # Fall back to default workspace
        default_ws = Workspace.query.filter_by(is_default=True).first()
        if default_ws:
            g.workspace = default_ws
            g.workspace_id = default_ws.id
        else:
            g.workspace = None
            g.workspace_id = None

    # Start reply checker background polling
    from app.services.reply_checker import ReplyChecker
    interval = app.config.get('REPLY_CHECK_INTERVAL', 300)
    ReplyChecker.start_background_polling(app, interval=interval)

    # Start listing monitor background polling (every hour)
    from app.services.listing_scraper import ListingMonitor
    listing_interval = app.config.get('LISTING_CHECK_INTERVAL', 3600)
    ListingMonitor.start_background_polling(app, interval=listing_interval)

    # Start sequence scheduler for campaign follow-up steps
    from app.services.sequence_scheduler import SequenceScheduler
    seq_interval = app.config.get('SEQUENCE_CHECK_INTERVAL', 300)
    SequenceScheduler.start_background_polling(app, interval=seq_interval)

    # Start prospect discovery scanner (hourly check, weekly actual scans)
    from app.services.prospect_discovery import ProspectScanner
    discovery_interval = app.config.get('DISCOVERY_CHECK_INTERVAL', 3600)
    ProspectScanner.start_background_polling(app, interval=discovery_interval)

    # Start website trigger monitor (daily check)
    from app.services.trigger_monitor import TriggerMonitor
    trigger_interval = app.config.get('TRIGGER_CHECK_INTERVAL', 86400)
    TriggerMonitor.start_background_polling(app, interval=trigger_interval)

    # Start lead enrichment worker (every 10 minutes)
    from app.services.enrichment_service import EnrichmentWorker
    enrichment_interval = app.config.get('ENRICHMENT_CHECK_INTERVAL', 600)
    EnrichmentWorker.start_background_polling(app, interval=enrichment_interval)

    # Start signal engine (hourly check across all signal sources)
    from app.services.signal_engine import SignalEngine
    signal_interval = app.config.get('SIGNAL_CHECK_INTERVAL', 3600)
    SignalEngine.start_background_polling(app, interval=signal_interval)

    return app


def _run_migrations(app):
    """Run simple schema migrations for SQLite."""
    from sqlalchemy import text, inspect

    inspector = inspect(db.engine)

    def _add_column(table, column, col_type, default=None):
        if table in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns(table)]
            if column not in columns:
                try:
                    default_clause = f' DEFAULT {default}' if default is not None else ''
                    db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}'))
                    db.session.commit()
                    app.logger.info(f'Added {column} column to {table} table')
                except Exception as e:
                    app.logger.warning(f'Migration note: {e}')

    # Recipients migrations
    _add_column('recipients', 'notes', 'TEXT')
    # SQLite cannot ALTER TABLE ADD COLUMN with non-constant defaults like
    # CURRENT_TIMESTAMP, so add without default then backfill NULLs.
    _add_column('recipients', 'enrolled_at', 'DATETIME')
    _add_column('recipients', 'created_at', 'DATETIME')

    # EmailLog tracking migrations
    _add_column('email_logs', 'step_id', 'INTEGER')
    _add_column('email_logs', 'tracking_id', 'VARCHAR(36)')
    _add_column('email_logs', 'gmail_thread_id', 'VARCHAR(100)')
    _add_column('email_logs', 'gmail_account_id', 'INTEGER')
    _add_column('email_logs', 'recipient_email', 'VARCHAR(255)')
    _add_column('email_logs', 'opened_at', 'DATETIME')
    _add_column('email_logs', 'open_count', 'INTEGER', default=0)
    _add_column('email_logs', 'clicked_at', 'DATETIME')
    _add_column('email_logs', 'click_count', 'INTEGER', default=0)
    _add_column('email_logs', 'replied_at', 'DATETIME')
    _add_column('email_logs', 'link_map', 'TEXT')
    _add_column('email_logs', 'is_html', 'BOOLEAN', default=0)
    _add_column('email_logs', 'bounced_at', 'DATETIME')
    _add_column('email_logs', 'bounce_reason', 'TEXT')

    # Contacts migrations
    _add_column('contacts', 'status', "VARCHAR(20)", default="'contacted'")
    _add_column('contacts', 'follow_up_date', 'DATE')
    _add_column('contacts', 'follow_up_note', 'TEXT')

    # Workspace ID migrations
    _add_column('contacts', 'workspace_id', 'INTEGER')
    _add_column('campaigns', 'workspace_id', 'INTEGER')
    _add_column('campaigns', 'attachments', 'TEXT')
    _add_column('campaigns', 'competitor_search_query', 'TEXT')
    _add_column('templates', 'workspace_id', 'INTEGER')
    _add_column('tags', 'workspace_id', 'INTEGER')
    _add_column('email_logs', 'workspace_id', 'INTEGER')

    # Website analysis structured data migrations
    _add_column('website_analysis_logs', 'analysis_json', 'TEXT')
    _add_column('website_analysis_logs', 'max_severity', 'VARCHAR(20)')

    # Contact discovery fields (Phase 1)
    _add_column('contacts', 'discovery_source', 'VARCHAR(50)')
    _add_column('contacts', 'discovered_at', 'DATETIME')
    _add_column('contacts', 'google_rating', 'FLOAT')
    _add_column('contacts', 'review_count', 'INTEGER')
    _add_column('contacts', 'phone', 'VARCHAR(50)')
    _add_column('contacts', 'address', 'VARCHAR(500)')
    _add_column('contacts', 'business_category', 'VARCHAR(200)')
    _add_column('contacts', 'qualified', 'BOOLEAN')
    _add_column('contacts', 'qualification_reason', 'TEXT')
    _add_column('contacts', 'discovery_criteria_id', 'INTEGER')

    # Campaign auto-send fields (Phase 2)
    _add_column('campaigns', 'auto_send_enabled', 'BOOLEAN', default=0)
    _add_column('campaigns', 'auto_send_threshold', 'FLOAT', default=0.8)

    # Recipient confidence scoring (Phase 2)
    _add_column('recipients', 'confidence_score', 'FLOAT')
    _add_column('recipients', 'confidence_breakdown', 'TEXT')
    _add_column('step_recipients', 'confidence_score', 'FLOAT')
    _add_column('step_recipients', 'confidence_breakdown', 'TEXT')

    # Reply autopilot fields (Phase 3)
    _add_column('reply_messages', 'sentiment_subcategory', 'VARCHAR(50)')
    _add_column('reply_messages', 'auto_responded', 'BOOLEAN', default=0)
    _add_column('reply_messages', 'auto_response_type', 'VARCHAR(50)')
    _add_column('reply_messages', 'flagged_for_review', 'BOOLEAN', default=0)
    _add_column('reply_messages', 'flag_reason', 'VARCHAR(200)')

    # Owner retirement likelihood detection
    _add_column('leads', 'retirement_score', 'INTEGER')
    _add_column('leads', 'retirement_label', 'VARCHAR(20)')

    # Create index on tracking_id
    try:
        db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_email_logs_tracking_id ON email_logs(tracking_id)'))
        db.session.commit()
    except Exception:
        pass


def _backfill_contacts(app):
    """One-time backfill of contacts from existing email_logs."""
    from app.models.contact import Contact
    from app.models import EmailLog, Recipient
    from sqlalchemy import func

    # Skip if contacts already exist (migration already ran)
    if Contact.query.first() is not None:
        return

    # Check if there are any email logs to backfill from
    if EmailLog.query.first() is None:
        return

    # Aggregate from email_logs grouped by recipient_email
    results = db.session.query(
        EmailLog.recipient_email,
        func.min(EmailLog.created_at),
        func.max(EmailLog.created_at),
        func.count(EmailLog.id),
        func.max(EmailLog.replied_at),
    ).filter(
        EmailLog.recipient_email.isnot(None),
        EmailLog.status == 'sent',
    ).group_by(EmailLog.recipient_email).all()

    count = 0
    for email, first, last, sent_count, replied in results:
        if not email:
            continue
        # Try to get name/company from Recipients table
        recipient = Recipient.query.filter_by(email=email).first()
        contact = Contact(
            email=email.strip().lower(),
            name=recipient.name if recipient else None,
            company=recipient.company if recipient else None,
            first_contacted_at=first,
            last_contacted_at=last,
            total_emails_sent=sent_count,
            last_replied_at=replied,
        )
        db.session.add(contact)
        count += 1

    if count > 0:
        db.session.commit()
        app.logger.info(f'Backfilled {count} contacts from email_logs')


def _ensure_default_workspace(app):
    """Create default workspace and backfill existing data."""
    from app.models.workspace import Workspace
    from app.models.settings import Settings, WorkspaceSettings
    from sqlalchemy import text

    # Check if default workspace already exists
    default_ws = Workspace.query.filter_by(is_default=True).first()
    if default_ws:
        return  # Already set up

    # Create default workspace
    default_ws = Workspace(
        name='Default',
        slug='default',
        color='#3B82F6',
        is_default=True,
    )
    db.session.add(default_ws)
    db.session.flush()  # Get the ID

    ws_id = default_ws.id
    app.logger.info(f'Created default workspace (id={ws_id})')

    # Backfill workspace_id on all existing rows
    for table in ['contacts', 'campaigns', 'templates', 'tags', 'email_logs']:
        try:
            db.session.execute(
                text(f'UPDATE {table} SET workspace_id = :ws_id WHERE workspace_id IS NULL'),
                {'ws_id': ws_id}
            )
        except Exception as e:
            app.logger.warning(f'Workspace backfill {table}: {e}')

    # Migrate writing_style from global Settings to WorkspaceSettings
    writing_style = Settings.get('writing_style')
    if writing_style:
        WorkspaceSettings.set(ws_id, 'writing_style', writing_style)
        app.logger.info('Migrated writing_style to default workspace settings')

    db.session.commit()
    app.logger.info('Workspace backfill complete')


def _migrate_unique_constraints(app):
    """Recreate contacts and tags tables to use composite unique constraints."""
    from app.models.settings import Settings
    from sqlalchemy import text

    # Use a settings flag to avoid re-running
    if Settings.get('workspace_unique_migrated'):
        return

    app.logger.info('Migrating unique constraints for workspace scoping...')

    try:
        # --- Contacts: change unique(email) to unique(email, workspace_id) ---
        # Check if contacts table exists and has data
        result = db.session.execute(text("SELECT count(*) FROM contacts")).scalar()
        if result is not None:
            # Rename old table
            db.session.execute(text("ALTER TABLE contacts RENAME TO contacts_old"))

            # Create new table with composite unique
            db.session.execute(text("""
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER REFERENCES workspaces(id),
                    email VARCHAR(255) NOT NULL,
                    name VARCHAR(100),
                    company VARCHAR(100),
                    website VARCHAR(255),
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'new',
                    follow_up_date DATE,
                    follow_up_note TEXT,
                    first_contacted_at DATETIME,
                    last_contacted_at DATETIME,
                    total_emails_sent INTEGER DEFAULT 0,
                    last_replied_at DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME,
                    UNIQUE(email, workspace_id)
                )
            """))

            # Copy data
            db.session.execute(text("""
                INSERT INTO contacts (id, workspace_id, email, name, company, website, notes,
                    status, follow_up_date, follow_up_note, first_contacted_at, last_contacted_at,
                    total_emails_sent, last_replied_at, created_at, updated_at)
                SELECT id, workspace_id, email, name, company, website, notes,
                    status, follow_up_date, follow_up_note, first_contacted_at, last_contacted_at,
                    total_emails_sent, last_replied_at, created_at, updated_at
                FROM contacts_old
            """))

            # Recreate indexes
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_email ON contacts(email)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_workspace_id ON contacts(workspace_id)"))

            # Drop old table
            db.session.execute(text("DROP TABLE contacts_old"))
            app.logger.info('Migrated contacts table unique constraint')

        # --- Tags: change unique(name) to unique(name, workspace_id) ---
        result = db.session.execute(text("SELECT count(*) FROM tags")).scalar()
        if result is not None:
            db.session.execute(text("ALTER TABLE tags RENAME TO tags_old"))

            db.session.execute(text("""
                CREATE TABLE tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER REFERENCES workspaces(id),
                    name VARCHAR(50) NOT NULL,
                    color VARCHAR(7) DEFAULT '#6B7280',
                    created_at DATETIME,
                    UNIQUE(name, workspace_id)
                )
            """))

            db.session.execute(text("""
                INSERT INTO tags (id, workspace_id, name, color, created_at)
                SELECT id, workspace_id, name, color, created_at
                FROM tags_old
            """))

            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_tags_workspace_id ON tags(workspace_id)"))
            db.session.execute(text("DROP TABLE tags_old"))
            app.logger.info('Migrated tags table unique constraint')

        # Mark as done
        Settings.set('workspace_unique_migrated', 'true')
        db.session.commit()
        app.logger.info('Unique constraint migration complete')

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Unique constraint migration failed: {e}')
        raise


def _ensure_campaign_steps(app):
    """Backfill Step 1 for existing campaigns that have no steps."""
    from app.models.settings import Settings
    from app.models.campaign_step import CampaignStep
    from app.models.step_recipient import StepRecipient
    from app.models import Campaign, Recipient

    if Settings.get('campaign_steps_backfilled'):
        return

    campaigns_without_steps = (
        Campaign.query
        .filter(~Campaign.id.in_(
            db.session.query(CampaignStep.campaign_id).distinct()
        ))
        .all()
    )

    if not campaigns_without_steps:
        Settings.set('campaign_steps_backfilled', 'true')
        db.session.commit()
        return

    for campaign in campaigns_without_steps:
        step = CampaignStep(
            campaign_id=campaign.id,
            position=1,
            name='Initial Outreach',
            step_type='template',
            template_id=campaign.template_id,
            delay_days=0,
            status='completed' if campaign.status in ('completed', 'cancelled') else 'draft',
            total_recipients=campaign.total_recipients or 0,
            sent_count=campaign.sent_count or 0,
            failed_count=campaign.failed_count or 0,
        )
        db.session.add(step)
        db.session.flush()

        recipients = Recipient.query.filter_by(campaign_id=campaign.id).all()
        for r in recipients:
            sr_status = 'pending'
            if r.status in ('sent',):
                sr_status = 'sent'
            elif r.status in ('failed',):
                sr_status = 'failed'
            elif r.status in ('skipped',):
                sr_status = 'skipped'
            elif r.personalized_body:
                sr_status = 'ready'

            sr = StepRecipient(
                step_id=step.id,
                recipient_id=r.id,
                personalized_subject=r.personalized_subject,
                personalized_body=r.personalized_body,
                approved=r.approved or False,
                status=sr_status,
                sent_at=r.sent_at if hasattr(r, 'sent_at') else None,
            )
            db.session.add(sr)

    Settings.set('campaign_steps_backfilled', 'true')
    db.session.commit()
    app.logger.info(f'Backfilled steps for {len(campaigns_without_steps)} existing campaigns')
