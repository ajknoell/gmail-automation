# Implementation Plan: Add Contacts to Running Campaign Feature

> **Status: Fully Implemented**
>
> All backend services, API endpoints, and frontend components described below have been built and integrated. This document is retained as a design reference.

## 1. Feature Overview

This feature allows users to add new contacts to campaigns that are already running (status: `running` or `sequence_active`). The feature supports three input methods:
- **Directory Contacts**: Select existing contacts from the contact directory
- **Manual Contact Entry**: Add a single new contact manually
- **Bulk CSV Import**: Upload a CSV file with multiple new contacts

### Availability Rules
- Available when campaign status is `running` or `sequence_active`
- Not available in `draft`, `paused`, `completed`, or `cancelled` states
- Cannot add contacts after campaign is completed
- New contacts should start receiving emails immediately at the current step

### New Contact Behavior
- **Single-step campaigns**: New contacts receive emails immediately (added to the running campaign queue)
- **Multi-step campaigns**: New contacts start at step 1 with the same timeline as original contacts (delayed start from enrollment date)

---

## 2. Backend Implementation

### 2.1 Database Models & Changes

#### Recipient Model Enhancement (`/home/user/gmail-automation/backend/app/models/recipient.py`)
Add new optional field to track when a recipient was added:
```
enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)  # Track when recipient was added to campaign
```

#### StepRecipient Model Update (`/home/user/gmail-automation/backend/app/models/step_recipient.py`)
No schema changes needed, but consider tracking enrollment timing when creating entries for new recipients.

#### New Migration
Create migration to add `enrolled_at` column to `recipients` table with default value of `created_at` for existing recipients.

### 2.2 Service Classes

#### New: `RecipientAdditionService` (`/home/user/gmail-automation/backend/app/services/recipient_addition.py`)

**Purpose**: Encapsulate logic for adding recipients to running campaigns

**Key Methods**:
```python
class RecipientAdditionService:
    @staticmethod
    def validate_can_add_recipients(campaign_id: int) -> tuple[bool, str]:
        """Check if campaign is in valid state to add recipients."""
        # Return (is_valid, error_message)
        # Valid states: running, sequence_active

    @staticmethod
    def add_directory_contact(campaign_id: int, contact_id: int) -> Recipient:
        """Add existing contact from directory to campaign."""
        # Check for duplicate
        # Create Recipient from Contact data
        # Generate StepRecipient entries if multi-step

    @staticmethod
    def add_manual_contact(campaign_id: int, contact_data: dict) -> Recipient:
        """Add manually entered contact to campaign."""
        # Validate email format
        # Create Contact in directory
        # Create Recipient in campaign
        # Generate StepRecipient entries if multi-step

    @staticmethod
    def bulk_add_from_csv(campaign_id: int, file_content: bytes, mapping: dict) -> dict:
        """Import contacts from CSV file."""
        # Reuse existing CSV parsing logic
        # Process duplicate handling
        # Return statistics (added, updated, skipped)

    @staticmethod
    def setup_step_recipients_for_new(campaign_id: int, recipient_ids: list[int]) -> None:
        """Create StepRecipient entries for newly added recipients."""
        # For each step in campaign:
        #   If step 1: create with status 'pending' (will be part of current queue)
        #   If step > 1: create with status 'pending' and scheduled send time
        #        accounting for enrollment delay

    @staticmethod
    def get_add_mode_for_campaign(campaign_id: int) -> str:
        """Determine whether to add immediately or queue for next step."""
        # Check campaign status and step position
        # Return 'immediate' or 'queued'
```

### 2.3 API Endpoints

#### POST `/api/campaigns/<int:id>/add-recipient`
**Purpose**: Add a single recipient (directory or manual)

**Request Body**:
```json
{
  "source": "directory|manual",
  "contact_id": 123,  // if source="directory"
  "email": "john@example.com",  // if source="manual"
  "name": "John Doe",
  "company": "Acme Corp",
  "custom_fields": {
    "title": "CEO",
    "industry": "SaaS"
  }
}
```

**Response**:
```json
{
  "success": true,
  "recipient": { /* Recipient object */ },
  "message": "Contact added and will receive email immediately",
  "duplicate": false,
  "immediately_added_to_queue": true
}
```

**Error Handling**:
- 400: Campaign not in valid state
- 400: Email already in campaign
- 400: Invalid email format
- 404: Campaign not found
- 404: Contact not found (if directory source)

