"""
Daycare Planner Script
======================

This script reads a Google Sheet with columns ``Week nummer``, ``Datum``,
``Oppas`` and ``Comments`` and creates all‑day Google Calendar events
for each row.  Each event is titled ``Oppas – <oppas naam>``, has
the corresponding date as the event date and uses the ``Comments`` field
as the description.

The script is intended to run periodically (for example via a GitHub
Actions workflow) and uses a Google service account to authenticate
against both the Sheets and Calendar APIs.  It also supports sending
invitations to the babysitter (the person in the ``Oppas`` column) and
to a default user email address.

Environment variables
---------------------

The following environment variables must be set for the script to run:

``GOOGLE_SERVICE_ACCOUNT``
    The JSON credentials for a Google service account with
    ``sheets.readonly`` and ``calendar`` scopes.  The JSON document
    should be provided as a single line string.  See the accompanying
    README.md for instructions on how to create this.

``GOOGLE_SHEET_ID``
    The ID of the Google Sheet containing the babysitting schedule.
    You can find this in the URL of the spreadsheet (the long string
    between ``/d/`` and ``/edit``).

``GOOGLE_CALENDAR_ID``
    The ID of the Google Calendar into which events should be added.
    For personal calendars this is usually your Gmail address.  For
    shared calendars you can find the ID under the calendar settings in
    Google Calendar.

``USER_EMAIL``
    (Optional) Your own email address.  If provided, you will be
    included as an attendee on all created events so that you receive
    invitations.

``EMAIL_MAP``
    (Optional) A JSON object mapping values from the ``Oppas`` column
    to corresponding email addresses.  For example::

        {
            "Opa Piet": "opa.piet@example.com",
            "Oma Lisa": "oma.lisa@example.com"
        }

    If a babysitter name is present in this mapping, the script will
    include that email address as an attendee on the event.  Any rows
    without a corresponding email in this mapping will still result in
    an event being created, but no invitation will be sent to the
    babysitter.

Dependencies
------------

This script requires ``gspread``, ``google-api-python-client``,
``google-auth``, and ``python-dateutil``.  These will be installed in
the accompanying GitHub Actions workflow, but if you run the script
locally you can install them via::

    pip install gspread google-api-python-client google-auth python-dateutil

"""

import json
import os
import datetime
from typing import Dict, Any, List

import gspread
from dateutil import parser as date_parser
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def load_service_account() -> Credentials:
    """Load Google service account credentials from the environment.

    Returns
    -------
    Credentials
        An authenticated credentials object with the required scopes.
    """
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if not credentials_json:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT environment variable is not set")
    try:
        info = json.loads(credentials_json)
    except json.JSONDecodeError as exc:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT does not contain valid JSON") from exc

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/calendar'
    ]
    return Credentials.from_service_account_info(info, scopes=scopes)


def get_sheet_records(sheet_id: str, creds: Credentials) -> List[Dict[str, Any]]:
    """Retrieve all rows from the first worksheet of a Google Sheet.

    Parameters
    ----------
    sheet_id : str
        The Google Sheet ID.
    creds : Credentials
        Authenticated Google credentials.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries keyed by column header.
    """
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.sheet1
    return worksheet.get_all_records()


def build_calendar_service(creds: Credentials):
    """Create a Google Calendar API client.

    Parameters
    ----------
    creds : Credentials
        Authenticated Google credentials.

    Returns
    -------
    googleapiclient.discovery.Resource
        A Calendar API service resource.
    """
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def parse_date(date_str: str) -> datetime.date:
    """Parse a date string into a ``datetime.date``.

    Accepts multiple common formats such as ``YYYY-MM-DD``, ``DD/MM/YYYY`` and
    locale-specific forms.  If parsing fails, a ``ValueError`` will be
    raised.

    Parameters
    ----------
    date_str : str
        The date string to parse.

    Returns
    -------
    datetime.date
        The parsed date.
    """
    # Use dateutil.parser for flexible parsing (dayfirst=True to prefer
    # Dutch/European formats).  ``fuzzy`` ignores unknown tokens like
    # extra comments.
    dt = date_parser.parse(date_str, dayfirst=True, fuzzy=False)
    return dt.date()


def create_event_body(row: Dict[str, Any], email_map: Dict[str, str], user_email: str) -> Dict[str, Any]:
    """Construct a Google Calendar event body from a sheet row.

    Parameters
    ----------
    row : dict
        The row from the spreadsheet, keyed by column headers.
    email_map : dict
        Mapping of babysitter names (Oppas) to their email addresses.
    user_email : str
        The default email to include on all events (may be ``None``).

    Returns
    -------
    dict
        The event definition to pass to the Calendar API.
    """
    date_str = row.get('Datum')
    oppas_name = row.get('Oppas')
    comments = row.get('Comments', '')

    if not date_str or not oppas_name:
        raise ValueError("Row must contain both 'Datum' and 'Oppas' fields")

    event_date = parse_date(date_str)
    start_date_iso = event_date.isoformat()
    end_date_iso = (event_date + datetime.timedelta(days=1)).isoformat()

    attendees = []
    babysitter_email = email_map.get(oppas_name)
    if babysitter_email:
        attendees.append({'email': babysitter_email})
    if user_email:
        attendees.append({'email': user_email})

    return {
        'summary': f'Oppas – {oppas_name}',
        'description': comments,
        'start': {'date': start_date_iso, 'timeZone': 'Europe/Amsterdam'},
        'end': {'date': end_date_iso, 'timeZone': 'Europe/Amsterdam'},
        'attendees': attendees,
    }


def main() -> None:
    """Main routine for the daycare planner.

    Loads credentials, reads the sheet, constructs events and inserts
    them into the target calendar.  Currently this script always
    creates events; it does not check for or update existing events.
    """
    sheet_id = os.environ.get('GOOGLE_SHEET_ID')
    calendar_id = os.environ.get('GOOGLE_CALENDAR_ID')
    if not sheet_id or not calendar_id:
        raise EnvironmentError('GOOGLE_SHEET_ID and GOOGLE_CALENDAR_ID must be set')

    user_email = os.environ.get('USER_EMAIL')
    email_map_str = os.environ.get('EMAIL_MAP', '{}')
    try:
        email_map = json.loads(email_map_str)
    except json.JSONDecodeError:
        raise ValueError('EMAIL_MAP environment variable must be valid JSON')

    creds = load_service_account()
    records = get_sheet_records(sheet_id, creds)
    calendar_service = build_calendar_service(creds)

    for row in records:
        try:
            event_body = create_event_body(row, email_map, user_email)
        except ValueError as exc:
            print(f'Skipping row due to error: {exc}')
            continue

        # Insert the event.  sendUpdates='all' ensures invites are sent.
        calendar_service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendUpdates='all'
        ).execute()
        print(f"Created event: {event_body['summary']} on {event_body['start']['date']}")


if __name__ == '__main__':
    main()