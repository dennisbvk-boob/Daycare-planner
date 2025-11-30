"""
Daycare Planner Script
======================

This script reads babysitting appointments from a Google Sheet (with columns
``Week nummer``, ``Datum``, ``Oppas`` and ``Comments``) and emails
iCalendar invites to the babysitters and yourself.  Each invite is
an all‑day event titled ``Oppas – <oppas naam>`` on the specified
date and includes the comment as the description.

The script is intended to run periodically (for example via a GitHub
Actions workflow) and it does **not** require a Google developer
account.  Instead of using Google APIs, it fetches the sheet as a
CSV via a direct download link and sends invites via SMTP.

Environment variables
---------------------

The following environment variables must be set for the script to run:

``CSV_URL``
    The direct download link to the sheet in CSV format.  You can
    construct this by taking the sheet URL and replacing everything
    after the spreadsheet ID with ``/export?format=csv`` and, if
    necessary, appending ``&gid=...`` for a specific tab.  See
    the README for details and examples.

``SMTP_USERNAME``
    The email address used to send the invites (e.g. your Gmail address).

``SMTP_PASSWORD``
    The SMTP password or app password for the above account.  When using
    Gmail, you must enable 2‑factor authentication and create an
    app password.

``USER_EMAIL``
    (Optional) Your own email address.  If provided, you will be
    included as an attendee on all invites so that you receive them.

``EMAIL_MAP``
    (Optional) A JSON object mapping values from the ``Oppas`` column
    to corresponding email addresses.  For example::

        {
            "Opa Piet": "opa.piet@example.com",
            "Oma Lisa": "oma.lisa@example.com"
        }

    If a babysitter name is present in this mapping, the script will
    include that email address as an attendee on the invitation.  Any
    rows without a corresponding email in this mapping will still
    result in an invitation being created, but no email will be sent
    to the babysitter.

``SMTP_HOST`` and ``SMTP_PORT``
    (Optional) Override the default SMTP server (``smtp.gmail.com``)
    and port (``587``) if using a different provider.

Dependencies
------------

This script requires ``requests``, ``python-dateutil`` and the
standard library.  These will be installed in the accompanying
GitHub Actions workflow, but if you run the script locally you can
install them via::

    pip install requests python-dateutil

"""

import json
import os
import datetime
from typing import Dict, Any, List

from dateutil import parser as date_parser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import uuid
import requests
import csv


def fetch_csv_records(csv_url: str) -> List[Dict[str, Any]]:
    """Download and parse CSV data from a Google Sheet.

    Parameters
    ----------
    csv_url : str
        The direct CSV export URL of the Google Sheet.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries keyed by the CSV header row.
    """
    response = requests.get(csv_url)
    response.raise_for_status()
    # Decode the response content as UTF-8; Google CSVs are typically UTF-8.
    content = response.content.decode('utf-8')
    reader = csv.DictReader(content.splitlines())
    return [row for row in reader]


def build_smtp_client(host: str, port: int, username: str, password: str) -> smtplib.SMTP:
    """Authenticate and return an SMTP client for sending emails.

    Parameters
    ----------
    host : str
        SMTP server host (e.g. ``smtp.gmail.com``).
    port : int
        SMTP server port (e.g. 587 for TLS).
    username : str
        SMTP login username.
    password : str
        SMTP login password (for Gmail this should be an app password).

    Returns
    -------
    smtplib.SMTP
        An authenticated SMTP client.
    """
    client = smtplib.SMTP(host, port)
    client.starttls()
    client.login(username, password)
    return client


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