#### POST `/api/campaigns/<int:id>/add-recipients-bulk`
**Purpose**: Bulk import recipients from CSV

**Request**: Multipart form data
- `file`: CSV file
- `mapping`: JSON string with field mapping (optional, auto-detected)

**Response**:
```json
{
  "success": true,
  "added": 10,
  "updated": 2,
  "skipped": 1,
  "duplicates": 3,
  "total_processed": 16,
  "message": "Added 10 new recipients, updated 2 existing, found 3 duplicates"
}
```

**Error Handling**:
- 400: Campaign not in valid state
- 400: No file provided
- 400: Invalid CSV format
- 400: No valid email addresses found

#### GET `/api/campaigns/<int:id>/add-recipient-status`
**Purpose**: Check if campaign can accept new recipients

**Response**:
```json
{
  "can_add": true,
  "campaign_status": "running",
  "step_count": 2,
  "current_recipients": 100,
  "message": "Campaign is running. New recipients will be added to step 1 queue."
}
```

### 2.4 Database Operations

#### Transaction Handling
All recipient additions should be wrapped in transactions:
```python
try:
    db.session.begin_nested()  # Savepoint
    # Add recipient(s)
    # Create StepRecipient entries
    # Update campaign.total_recipients
    db.session.commit()
except IntegrityError:
    db.session.rollback()
    # Return duplicate error
except Exception as e:
    db.session.rollback()
    # Return error
```

#### Duplicate Detection
```python
def check_duplicate(campaign_id: int, email: str) -> bool:
    existing = Recipient.query.filter(
        Recipient.campaign_id == campaign_id,
        Recipient.email == email.lower()
    ).first()
    return existing is not None
```

### 2.5 CampaignRunner Integration

#### Modifications to CampaignRunner (`/home/user/gmail-automation/backend/app/services/campaign_runner.py`)

**Dynamic Queue Addition**:
- Modify `_run_campaign` to check for new recipients during execution
- Add method to inject new recipient IDs into the processing queue
- Implement "pending new" status for recipients added after campaign start

```python
@classmethod
def add_new_recipients(cls, campaign_id: int, recipient_ids: list[int]) -> bool:
    """Add recipients to already-running campaign."""
    with cls._lock:
        if campaign_id not in cls._instances:
            return False
        state = cls._instances[campaign_id]
        # Append new IDs to the processing queue
        state.recipient_queue.extend(recipient_ids)
        return True
```

#### Modifications to StepRunner (`/home/user/gmail-automation/backend/app/services/step_runner.py`)

**Dynamic Step Recipient Addition**:
- Similar approach: allow adding new StepRecipient entries during step execution
- Queue them after current recipients with appropriate delays

### 2.6 Error Handling & Validation

#### Validation Logic
```python
def validate_recipient_data(email: str, name: str = None, company: str = None) -> tuple[bool, str]:
    """Validate recipient fields."""
    if not email or '@' not in email or len(email) > 255:
        return False, "Invalid email format"
    if name and len(name) > 100:
        return False, "Name too long (max 100 characters)"
    if company and len(company) > 100:
        return False, "Company too long (max 100 characters)"
    return True, ""
```

#### Campaign State Validation
```python
def validate_campaign_state(campaign: Campaign) -> tuple[bool, str]:
    """Check if campaign can receive new recipients."""
    if campaign.status not in ['running', 'sequence_active']:
        return False, f"Cannot add recipients to {campaign.status} campaign"
    if not campaign.template and not campaign.steps:
        return False, "Campaign has no template or steps configured"
    return True, ""
```

#### Duplicate Handling Policy
- **During upload**: Skip silently, count as processed
- **API responses**: Include duplicate count in response
- **UI notification**: Show count of duplicates skipped

---

## 3. Frontend Implementation

### 3.1 New Components

#### AddContactToRunningCampaignModal (`/home/user/gmail-automation/frontend/src/components/AddContactToRunningCampaignModal.jsx`)

**Features**:
- Three tabs: Directory, Manual, Bulk CSV
- Tab 1: Directory contact selection
  - Search/filter existing contacts
  - Select multiple or single contacts
  - Show contact details (last contacted, status)
- Tab 2: Manual entry form
  - Email, Name, Company fields
  - Optional custom fields
  - Real-time validation
- Tab 3: CSV bulk import
  - File upload
  - Field mapping preview
  - Progress indicator

