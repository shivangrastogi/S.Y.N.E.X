// Bridge client — the phone's mirror of core/cloud_bridge.py.
//
// Sends encrypted messages to bridge/{pid}/toLaptop and listens on
// bridge/{pid}/toPhone. Mirrors the laptop's contract exactly:
//   - delete-on-read (no replay)
//   - {n, ct, ts} envelope, ts for staleness
//   - presence heartbeat at bridge/{pid}.phone_ts
import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'crypto.dart';
import 'pairing.dart';

class BridgeMessage {
  final String id;
  final String type; // response | event | phone_action | ...
  final String text;
  final String? replyTo;
  final Map<String, dynamic> extra;
  BridgeMessage(this.id, this.type, this.text, this.replyTo,
      [this.extra = const {}]);
}

class BridgeClient {
  final Pairing pairing;
  final BridgeCrypto _crypto;
  final _db = FirebaseFirestore.instance;
  StreamSubscription? _sub;
  Timer? _presence;

  BridgeClient(this.pairing) : _crypto = BridgeCrypto(pairing.keyBytes);

  DocumentReference get _root =>
      _db.collection('bridge').doc(pairing.pid);

  /// Send a chat/command to the laptop. Returns the message id used.
  Future<String> send(String text,
      {String type = 'chat', Map<String, dynamic> extra = const {}}) async {
    final id = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    final enc = await _crypto.encrypt({
      'id': id,
      'type': type,
      'text': text,
      'reply_to': null,
      'extra': extra,
    });
    // Firestore doc mixes String cipher fields with a numeric ts, so
    // build a dynamic map (enc is Map<String,String>).
    final doc = <String, dynamic>{
      ...enc,
      'ts': DateTime.now().millisecondsSinceEpoch / 1000.0,
    };
    await _root.collection('toLaptop').add(doc);
    return id;
  }

  /// Tell the laptop this phone's FCM token so it can push when closed.
  Future<void> registerToken(String token) =>
      send(token, type: 'register_token', extra: {'token': token})
          .then((_) {});

  /// Reply to a laptop 'get_battery' action with the phone's status.
  Future<void> sendStatus(Map<String, dynamic> status) =>
      send('phone_status', type: 'phone_status', extra: status).then((_) {});

  /// Stream of decrypted messages arriving from the laptop.
  Stream<BridgeMessage> incoming() {
    final controller = StreamController<BridgeMessage>();
    _sub = _root.collection('toPhone').snapshots().listen((snap) async {
      for (final change in snap.docChanges) {
        if (change.type != DocumentChangeType.added) continue;
        final d = change.doc;
        final data = d.data() as Map<String, dynamic>;
        await d.reference.delete(); // consume once
        final payload = await _crypto.decrypt(data);
        if (payload == null) continue;
        controller.add(BridgeMessage(
          (payload['id'] ?? '') as String,
          (payload['type'] ?? 'response') as String,
          (payload['text'] ?? '') as String,
          payload['reply_to'] as String?,
          (payload['extra'] as Map?)?.cast<String, dynamic>() ?? const {},
        ));
      }
    });
    return controller.stream;
  }

  /// True if the laptop's presence heartbeat is recent (<90s).
  Stream<bool> laptopOnline() {
    return _root.snapshots().map((snap) {
      final data = snap.data() as Map<String, dynamic>?;
      final ts = (data?['laptop_ts'] as num?)?.toDouble();
      if (ts == null) return false;
      final ageS = DateTime.now().millisecondsSinceEpoch / 1000.0 - ts;
      return ageS < 90;
    });
  }

  void startPresence() {
    _presence?.cancel();
    _presence = Timer.periodic(const Duration(seconds: 60), (_) {
      _root.set({'phone_ts': DateTime.now().millisecondsSinceEpoch / 1000.0},
          SetOptions(merge: true));
    });
    _root.set({'phone_ts': DateTime.now().millisecondsSinceEpoch / 1000.0},
        SetOptions(merge: true));
  }

  void dispose() {
    _sub?.cancel();
    _presence?.cancel();
  }
}
