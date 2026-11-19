// Whether — and where — AERIS may speak about a ringing call. AERIS behaves
// exactly like the ringtone: when the phone wouldn't ring out loud, AERIS
// stays quiet too — earbuds included (on silent / vibrate the earbuds don't
// get a ringtone either; checked on the phone, 2026-11-17).
//
//   Do Not Disturb             → quiet
//   silent / vibrate           → quiet (earbuds or not — the phone just vibrates)
//   ringer on, earbuds in      → earbuds only (never the phone speaker)
//   ringer on, no earbuds      → aloud (alarm channel)
import '../voice/io.dart';

enum RingerMode { normal, vibrate, silent }

/// The phone's audio situation when a call rings (read on the Android side,
/// android/.../calls/CallAudio.kt).
class AudioSituation {
  const AudioSituation({
    this.ringerMode = RingerMode.normal,
    this.doNotDisturb = false,
    this.earbudsConnected = false,
    this.earbudsName = '',
  });

  factory AudioSituation.fromMap(Map<String, Object?> map) => AudioSituation(
        ringerMode: RingerMode.values.asNameMap()[map['ringerMode']] ?? RingerMode.normal,
        doNotDisturb: map['doNotDisturb'] == true,
        earbudsConnected: map['earbuds'] == true,
        earbudsName: '${map['earbudsName'] ?? ''}',
      );

  final RingerMode ringerMode;
  final bool doNotDisturb;
  final bool earbudsConnected;
  final String earbudsName;

  /// For the call log, e.g. "vibrate, earbuds (Buds Air)".
  String describe() => [
        ringerMode.name,
        if (doNotDisturb) 'do not disturb',
        if (earbudsConnected) 'earbuds${earbudsName.isEmpty ? '' : ' ($earbudsName)'}' else 'no earbuds',
      ].join(', ');
}

/// How AERIS may speak during this ringing call, or null = stay completely quiet.
SpeechOutput? voiceForRingingCall(AudioSituation phone) {
  if (phone.doNotDisturb || phone.ringerMode != RingerMode.normal) return null;
  return phone.earbudsConnected ? SpeechOutput.ringingEarbudsOnly : SpeechOutput.ringingAloud;
}