**State Management**:
```javascript
const [activeTab, setActiveTab] = useState('directory');
const [selectedContacts, setSelectedContacts] = useState([]);
const [manualContactData, setManualContactData] = useState({ email: '', name: '', company: '' });
const [csvFile, setCsvFile] = useState(null);
const [csvMapping, setCsvMapping] = useState({});
const [isLoading, setIsLoading] = useState(false);
const [error, setError] = useState('');
```

#### ContactDirectoryPicker (`/home/user/gmail-automation/frontend/src/components/ContactDirectoryPicker.jsx`)

**Features**:
- Search contacts by name/email/company
- Filter by status and tags
- Select/deselect contacts with checkboxes
- Show last contacted date
- Disable already-added contacts

#### BulkAddProgress (`/home/user/gmail-automation/frontend/src/components/BulkAddProgress.jsx`)

**Features**:
- Progress bar for file processing
- Show added/updated/duplicate counts in real-time
- Error messages for invalid rows
- Success summary

### 3.2 Pages to Update

#### CampaignDetail.jsx (`/home/user/gmail-automation/frontend/src/pages/CampaignDetail.jsx`)

**Changes**:
1. Add "Add Contacts" button in campaign header when campaign is running
2. Button visibility logic:
   ```javascript
   const canAddContacts = ['running', 'sequence_active'].includes(campaign.status);
   ```
3. Open modal when clicked
4. Handle success callback to refresh recipient list
5. Show toast notification with results (added, duplicates)

**Implementation**:
```javascript
const [showAddModal, setShowAddModal] = useState(false);

const handleAddContacts = async (data) => {
  if (data.source === 'directory') {
    // Call addDirectoryContactsToCampaign API
  } else if (data.source === 'manual') {
    // Call addManualContactToCampaign API
  } else if (data.source === 'csv') {
    // Call addBulkContactsToCampaign API
  }
  // Refresh recipients on success
  loadRecipients();
  showToast(`Added ${data.added} new contacts`);
};
```

#### Contacts.jsx (`/home/user/gmail-automation/frontend/src/pages/Contacts.jsx`)

**Changes**:
1. Add "Add to Running Campaign" button in context menu for each contact
2. When clicked, show modal with list of running campaigns
3. Allow selecting target campaign and adding contact

### 3.3 UI Flows & States

#### Flow 1: Directory Contact Addition
```
User clicks "Add Contacts" →
Modal opens on "Directory" tab →
User searches/selects contacts →
Click "Add Selected" →
Loading spinner →
Success toast + modal closes →
Recipient list refreshes
```

#### Flow 2: Manual Contact Entry
```
User clicks "Add Contacts" →
Modal opens on "Manual" tab →
User fills email/name/company →
Click "Add Contact" →
Loading spinner →
Success toast →
Form clears →
Option to add another
```

#### Flow 3: Bulk CSV Import
```
User clicks "Add Contacts" →
Modal opens on "Bulk" tab →
User uploads CSV →
Auto-detection + mapping preview →
User confirms mapping →
Click "Import" →
Progress bar with real-time counts →
Success summary →
Modal closes
```

### 3.4 Form Validation

#### Email Validation
```javascript
const isValidEmail = (email) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};
```

#### Custom Fields Handling
```javascript
const [customFields, setCustomFields] = useState({});

const handleCustomFieldChange = (fieldName, value) => {
  setCustomFields(prev => ({
    ...prev,
    [fieldName]: value
  }));
};
```

---

## 4. Testing Strategy

### 4.1 Unit Tests

#### Backend Tests (`/home/user/gmail-automation/backend/tests/test_recipient_addition.py`)

