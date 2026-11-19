import '../core/models.dart';
import '../core/store.dart';
import 'io.dart';

/// Picks the listener from Settings: AERIS on-device (default) or Google.
class SwitchEars implements Ears {
  SwitchEars({required this.store, required this.local, required this.google});
  final Store store;
  final Ears local;
  final Ears google;

  Ears get _cur => store.settings.stt == SttEngine.google ? google : local;

  @override
  bool get available => _cur.available;
  @override
  Future<bool> init() => _cur.init();
  @override
  Future<void> listen({
    required String locale,
    required void Function(String partial) onPartial,
    required void Function(String text) onFinal,
    required void Function() onSilence,
    required void Function(String error) onError,
    required void Function(double level) onLevel,
    void Function()? onTranscribing,
    bool usePhoneMic = false,
  }) =>
      _cur.listen(
        locale: locale,
        onPartial: onPartial,
        onFinal: onFinal,
        onSilence: onSilence,
        onError: onError,
        onLevel: onLevel,
        onTranscribing: onTranscribing,
        usePhoneMic: usePhoneMic,
      );
  @override
  Future<void> stop() => _cur.stop();
  @override
  Future<void> cancel() async {
    await local.cancel();
    await google.cancel();
  }
}
