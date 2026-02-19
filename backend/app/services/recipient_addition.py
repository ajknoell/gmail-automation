"""Service for adding recipients to running campaigns."""
from datetime import datetime
from flask import current_app
from app import db
from app.models.recipient import Recipient
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.campaign_step import CampaignStep
from app.models.step_recipient import StepRecipient
import csv
import io
import json


def _notify_campaign_runner(campaign_id: int, recipient_ids: list):
    """Notify the campaign runner about new recipients if campaign is running."""
    try:
        from app.services.campaign_runner import CampaignRunner
        CampaignRunner.add_new_recipients(campaign_id, recipient_ids)
    except Exception as e:
        # Log but don't fail if runner notification fails
        current_app.logger.warning(f"Failed to notify campaign runner: {str(e)}")


class RecipientAdditionException(Exception):
    """Exception raised for recipient addition errors."""
    pass


class RecipientAdditionService:
    """Service for adding recipients to running campaigns."""

    @staticmethod
    def validate_can_add_recipients(campaign_id: int) -> tuple[bool, str]:
        """
        Check if campaign is in a valid state to add recipients.

        Args:
            campaign_id: ID of the campaign to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        campaign = Campaign.query.get(campaign_id)

        if not campaign:
            return False, "Campaign not found"

        if campaign.status not in ['running', 'sequence_active']:
            return False, f"Cannot add recipients to {campaign.status} campaign"

        if not campaign.template and not campaign.steps:
            return False, "Campaign has no template or steps configured"

        return True, ""

    @staticmethod
    def validate_recipient_data(email: str, name: str = None, company: str = None) -> tuple[bool, str]:
        """
        Validate recipient fields.

        Args:
            email: Email address
            name: Contact name
            company: Company name

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email or '@' not in email or len(email) > 255:
            return False, "Invalid email format"

        if name and len(name) > 100:
            return False, "Name too long (max 100 characters)"

        if company and len(company) > 100:
            return False, "Company too long (max 100 characters)"

        return True, ""

    @staticmethod
    def check_duplicate(campaign_id: int, email: str) -> bool:
        """
        Check if email already exists in campaign.

        Args:
            campaign_id: ID of the campaign
            email: Email address to check

        Returns:
            True if duplicate exists, False otherwise
        """
        existing = Recipient.query.filter(
            Recipient.campaign_id == campaign_id,
            Recipient.email == email.lower()
        ).first()
        return existing is not None

    @staticmethod
    def add_directory_contact(campaign_id: int, contact_id: int, auto_approve: bool = None) -> Recipient:
        """
        Add existing contact from directory to campaign.

        Args:
            campaign_id: ID of the campaign
            contact_id: ID of the contact to add
            auto_approve: Whether to auto-approve (defaults to campaign setting)

        Returns:
            Created Recipient object

        Raises:
            RecipientAdditionException: If operation fails
        """
        # Validate campaign
        is_valid, error = RecipientAdditionService.validate_can_add_recipients(campaign_id)
        if not is_valid:
            raise RecipientAdditionException(error)

        # Get contact
        contact = Contact.query.get(contact_id)
        if not contact:
            raise RecipientAdditionException("Contact not found")

        # Check for duplicate
        if RecipientAdditionService.check_duplicate(campaign_id, contact.email):
            raise RecipientAdditionException(f"Email {contact.email} already in campaign")

        # Get campaign
        campaign = Campaign.query.get(campaign_id)

        # Create recipient
        recipient = Recipient(
            campaign_id=campaign_id,
            email=contact.email,
            name=contact.name,
            company=contact.company,
            approved=auto_approve if auto_approve is not None else False,
            enrolled_at=datetime.utcnow()
        )

        db.session.add(recipient)
        db.session.flush()  # Get the ID without committing

        # Setup step recipients
        try:
            RecipientAdditionService.setup_step_recipients_for_new(campaign_id, [recipient.id])
            db.session.commit()

            # Notify campaign runner if campaign is running
            _notify_campaign_runner(campaign_id, [recipient.id])

            return recipient
        except Exception as e:
            db.session.rollback()
            raise RecipientAdditionException(f"Failed to add recipient: {str(e)}")

    @staticmethod
    def add_manual_contact(campaign_id: int, contact_data: dict, auto_approve: bool = None) -> Recipient:
        """
        Add manually entered contact to campaign.

        Args:
            campaign_id: ID of the campaign
            contact_data: Dict with keys: email, name, company, custom_fields
            auto_approve: Whether to auto-approve (defaults to campaign setting)

        Returns:
            Created Recipient object

        Raises:
            RecipientAdditionException: If operation fails
        """
        # Validate campaign
        is_valid, error = RecipientAdditionService.validate_can_add_recipients(campaign_id)
        if not is_valid:
            raise RecipientAdditionException(error)

        email = contact_data.get('email', '').lower()
        name = contact_data.get('name', '')
        company = contact_data.get('company', '')
        custom_fields = contact_data.get('custom_fields', {})

        # Validate data
        is_valid, error = RecipientAdditionService.validate_recipient_data(email, name, company)
        if not is_valid:
            raise RecipientAdditionException(error)

        # Check for duplicate
        if RecipientAdditionService.check_duplicate(campaign_id, email):
            raise RecipientAdditionException(f"Email {email} already in campaign")

        try:
            # Create or update contact in directory
            contact = Contact.query.filter_by(email=email).first()
            if not contact:
                contact = Contact(
                    email=email,
                    name=name,
                    company=company,
                    status='contacted'
                )
                db.session.add(contact)
                db.session.flush()

            # Create recipient
            recipient = Recipient(
                campaign_id=campaign_id,
                email=email,
                name=name or contact.name,
                company=company or contact.company,
                approved=auto_approve if auto_approve is not None else False,
                enrolled_at=datetime.utcnow()
            )

            if custom_fields:
                recipient.set_custom_fields(custom_fields)

            db.session.add(recipient)
            db.session.flush()

            # Setup step recipients
            RecipientAdditionService.setup_step_recipients_for_new(campaign_id, [recipient.id])
            db.session.commit()

            # Notify campaign runner if campaign is running
            _notify_campaign_runner(campaign_id, [recipient.id])

            return recipient
        except Exception as e:
            db.session.rollback()
            raise RecipientAdditionException(f"Failed to add contact: {str(e)}")

    @staticmethod
    def setup_step_recipients_for_new(campaign_id: int, recipient_ids: list[int]) -> None:
        """
        Create StepRecipient entries for newly added recipients.

        For each step in the campaign:
        - Step 1: create with status 'pending' (will be part of current queue)
        - Step N>1: create with status 'pending' and scheduled per campaign delays

        Args:
            campaign_id: ID of the campaign
            recipient_ids: List of recipient IDs to setup

        Raises:
            RecipientAdditionException: If operation fails
        """
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            raise RecipientAdditionException("Campaign not found")

        steps = CampaignStep.query.filter_by(campaign_id=campaign_id).order_by(CampaignStep.order).all()

        if not steps:
            # Single-step campaign - no StepRecipient needed
            return

        # Create StepRecipient for each step
        for recipient_id in recipient_ids:
            for step in steps:
                step_recipient = StepRecipient(
                    step_id=step.id,
                    recipient_id=recipient_id,
                    status='pending'
                )
                db.session.add(step_recipient)

    @staticmethod
    def bulk_add_from_csv(campaign_id: int, file_content: bytes, mapping: dict = None) -> dict:
        """
        Import contacts from CSV file.

        Args:
            campaign_id: ID of the campaign
            file_content: CSV file content as bytes
            mapping: Optional field mapping dict {csv_column: recipient_field}

        Returns:
            Dict with statistics: {added: int, updated: int, skipped: int, duplicates: int, total_processed: int}

        Raises:
            RecipientAdditionException: If operation fails
        """
        # Validate campaign
        is_valid, error = RecipientAdditionService.validate_can_add_recipients(campaign_id)
        if not is_valid:
            raise RecipientAdditionException(error)

        try:
            # Parse CSV
            text_content = file_content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text_content))

            if not reader.fieldnames:
                raise RecipientAdditionException("Invalid CSV format")

            # Auto-detect mapping if not provided
            if not mapping:
                mapping = RecipientAdditionService._detect_csv_mapping(reader.fieldnames)

            added_count = 0
            updated_count = 0
            duplicate_count = 0
            skipped_count = 0
            new_recipient_ids = []

            for row in reader:
                email = row.get(mapping.get('email', 'email'), '').strip().lower()

                if not email or '@' not in email:
                    skipped_count += 1
                    continue

                # Check for duplicate
                if RecipientAdditionService.check_duplicate(campaign_id, email):
                    duplicate_count += 1
                    continue

                name = row.get(mapping.get('name', 'name'), '').strip()
                company = row.get(mapping.get('company', 'company'), '').strip()

                # Validate
                is_valid, error = RecipientAdditionService.validate_recipient_data(email, name, company)
                if not is_valid:
                    skipped_count += 1
                    continue

                try:
                    # Create or update contact in directory
                    contact = Contact.query.filter_by(email=email).first()
                    if not contact:
                        contact = Contact(
                            email=email,
                            name=name,
                            company=company,
                            status='contacted'
                        )
                        db.session.add(contact)
                        db.session.flush()

                    # Create recipient
                    recipient = Recipient(
                        campaign_id=campaign_id,
                        email=email,
                        name=name or contact.name,
                        company=company or contact.company,
                        approved=False,
                        enrolled_at=datetime.utcnow()
                    )

                    db.session.add(recipient)
                    db.session.flush()
                    new_recipient_ids.append(recipient.id)
                    added_count += 1
                except Exception as e:
                    current_app.logger.warning(f"Failed to add recipient {email}: {str(e)}")
                    skipped_count += 1

            # Setup step recipients for all new recipients
            if new_recipient_ids:
                RecipientAdditionService.setup_step_recipients_for_new(campaign_id, new_recipient_ids)

            db.session.commit()

            # Notify campaign runner if campaign is running
            if new_recipient_ids:
                _notify_campaign_runner(campaign_id, new_recipient_ids)

            return {
                'added': added_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'duplicates': duplicate_count,
                'total_processed': added_count + updated_count + skipped_count + duplicate_count,
                'new_recipient_ids': new_recipient_ids
            }
        except Exception as e:
            db.session.rollback()
            raise RecipientAdditionException(f"Failed to import CSV: {str(e)}")

    @staticmethod
    def _detect_csv_mapping(fieldnames: list) -> dict:
        """
        Auto-detect CSV column to recipient field mapping.

        Args:
            fieldnames: List of CSV field names

        Returns:
            Dict mapping {recipient_field: csv_column}
        """
        mapping = {}
        fieldnames_lower = [f.lower() for f in fieldnames]

        # Email field (required)
        for variant in ['email', 'email_address', 'e-mail', 'emailaddress']:
            if variant in fieldnames_lower:
                idx = fieldnames_lower.index(variant)
                mapping['email'] = fieldnames[idx]
                break

        # Name field
        for variant in ['name', 'full_name', 'fullname', 'contact_name']:
            if variant in fieldnames_lower:
                idx = fieldnames_lower.index(variant)
                mapping['name'] = fieldnames[idx]
                break

        # Company field
        for variant in ['company', 'company_name', 'organization', 'org']:
            if variant in fieldnames_lower:
                idx = fieldnames_lower.index(variant)
                mapping['company'] = fieldnames[idx]
                break

        return mapping
