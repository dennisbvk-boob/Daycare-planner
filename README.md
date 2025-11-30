# Daycare Planner

Automate the process of scheduling babysitting duties between
grandparents and yourself using a shared Google Sheet and email
invitations.  This project provides a Python script and a GitHub
Actions workflow that runs hourly.  The workflow fetches the
spreadsheet as a CSV (via a public download link) and sends
iCalendar (`.ics`) invitations via email to the babysitter and to
you.  Gmail (via SMTP) can interpret these attachments and
automatically add the events to calendars.

## How it works

1. **Shared Spreadsheet** – Create a Google Sheet with the columns
   **Week nummer**, **Datum**, **Oppas**, and **Comments**.  Each row
   represents a babysitting appointment.  The `Datum` column should
   contain a date (e.g. `2025-12-24` or `24/12/2025`).  The
   `Oppas` column contains the babysitter's name.  Any text in the
   `Comments` column will appear in the event description.

2. **CSV export for Sheets** – To avoid the need for any Google
   developer account, publish the spreadsheet to the web or share it
   with “Anyone with the link” and use a direct CSV export link.  The
   script downloads this CSV and parses it to obtain the data.

3. **Email Invitations** – Instead of using the Google Calendar API,
   the script generates iCalendar invites and sends them via SMTP.
   When recipients use Gmail, these invites will show up as calendar
   events automatically.  To send mail via your own Gmail account
   without a Google developer project, you need to enable 2‑factor
   authentication and create an **app password** for SMTP (see
   instructions below).

4. **GitHub Actions** – A workflow defined in
   `.github/workflows/daycare_planner.yml` runs the script every hour.
   It reads the necessary secret values, installs dependencies and
   executes the script.  The workflow can also be run manually via the
   Actions tab.

## Setup instructions

### 1. Make the spreadsheet accessible

Because this version of the script does not use the Google API, it
needs to download the sheet as a CSV file.  You have two options:

1. **Share the sheet** – Open the sheet in Google Sheets, click
   **Share** and set the **General access** to **Anyone with the
   link** with **Viewer** access.  This makes the sheet readable
   without signing in.
2. **Publish to the web** – From the sheet menu, choose
   **File > Share > Publish to web**, select **Comma separated values
   (.csv)** and the specific tab you want to export.  Make sure the
   option to republish when changes are made is enabled.

Note the sheet ID (the long string between `/d/` and `/edit` in the
URL) and the sheet/tab ID (`gid`) for the tab you want to export.
You will use these values to construct the CSV export link for the
`CSV_URL` secret.

### 2. Create the required GitHub secrets

1. Go to your repository on GitHub and click on **Settings › Secrets
   and variables › Actions**.
2. Click **New repository secret** for each of the following keys:

   | Secret name                | Description                                                       |
   |----------------------------|-------------------------------------------------------------------|
   | `CSV_URL`                  | The direct download link for your sheet in CSV format.  Construct this as `https://docs.google.com/spreadsheets/d/ID/export?format=csv` for the first tab, or append `&gid=<sheet_id>` to export a specific tab【568067904121421†L63-L71】. |
   | `USER_EMAIL`               | *(Optional)* Your own email address to include on every invite. |
   | `EMAIL_MAP`                | *(Optional)* A JSON object mapping babysitter names to email addresses. Example: `{"Opa Piet": "opa.piet@example.com", "Oma Lisa": "oma.lisa@example.com"}` |
   | `SMTP_USERNAME`            | Your Gmail address (used to send email). |
   | `SMTP_PASSWORD`            | An **app password** generated in your Google account for SMTP.  See below. |
   | `SMTP_HOST` and `SMTP_PORT`| *(Optional)* Override the default SMTP server (`smtp.gmail.com`) and port (`587`) if using a different provider. |

   When entering JSON (for `GOOGLE_SERVICE_ACCOUNT` or `EMAIL_MAP`), paste
   it as a single line without line breaks.

### 3. Add and commit the code

The repository should contain at least the following files:

* `daycare_planner.py` – The Python script that reads the sheet and
  sends calendar invites via email.
* `.github/workflows/daycare_planner.yml` – The GitHub Actions
  workflow definition.

After adding these files, commit and push them to your repository.
GitHub Actions will automatically run the workflow on the schedule.

### 4. Verify the workflow

Once the secrets are configured and the code is committed, navigate to
the **Actions** tab in your repository.  You should see the
`Daycare Planner` workflow listed.  The first scheduled run will
occur at the next top of the hour, but you can trigger a manual run
via **Run workflow** to test your setup immediately.

During the run, the workflow will output log messages indicating
emails being sent.  Any errors (such as missing credentials or
invalid data) will appear in the logs.

## Customising the script

The default behaviour is to send a new invite for every row in the
sheet.  If you need to avoid duplicate emails or send updates only
when something changes, you could extend the script to record which
rows have been processed and skip them on subsequent runs.  This
implementation keeps things simple and is suitable when the sheet
contains the authoritative schedule.

### Generating an app password for Gmail

To send email via Gmail without using OAuth, you need to enable
2‑factor authentication on your Google account and then create an app
password for “Mail”.  Follow these steps:

1. Open <https://myaccount.google.com/apppasswords>.  (You may need
   to log in and complete 2‑factor verification.)
2. Under **Select app**, choose **Mail**.  Under **Select device**,
   choose **Other** and name it “Daycare Planner”.  Click **Generate**.
3. Copy the 16‑character password displayed.  This is your app
   password.  Store it as the `SMTP_PASSWORD` secret in GitHub.
4. Use your full Gmail address as the `SMTP_USERNAME` secret.

If you use another email provider, adjust `SMTP_HOST`, `SMTP_PORT`
and provide the appropriate username and password.

Feel free to open pull requests if you want to enhance the
functionality or adapt it to your needs.