**Tests for RecipientAdditionService**:
```python
class TestRecipientAdditionService(unittest.TestCase):

    def test_validate_can_add_recipients_running_campaign(self):
        """Campaign in 'running' state should allow additions."""
        # Create running campaign
        # Assert validation returns (True, "")

    def test_validate_can_add_recipients_draft_campaign(self):
        """Campaign in 'draft' state should reject additions."""
        # Create draft campaign
        # Assert validation returns (False, error_message)

    def test_add_directory_contact_success(self):
        """Add existing contact to campaign."""
        # Create campaign and contact
        # Call add_directory_contact
        # Assert Recipient created with correct data

    def test_add_directory_contact_duplicate(self):
        """Adding duplicate contact should be handled."""
        # Create campaign with existing recipient
        # Try to add same contact
        # Assert duplicate error returned

    def test_add_manual_contact_valid_email(self):
        """Add manually entered contact with valid email."""
        # Call add_manual_contact with valid data
        # Assert Recipient and Contact created

    def test_add_manual_contact_invalid_email(self):
        """Reject manually entered contact with invalid email."""
        # Call add_manual_contact with invalid email
        # Assert ValidationError raised

    def test_setup_step_recipients_single_step(self):
        """Single-step campaign: new recipients added to step 1."""
        # Create single-step campaign
        # Add new recipient
        # Assert StepRecipient created with correct step_id

    def test_setup_step_recipients_multi_step(self):
        """Multi-step campaign: new recipients follow timeline."""
        # Create 3-step campaign
        # Add new recipient
        # Assert StepRecipient entries created for all steps

    def test_bulk_add_from_csv_success(self):
        """Bulk add from CSV file."""
        # Create CSV file with test data
        # Call bulk_add_from_csv
        # Assert added count correct

    def test_bulk_add_from_csv_with_duplicates(self):
        """Bulk add handles duplicate emails."""
        # Create CSV with duplicate emails
        # Call bulk_add_from_csv
        # Assert duplicates counted correctly

    def test_bulk_add_from_csv_invalid_format(self):
        """Bulk add rejects invalid CSV format."""
        # Create malformed CSV
        # Call bulk_add_from_csv
        # Assert error returned
```

**Tests for API Endpoints**:
```python
class TestAddRecipientEndpoints(unittest.TestCase):

    def test_post_add_recipient_directory(self):
        """POST /api/campaigns/<id>/add-recipient with directory source."""
        # Create campaign and contact
        # Make request with directory source
        # Assert 200 response with recipient data

    def test_post_add_recipient_manual(self):
        """POST /api/campaigns/<id>/add-recipient with manual entry."""
        # Create campaign
        # Make request with manual contact data
        # Assert 201 response with created recipient

    def test_post_add_recipient_campaign_not_running(self):
        """POST /api/campaigns/<id>/add-recipient to non-running campaign."""
        # Create draft campaign
        # Make request
        # Assert 400 error

    def test_post_add_recipient_duplicate_email(self):
        """POST /api/campaigns/<id>/add-recipient with duplicate email."""
        # Create campaign with existing recipient
        # Try to add same email
        # Assert 400 error or duplicate flag in response

    def test_post_add_recipients_bulk(self):
        """POST /api/campaigns/<id>/add-recipients-bulk with CSV file."""
        # Create campaign and CSV file
        # Make multipart request
        # Assert 200 response with statistics

    def test_get_add_recipient_status(self):
        """GET /api/campaigns/<id>/add-recipient-status."""
        # Create running campaign
        # Make request
        # Assert correct status response
```

#### Frontend Tests (`/home/user/gmail-automation/frontend/src/components/__tests__/AddContactModal.test.jsx`)

```javascript
describe('AddContactToRunningCampaignModal', () => {

  test('renders modal with three tabs', () => {
    render(<AddContactToRunningCampaignModal campaignId={1} onClose={() => {}} />);
    expect(screen.getByText('Directory')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
    expect(screen.getByText('Bulk Import')).toBeInTheDocument();
  });

  test('disables submit button if no contacts selected', () => {
    render(<AddContactToRunningCampaignModal campaignId={1} onClose={() => {}} />);
    expect(screen.getByText('Add Selected')).toBeDisabled();
  });

  test('enables submit button when contact selected', async () => {
    render(<AddContactToRunningCampaignModal campaignId={1} onClose={() => {}} />);
    const contactCheckbox = screen.getByRole('checkbox', { name: /john@example.com/ });
    await userEvent.click(contactCheckbox);
    expect(screen.getByText('Add Selected')).toBeEnabled();
  });

  test('shows validation error for invalid email in manual mode', async () => {
    render(<AddContactToRunningCampaignModal campaignId={1} onClose={() => {}} />);
    await userEvent.click(screen.getByText('Manual'));
    await userEvent.type(screen.getByLabelText('Email'), 'invalid-email');
    expect(screen.getByText(/invalid email format/i)).toBeInTheDocument();
  });

  test('submits CSV file and shows progress', async () => {
    render(<AddContactToRunningCampaignModal campaignId={1} onClose={() => {}} />);
    // Test CSV upload flow
  });
});
```

### 4.2 Integration Tests

