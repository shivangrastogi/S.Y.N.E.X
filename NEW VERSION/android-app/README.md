[//]: # (Path: d:\New folder (2) - JARVIS\android-app\README.md)
# JARVIS Mobile - Android App

This is the Android companion app for JARVIS. It enables your phone to communicate with the JARVIS desktop system.

## Features
- **Notification Sync**: Forwards all phone notifications to JARVIS
- **Accessibility Automation**: Allows JARVIS to control your phone (unlock, open apps, etc.)
- **Real-time Communication**: WebSocket connection for instant commands

## Setup Instructions

### 1. Open in Android Studio
1. Open Android Studio
2. Click "Open an Existing Project"
3. Navigate to this `android-app` folder
4. Wait for Gradle sync to complete

### 2. Enable Permissions
After installing the app on your phone:
1. Go to **Settings** → **Accessibility** → Enable "JARVIS Automation"
2. Go to **Settings** → **Notifications** → **Notification Access** → Enable "JARVIS Mobile"

### 3. Connect to JARVIS
1. Open the app
2. Enter your computer's IP address: `ws://192.168.1.X:8765`
   - Find your IP by running `ipconfig` on Windows or `ifconfig` on Mac/Linux
3. Tap **CONNECT**

## Usage
Once connected, JARVIS will:
- Speak your phone notifications aloud
- Show notifications in the desktop GUI
- Execute automation commands (unlock, open apps, etc.)

## Troubleshooting
- **Connection Failed**: Make sure your phone and computer are on the same Wi-Fi network
- **Notifications Not Working**: Check that Notification Access is enabled
- **Automation Not Working**: Check that Accessibility Service is enabled
