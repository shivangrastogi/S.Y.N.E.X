# AERIS Remote — build & connect

Flutter app that controls your laptop AERIS from anywhere. Encrypted
end-to-end through Firebase; no server, no IPs, no config sharing.

## One-time setup

### 1. Connect the app to your Firebase project
The laptop uses a service-account key; the phone uses a client config.
Easiest path — FlutterFire CLI (run from this folder):

```bash
dart pub global activate flutterfire_cli
flutterfire configure --project=aeris---personal-assistant
```

Pick **Android**. This generates `lib/firebase_options.dart` **and**
`android/app/google-services.json`. (If you prefer the console: download
`google-services.json` from Firebase → Project settings → your Android
app → drop it in `android/app/`.)

Then in `lib/main.dart` change:
```dart
await Firebase.initializeApp();
```
to:
```dart
await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
```
and add `import 'firebase_options.dart';`.

### 2. Enable in Firebase console (already done if you followed the plan)
- Firestore Database created (asia-south1)
- Authentication → Anonymous → Enabled
- Firestore Rules published (auth-gated bridge/** access)

### 3. Build & install
```bash
flutter pub get
flutter run          # phone plugged in with USB debugging
# or a shareable APK:
flutter build apk --release
# → build/app/outputs/flutter-apk/app-release.apk
```

## Pair & use
1. On the laptop, say / type: **"phone pair karo"** — a QR appears.
2. Open AERIS Remote → scan the QR. Done, forever.
3. Chat, tap quick actions (Lock / Screenshot / Battery…), or hold the
   mic and speak Hinglish. Green dot = laptop online.

## Kill switch
Say **"phone unpair karo"** on the laptop, or **Unpair this laptop** in
the app menu. The old key becomes useless instantly.

## Notes
- Android SDK min: bumped to 23 (secure storage + scanner need it).
- Permissions added: INTERNET, CAMERA (QR), RECORD_AUDIO (voice).