def build_ics_event(
    date_str: str,
    oppas_name: str,
    description: str,
    organizer_email: str,
    babysitter_email: str,
    user_email: str,
) -> str:
    """Create an iCalendar event string for emailing invitations.

    Parameters
    ----------
    date_str : str
        Date string from the sheet (parsed by ``parse_date``).
    oppas_name : str
        Name of the babysitter.
    description : str
        Event description from the sheet.
    organizer_email : str
        Email address used as the organiser (the SMTP login address).
    babysitter_email : str
        Email address of the babysitter (may be ``None``).
    user_email : str
        Email address of the user to include as attendee (may be ``None``).

    Returns
    -------
    str
        An RFC5545 iCalendar meeting invitation.
    """
    event_date = parse_date(date_str)
    start_date = event_date
    # End date is exclusive for all‑day events; for a one‑day event we add one day.
    end_date = event_date + datetime.timedelta(days=1)
    dtstamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    uid = f"{uuid.uuid4()}@daycare-planner"
    lines = [
        'BEGIN:VCALENDAR',
        'PRODID:-//Daycare Planner//EN',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        'METHOD:REQUEST',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART;VALUE=DATE:{start_date.strftime("%Y%m%d")}',
        f'DTEND;VALUE=DATE:{end_date.strftime("%Y%m%d")}',
        f'SUMMARY:Oppas – {oppas_name}',
        f'DESCRIPTION:{description}',
        f'ORGANIZER:MAILTO:{organizer_email}',
    ]
    # Add attendees
    if babysitter_email:
        lines.append(f'ATTENDEE;CN={oppas_name};RSVP=TRUE:MAILTO:{babysitter_email}')
    if user_email:
        # Avoid duplicate addresses
        if user_email != babysitter_email:
            lines.append(f'ATTENDEE;CN=Planner User;RSVP=TRUE:MAILTO:{user_email}')
    lines.extend([
        'END:VEVENT',
        'END:VCALENDAR',
    ])
    return '\r\n'.join(lines)


def main() -> None:
    """Main routine for the daycare planner.

    Loads credentials, reads the sheet, constructs .ics invitations and
    emails them via SMTP.  This version does not use the Google
    Calendar API; instead, recipients will receive iCalendar invites
    via email, which Gmail will interpret as calendar events.
    """
    csv_url = os.environ.get('CSV_URL')
    if not csv_url:
        raise EnvironmentError('CSV_URL must be set')

    user_email = os.environ.get('USER_EMAIL')
    email_map_str = os.environ.get('EMAIL_MAP', '{}')
    try:
        email_map: Dict[str, str] = json.loads(email_map_str)
    except json.JSONDecodeError:
        raise ValueError('EMAIL_MAP environment variable must be valid JSON')

    # SMTP configuration
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    if not smtp_username or not smtp_password:
        raise EnvironmentError('SMTP_USERNAME and SMTP_PASSWORD must be set')

    # Fetch the CSV data
    records = fetch_csv_records(csv_url)

    smtp_client = build_smtp_client(smtp_host, smtp_port, smtp_username, smtp_password)

    for row in records:
        date_str = row.get('Datum')
        oppas_name = row.get('Oppas')
        description = row.get('Comments', '')
        if not date_str or not oppas_name:
            print('Skipping row missing required fields')
            continue

        babysitter_email = email_map.get(oppas_name)
        # Build the iCalendar event
        ics_content = build_ics_event(
            date_str=date_str,
            oppas_name=oppas_name,
            description=description,
            organizer_email=smtp_username,
            babysitter_email=babysitter_email,
            user_email=user_email,
        )
        # Prepare the email
        recipients = []
        if babysitter_email:
            recipients.append(babysitter_email)
        if user_email and user_email not in recipients:
            recipients.append(user_email)
        if not recipients:
            # If no recipients, skip sending
            print(f'No recipients for {oppas_name}; skipping')
            continue
        msg = MIMEMultipart('mixed')
        msg['Subject'] = f'Oppas – {oppas_name} ({date_str})'
        msg['From'] = smtp_username
        msg['To'] = ', '.join(recipients)
        # Simple text body for clients that cannot handle calendar invites
        msg.attach(MIMEText('Zie de bijgevoegde kalenderuitnodiging.', 'plain', 'utf-8'))
        part = MIMEText(ics_content, 'calendar;method=REQUEST', 'utf-8')
        msg.attach(part)
        # Send the email
        try:
            smtp_client.sendmail(smtp_username, recipients, msg.as_string())
            print(f'Sent invite for {oppas_name} on {date_str} to {recipients}')
        except Exception as exc:
            print(f'Failed to send invite for {oppas_name} on {date_str}: {exc}')

    smtp_client.quit()


if __name__ == '__main__':
    main()