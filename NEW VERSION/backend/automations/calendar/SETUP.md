# Google Calendar API Setup Guide

To use the Google Calendar integration in JARVIS without using someone else's credentials, follow these steps to create your own `credentials.json` file.

## Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top and select **New Project**.
3. Give it a name (e.g., "JARVIS-Calendar") and click **Create**.

## Step 2: Enable Google Calendar API
1. In the sidebar, go to **APIs & Services > Library**.
2. Search for "Google Calendar API".
3. Click on it and then click **Enable**.

## Step 3: Configure OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** (if you don't have a Workspace account) and click **Create**.
3. Fill in the **App Information** (App name: JARVIS, User support email: your email).
4. Scroll down, add your email to **Developer contact information**, and click **Save and Continue**.
5. In the **Scopes** section, click **Save and Continue** (you don't need to add scopes here yet).
6. In **Test users**, click **Add Users** and add your own Google email. This is CRITICAL for the app to work while in "Testing" mode.
7. Click **Save and Continue**, then click **Back to Dashboard**.

## Step 4: Create Credentials
1. Go to **APIs & Services > Credentials**.
2. Click **+ Create Credentials** at the top and select **OAuth client ID**.
3. Select **Desktop app** as the Application type.
4. Name it "JARVIS Laptop" and click **Create**.
5. A popup will show your Client ID and Client Secret. Click **OK**.

## Step 5: Download and Placement
1. In the list of OAuth 2.0 Client IDs, click the **Download icon** (Download JSON) for the one you just created.
2. Rename the downloaded file to exactly `credentials.json`.
3. Move this file into the following folder in your JARVIS directory:
   `backend/automations/calendar/config/`

## Step 6: Connect in JARVIS
1. Restart JARVIS.
2. Go to **Settings > Integrations**.
3. Click **Connect Google Calendar**.
4. A browser window will open. Log in with your Google account.
5. If you see a "Google hasn't verified this app" warning, click **Advanced** and then **Go to JARVIS (unsafe)**. This is normal for personal projects.
6. Once you see "The authentication flow is complete", you are all set!

---
> [!TIP]
> Each user can follow these steps to have their own private integration. JARVIS will keep each person's data separate automatically.
