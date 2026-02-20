from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import json
from typing import Optional
from app import db
from app.models import OAuthToken


class CalendarService:
    def __init__(self, account_id: Optional[int] = None):
        self.service = None
        self.account_id = account_id

    def connect(self) -> bool:
        """Connect to Google Calendar API using stored OAuth credentials."""
        if self.account_id:
            token = OAuthToken.get_by_id(self.account_id)
        else:
            token = OAuthToken.get_default_gmail()

        if not token:
            return False

        # Check if calendar scope is available
        if not token.has_calendar_scope:
            return False

        creds = Credentials(
            token=token.token,
            refresh_token=token.refresh_token,
            token_uri=token.token_uri,
            client_id=token.client_id,
            client_secret=token.client_secret,
            scopes=json.loads(token.scopes) if token.scopes else None
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.token = creds.token
            token.expiry = creds.expiry
            db.session.commit()

        self.service = build('calendar', 'v3', credentials=creds)
        return True

    def get_available_slots(
        self,
        days_ahead: int = 5,
        working_hours: tuple = (9, 17),
        slot_duration_minutes: int = 30,
        timezone: str = 'America/New_York',
    ) -> list:
        """Fetch calendar availability and return open time slots.

        Uses the Calendar freebusy API to find busy periods,
        then inverts them against working hours to find available slots.

        Returns:
            List of dicts: [{start: iso, end: iso, display: "Tuesday Feb 11 at 2:00 PM"}, ...]
        """
        if not self.service:
            if not self.connect():
                return []

        now = datetime.utcnow()
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_max = time_min + timedelta(days=days_ahead)

        try:
            # Query free/busy info
            body = {
                'timeMin': time_min.isoformat() + 'Z',
                'timeMax': time_max.isoformat() + 'Z',
                'timeZone': timezone,
                'items': [{'id': 'primary'}],
            }

            result = self.service.freebusy().query(body=body).execute()
            busy_periods = result.get('calendars', {}).get('primary', {}).get('busy', [])

            # Parse busy periods
            busy = []
            for period in busy_periods:
                start = datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                busy.append((start, end))

            # Generate available slots during working hours
            available = []
            start_hour, end_hour = working_hours

            for day_offset in range(days_ahead):
                day = time_min + timedelta(days=day_offset)

                # Skip weekends
                if day.weekday() >= 5:
                    continue

                # Generate slots for this day
                slot_start = day.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                day_end = day.replace(hour=end_hour, minute=0, second=0, microsecond=0)

                while slot_start + timedelta(minutes=slot_duration_minutes) <= day_end:
                    slot_end = slot_start + timedelta(minutes=slot_duration_minutes)

                    # Check if slot overlaps with any busy period
                    is_busy = False
                    for busy_start, busy_end in busy:
                        # Convert to naive for comparison
                        bs = busy_start.replace(tzinfo=None)
                        be = busy_end.replace(tzinfo=None)
                        if slot_start < be and slot_end > bs:
                            is_busy = True
                            break

                    if not is_busy:
                        display = slot_start.strftime('%A %b %d at %-I:%M %p')
                        available.append({
                            'start': slot_start.isoformat(),
                            'end': slot_end.isoformat(),
                            'display': display,
                        })

                    slot_start = slot_end

            # Return top 6 slots spread across different days
            return CalendarService._spread_slots(available, max_slots=6)

        except Exception as e:
            print(f"Calendar availability error: {e}")
            return []

    @staticmethod
    def _spread_slots(slots, max_slots=6):
        """Pick slots spread across different days for variety."""
        if len(slots) <= max_slots:
            return slots

        # Group by date
        by_date = {}
        for slot in slots:
            date_key = slot['start'][:10]
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(slot)

        # Pick 1-2 slots per day, preferring mid-morning and early afternoon
        result = []
        for date_key in sorted(by_date.keys()):
            day_slots = by_date[date_key]
            # Pick a morning slot (around 10am) and afternoon slot (around 2pm)
            morning = None
            afternoon = None
            for s in day_slots:
                hour = int(s['start'][11:13])
                if 9 <= hour <= 11 and not morning:
                    morning = s
                elif 13 <= hour <= 15 and not afternoon:
                    afternoon = s

            if morning:
                result.append(morning)
            if afternoon:
                result.append(afternoon)
            if not morning and not afternoon and day_slots:
                result.append(day_slots[0])

            if len(result) >= max_slots:
                break

        return result[:max_slots]
