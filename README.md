# Daycare Planner

Automate the process of scheduling babysitting duties between
grandparents and yourself using a shared Google Sheet and Google
Calendar.  This project provides a Python script and a GitHub Actions
workflow that runs hourly.  The workflow reads rows from a Google
Sheet and creates corresponding all‑day events in a specified
Google Calendar, sending invitations to the babysitter and to you.

## How it works

1. **Shared Spreadsheet** – Create a Google Sheet with the columns
   **Week nummer**, **Datum**, **Oppas**, and **Comments**.  Each row
   represents a babysitting appointment.  The `Datum` column should
   contain a date (e.g. `2025-12-24` or `24/12/2025`).  The
   `Oppas` column contains the babysitter's name.  Any text in the
   `Comments` column will appear in the event description.

2. **Service Account** – The script uses a Google service account to
   read from the sheet and write to the calendar.  You must create a
   service account in the Google Cloud console, download its JSON
   credentials and store them in a GitHub secret.  See below for
   detailed steps.

3. **GitHub Actions** – A workflow defined in
   `.github/workflows/daycare_planner.yml` runs the script every hour.
   It reads the necessary secret values, installs dependencies and
   executes the script.  The workflow can also be run manually via the
   Actions tab.

## Setup instructions

### 1. Create a Google service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and
   create a new project or select an existing one.
2. Navigate to **APIs & Services › Enabled APIs & services** and
   enable the **Google Sheets API** and **Google Calendar API**.
3. Go to **IAM & Admin › Service accounts** and click **Create
   service account**.
4. Give it a name (e.g. `daycare-planner`) and click **Create and
   Continue**.
5. On the next screen, grant the service account the role
   **Editor** (or a more restrictive role if you prefer) and finish
   creation.
6. Click the new service account, go to the **Keys** tab and click
   **Add key › Create new key**.  Select **JSON** and download the
   key.  Keep this file safe — it contains your credentials.

### 2. Share the sheet and calendar with the service account

The service account behaves like a separate user.  You need to share
both the Google Sheet and the target calendar with it.

1. **Sheet** – Open the Google Sheet and click **Share**.  Add the
   service account’s email address (found in the JSON credentials under
   `client_email`) with **Editor** access.
2. **Calendar** – In Google Calendar, go to the calendar’s settings
   and under **Share with specific people**, add the service account’s
   email with **Make changes to events** permission.

### 3. Create the required GitHub secrets

1. Go to your repository on GitHub and click on **Settings › Secrets
   and variables › Actions**.
2. Click **New repository secret** for each of the following keys:

   | Secret name            | Description                                                       |
   |------------------------|-------------------------------------------------------------------|
   | `GOOGLE_SERVICE_ACCOUNT` | Paste the entire JSON credentials file content on a single line. |
   | `GOOGLE_SHEET_ID`      | The ID of your spreadsheet (the portion between `/d/` and `/edit` in the URL). |
   | `GOOGLE_CALENDAR_ID`   | The ID of the calendar where events should be created (often your Gmail address). |
   | `USER_EMAIL`           | *(Optional)* Your own email address to include on every event.    |
   | `EMAIL_MAP`            | *(Optional)* A JSON object mapping babysitter names to email addresses. Example: `{"Opa Piet": "opa.piet@example.com", "Oma Lisa": "oma.lisa@example.com"}` |

   When entering JSON (for `GOOGLE_SERVICE_ACCOUNT` or `EMAIL_MAP`), paste
   it as a single line without line breaks.

### 4. Add and commit the code

The repository should contain at least the following files:

* `daycare_planner.py` – The Python script that reads the sheet and
  writes to the calendar.
* `.github/workflows/daycare_planner.yml` – The GitHub Actions
  workflow definition.

After adding these files, commit and push them to your repository.
GitHub Actions will automatically run the workflow on the schedule.

### 5. Verify the workflow

Once the secrets are configured and the code is committed, navigate to
the **Actions** tab in your repository.  You should see the
`Daycare Planner` workflow listed.  The first scheduled run will
occur at the next top of the hour, but you can trigger a manual run
via **Run workflow** to test your setup immediately.

During the run, the workflow will output log messages indicating
events being created.  Any errors (such as missing credentials or
invalid data) will appear in the logs.

## Customising the script

The default behaviour is to create a new all‑day event for every row
in the sheet.  If you need to avoid duplicate events or update
existing ones, you could extend the script to search for existing
events and update them instead of always inserting new ones.  This
basic implementation keeps things simple and is suitable when the
sheet contains the authoritative schedule.

Feel free to open pull requests if you want to enhance the
functionality or adapt it to your needs.