#### Campaign + Recipient Addition Flow
```python
class TestCampaignRecipientAdditionFlow(unittest.TestCase):

    def test_add_contacts_to_running_single_step_campaign(self):
        """Full flow: add contacts to running single-step campaign."""
        # Create template
        # Create campaign with template
        # Start campaign with initial recipients
        # Wait a moment for processing to start
        # Add new contacts
        # Assert new contacts in Recipient table
        # Assert they're queued for sending
        # Assert campaign.total_recipients updated

    def test_add_contacts_to_running_multi_step_campaign(self):
        """Full flow: add contacts to running multi-step campaign."""
        # Create multi-step campaign
        # Start step 1
        # Add new contacts mid-campaign
        # Assert StepRecipient entries created for all steps
        # Assert enrollment_at timestamp accurate

    def test_add_contacts_then_query_progress(self):
        """Add contacts and verify they appear in progress API."""
        # Create and start campaign
        # Add new contacts
        # Query progress endpoint
        # Assert total_recipients incremented

    def test_bulk_add_then_export_campaign(self):
        """Add contacts via bulk upload and export campaign results."""
        # Create and start campaign
        # Bulk add 10 recipients
        # Export campaign
        # Assert new recipients in export
```

### 4.3 Edge Cases & Constraints

#### Must Test:
1. **Duplicate Prevention**
   - Same email in directory contact already in campaign
   - Same email in manual entry already in campaign
   - Duplicate email within CSV file being imported
   - Case-insensitive email matching

2. **Campaign State Validation**
   - Cannot add to draft campaign
   - Cannot add to paused campaign (should allow? clarify requirement)
   - Cannot add to completed campaign
   - Cannot add to cancelled campaign
   - CAN add to running campaign
   - CAN add to sequence_active campaign

3. **Multi-Step Campaign Rules**
   - New recipients start at step 1
   - Respect delay_days between steps
   - Staggered start from enrollment date
   - Do not send step 2 email before step 1 delay expires
   - Handle if original recipients already moved to step 2

4. **Recipient State Management**
   - Newly added recipients have status='pending'
   - Approved status handled correctly
   - Personalized content generation for new recipients (if AI enabled)
   - Tracking data properly recorded in EmailLog

5. **Email Sending**
   - New recipients receive email with same template/content
   - Personalization applied if enabled
   - Subject/body properly formatted
   - Tracking pixel/links included
   - Email delays respected

6. **Contact Directory Integration**
   - Contact created in directory when adding manual recipient
   - Contact status updated to 'contacted' after email sent
   - Email history populated correctly

---

## 5. Implementation Order

### Phase 1: Core Backend (Days 1-2)
1. Add `enrolled_at` column to Recipient model and create migration
2. Implement `RecipientAdditionService` with validation logic
3. Create API endpoint: `POST /api/campaigns/<id>/add-recipient`
4. Create API endpoint: `POST /api/campaigns/<id>/add-recipients-bulk`
5. Create API endpoint: `GET /api/campaigns/<id>/add-recipient-status`
6. Integrate with CampaignRunner to handle dynamic additions
7. Write backend unit tests

### Phase 2: CampaignRunner & StepRunner Integration (Day 2-3)
1. Modify CampaignRunner to support adding new recipients mid-run
2. Modify StepRunner to support adding new recipients mid-step
3. Implement StepRecipient creation for multi-step campaigns
4. Handle enrollment timing for staggered step entry
5. Write integration tests for campaign + recipient flows

### Phase 3: Frontend UI (Days 3-4)
1. Create `AddContactToRunningCampaignModal` component
2. Create `ContactDirectoryPicker` component
3. Create `BulkAddProgress` component
4. Update CampaignDetail.jsx to show "Add Contacts" button
5. Implement tab switching and form state management
6. Add validation and error handling in UI
7. Write component tests

### Phase 4: Polish & Testing (Day 4-5)
1. End-to-end testing across all flows
2. Edge case testing (duplicates, state validation)
3. Error message clarity and UX
4. Performance testing with bulk imports
5. Documentation updates
6. Code review and cleanup

---

## 6. Key Constraints & Rules

### When Contacts Can Be Added
- Campaign status must be `running` or `sequence_active`
- Campaign must have a template OR steps configured
- User must have permission to modify the campaign

### Duplicate Handling Policy
- Check email (case-insensitive) against all existing recipients in campaign
- Show duplicate count in response
- Do NOT add duplicate recipients
- In CSV: skip duplicates, count as processed
- Return statistics: added, updated, duplicates, total

