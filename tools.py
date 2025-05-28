# tools.py

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
import uuid
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# OAuth2 scopes and paths
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar",
]
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
TOKEN_PATH = os.getenv("TOKEN_PATH")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# Timezone for Mexico City
LOCAL_TZ = ZoneInfo("America/Mexico_City")

# Global service clients
_calendar_service = None
_oauth2_service   = None

def init_services():
    """
    Initialize and return authenticated Google Calendar and OAuth2 service clients.

    Raises:
        FileNotFoundError: if the OAuth2 client secrets JSON is missing.
    """
    global _calendar_service, _oauth2_service
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(f"Missing client secrets: {CREDENTIALS_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    _calendar_service = build("calendar", "v3", credentials=creds)
    _oauth2_service   = build("oauth2",   "v2", credentials=creds)
    return _calendar_service, _oauth2_service

def get_current_user_email() -> str:
    """
    Return the authenticated user's email.
    """
    global _oauth2_service
    if not _oauth2_service:
        _, _oauth2_service = init_services()
    return _oauth2_service.userinfo().get().execute().get("email")

def logout() -> str:
    """
    Revoke and delete stored credentials, logging the user out.

    Returns:
        Status message.
    """
    global _calendar_service, _oauth2_service
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        r = requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": creds.token},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        os.remove(TOKEN_PATH)
        _calendar_service = None
        _oauth2_service   = None
        return "Session successfully logged out." if r.status_code == 200 else \
               "Credentials removed, but revoke failed."
    return "No active session to log out."

@tool
def get_next_available_appointment() -> str:
    """
    Return the next free 30-minute slot in the next 24 hours, in CDMX local time.

    Returns:
        A string “YYYY-MM-DD HH:MM to HH:MM (CDT)”, or no-availability.
    """
    cal, _ = init_services()
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    events = (
        cal.events()
        .list(
            calendarId="primary",
            timeMin=now_utc.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    busy = [
        (
            datetime.fromisoformat(e["start"].get("dateTime", e["start"].get("date"))),
            datetime.fromisoformat(e["end"].get("dateTime",   e["end"].get("date")))
        )
        for e in events
    ]
    cursor = now_utc.replace(second=0, microsecond=0)
    for _ in range(48):
        end_slot = cursor + timedelta(minutes=30)
        if not any(not (end_slot <= b_start or cursor >= b_end) for b_start, b_end in busy):
            # convert to local
            start_local = cursor.astimezone(LOCAL_TZ)
            end_local   = end_slot.astimezone(LOCAL_TZ)
            return (f"{start_local.strftime('%Y-%m-%d %H:%M')} to "
                    f"{end_local.strftime('%Y-%m-%d %H:%M')} (CDT)")
        cursor = end_slot
    return "No available slots in the next 24 hours."

@tool
def get_all_available_appointments() -> list[str]:
    """
    Return all free 30-minute slots in the next 24 hours, in CDMX local time.

    Returns:
        List of “YYYY-MM-DD HH:MM to HH:MM (CDT)”.
    """
    cal, _ = init_services()
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    events = (
        cal.events()
        .list(
            calendarId="primary",
            timeMin=now_utc.isoformat(),
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    busy = [
        (
            datetime.fromisoformat(e["start"].get("dateTime", e["start"].get("date"))),
            datetime.fromisoformat(e["end"].get("dateTime",   e["end"].get("date")))
        )
        for e in events
    ]
    busy.sort(key=lambda x: x[0])
    slots = []
    cursor = now_utc.replace(second=0, microsecond=0)
    window_end = cursor + timedelta(hours=24)
    while cursor < window_end:
        end_slot = cursor + timedelta(minutes=30)
        if not any(not (end_slot <= b_start or cursor >= b_end) for b_start, b_end in busy):
            sl = cursor.astimezone(LOCAL_TZ)
            el = end_slot.astimezone(LOCAL_TZ)
            slots.append(f"{sl.strftime('%Y-%m-%d %H:%M')} to {el.strftime('%Y-%m-%d %H:%M')} (CDT)")
        cursor = end_slot
    return slots or ["No available slots in the next 24 hours."]

@tool
def book_appointment_by_slot(
    slot: str,
    first_name: str,
    last_name: str
) -> str:
    """
    Book exactly the given 30-minute slot (in CDMX local time).

    Args:
        slot:       "YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM (CDT)"
        first_name: Guest first name
        last_name:  Guest last name

    Returns:
        Confirmation string with Meet link & calendar URL.
    """
    cal, _ = init_services()
    # parse the local times
    times, _ = slot.split(" (")
    start_s, end_s = times.split(" to ")
    start_local = datetime.strptime(start_s, "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
    end_local   = datetime.strptime(end_s,   "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
    # convert to UTC
    start_dt = start_local.astimezone(timezone.utc)
    end_dt   = end_local.astimezone(timezone.utc)

    user_email = get_current_user_email()
    summary    = f"{first_name} {last_name}"
    req_id     = str(uuid.uuid4())
    event = {
        "summary": summary,
        "organizer": {"email": ADMIN_EMAIL},
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "UTC"},
        "attendees": [{"email": user_email}, {"email": ADMIN_EMAIL}],
        "conferenceData": {"createRequest": {"requestId": req_id, "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
    }
    created = cal.events().insert(calendarId="primary", body=event, conferenceDataVersion=1).execute()
    meet_link = created["conferenceData"]["entryPoints"][0]["uri"]
    html_link = created["htmlLink"]
    return (
        f"Booked '{summary}' from {slot}. "
        f"Attendees: you ({user_email}) & organizer ({ADMIN_EMAIL}). "
        f"Meet: {meet_link}. View: {html_link}"
    )

@tool
def cancel_appointment(
    appointment_year: int,
    appointment_month: int,
    appointment_day: int,
    appointment_hour: int,
    appointment_minute: int
) -> str:
    """
    Cancel the 30-minute event that starts at the given UTC time.
    """
    cal, _ = init_services()
    start_dt = datetime(
        appointment_year,
        appointment_month,
        appointment_day,
        appointment_hour,
        appointment_minute,
        tzinfo=timezone.utc,
    )
    tmin = start_dt.isoformat()
    tmax = (start_dt + timedelta(minutes=30)).isoformat()
    events = cal.events().list(calendarId="primary", timeMin=tmin, timeMax=tmax, singleEvents=True).execute().get("items", [])
    if not events:
        return f"No appointment at {tmin}"
    cal.events().delete(calendarId="primary", eventId=events[0]["id"]).execute()
    return f"Cancelled appointment at {tmin}"

def list_upcoming_appointments(max_results: int = 10) -> list[dict]:
    """
    Return the next upcoming events.
    """
    cal, _ = init_services()
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    items = cal.events().list(calendarId="primary", timeMin=now, maxResults=max_results, singleEvents=True, orderBy="startTime").execute().get("items", [])
    return [{"summary": e.get("summary","(no title)"), "start": e["start"].get("dateTime", e["start"].get("date")), "end": e["end"].get("dateTime", e["end"].get("date"))} for e in items]