### Multi-Step Campaign Rules
- New recipients MUST start at step 1, not current step
- New recipients follow the same timeline delays as originals
- delay_days between steps applied from enrollment_at
- Do NOT send step N until step N-1 delay expires for that recipient
- If some original recipients already on step 2, new recipients still start step 1
- Handle resume timing: if campaign is paused mid-step, preserve behavior on resume

### Recipient State Management
- New recipients have status='pending'
- New recipients have approved=False by default
- If campaign has auto_send=true, set approved=True automatically
- Personalized content generated on-demand or in background (matching campaign behavior)
- enrolled_at timestamp tracks when recipient was added

### Email Sending & Timing
- New recipients added to running campaign should receive email ASAP (within next delay interval)
- Respect campaign.delay_seconds between emails
- Queue implementation: use recipient_id list or dedicated "new recipients" queue in CampaignRunner
- Do NOT retroactively apply prior step 1 email; new recipients get step 1 going forward

### Contact Directory Integration
- Adding directory contact creates Recipient (does not duplicate contact)
- Adding manual contact creates both Contact and Recipient
- Contact status='contacted' after first email sent
- Email history reflects all campaign emails

---

## 7. API Contract Summary

### New Endpoints

| Method | Endpoint | Purpose | Status Codes |
|--------|----------|---------|--------------|
| POST | `/api/campaigns/<id>/add-recipient` | Add single contact (directory or manual) | 200, 400, 404 |
| POST | `/api/campaigns/<id>/add-recipients-bulk` | Bulk import from CSV | 200, 400, 404 |
| GET | `/api/campaigns/<id>/add-recipient-status` | Check if campaign accepts additions | 200, 404 |

### Updated Endpoints

| Method | Endpoint | Changes |
|--------|----------|---------|
| GET | `/api/campaigns/<id>/recipients` | May return newly added recipients |
| POST | `/api/campaigns/<id>/start` | No changes (already supports running state) |

---

## 8. File Structure Summary

```
Backend New Files:
- /home/user/gmail-automation/backend/app/services/recipient_addition.py
- /home/user/gmail-automation/backend/app/migrations/versions/xxxx_add_enrolled_at.py

Backend Modified Files:
- /home/user/gmail-automation/backend/app/models/recipient.py (add enrolled_at field)
- /home/user/gmail-automation/backend/app/routes/campaigns.py (add 3 new endpoints)
- /home/user/gmail-automation/backend/app/services/campaign_runner.py (add dynamic queue)
- /home/user/gmail-automation/backend/app/services/step_runner.py (add dynamic queue)

Frontend New Files:
- /home/user/gmail-automation/frontend/src/components/AddContactToRunningCampaignModal.jsx
- /home/user/gmail-automation/frontend/src/components/ContactDirectoryPicker.jsx
- /home/user/gmail-automation/frontend/src/components/BulkAddProgress.jsx
- /home/user/gmail-automation/frontend/src/components/__tests__/AddContactModal.test.jsx

Frontend Modified Files:
- /home/user/gmail-automation/frontend/src/pages/CampaignDetail.jsx (add button and modal)
- /home/user/gmail-automation/frontend/src/pages/Contacts.jsx (add context menu option)
- /home/user/gmail-automation/frontend/src/api/client.js (add API calls)
```

---

## Critical Files for Implementation

### /home/user/gmail-automation/backend/app/models/recipient.py
**Reason**: Core data model update to add enrollment tracking. Must add `enrolled_at` column and update `to_dict()` method.

### /home/user/gmail-automation/backend/app/routes/campaigns.py
**Reason**: Primary API endpoint layer. Add 3 new endpoints for recipient addition with comprehensive validation and error handling.

### /home/user/gmail-automation/backend/app/services/recipient_addition.py
**Reason**: New service class containing all business logic for adding recipients. Central logic hub for validation, duplicate detection, and multi-step setup.

### /home/user/gmail-automation/frontend/src/pages/CampaignDetail.jsx
**Reason**: Primary UI integration point. Add "Add Contacts" button visibility logic, modal integration, and success handling. Critical for user interaction.

### /home/user/gmail-automation/frontend/src/components/AddContactToRunningCampaignModal.jsx
**Reason**: Core new component managing three-tab UI for contact addition methods (directory, manual, bulk). Handles all input methods and state management.
