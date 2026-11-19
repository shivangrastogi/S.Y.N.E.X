import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'pairing.dart';
import '../ui/theme.dart';

// One-time pairing: scan the QR that AERIS shows on the laptop
// ("phone pair karo"). The key rides in the QR — never over the network.
class PairScreen extends StatefulWidget {
  final void Function(Pairing) onPaired;
  const PairScreen({super.key, required this.onPaired});

  @override
  State<PairScreen> createState() => _PairScreenState();
}

class _PairScreenState extends State<PairScreen> {
  bool _handled = false;
  String? _error;

  void _onDetect(BarcodeCapture cap) {
    if (_handled) return;
    for (final b in cap.barcodes) {
      final raw = b.rawValue;
      if (raw == null) continue;
      final p = Pairing.fromQr(raw);
      if (p != null) {
        _handled = true;
        widget.onPaired(p);
        return;
      }
    }
    setState(() => _error = 'Ye AERIS ka QR nahi lagta — laptop pe '
        '"phone pair karo" bolo.');
  }

  @override
  Widget build(BuildContext context) {
    final bad = _error != null;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 36),
            const AerisOrb(size: 74, online: true, active: true),
            const SizedBox(height: 18),
            const Text(
              'A E R I S',
              style: TextStyle(
                color: A.text,
                fontSize: 26,
                fontWeight: FontWeight.w600,
                letterSpacing: 8,
              ),
            ),
            const SizedBox(height: 8),
            A.label('link a laptop'),
            const SizedBox(height: 30),
            // Scanner inside an accent-framed viewfinder.
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 30),
                child: LayoutBuilder(
                  builder: (_, box) {
                    final side = box.maxWidth.clamp(0.0, 340.0);
                    return Center(
                      child: SizedBox(
                        width: side,
                        height: side,
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(22),
                              child: ColorFiltered(
                                colorFilter: const ColorFilter.mode(
                                    Color(0x11000000), BlendMode.darken),
                                child: MobileScanner(onDetect: _onDetect),
                              ),
                            ),
                            const IgnorePointer(
                              child: CustomPaint(painter: _ViewfinderPainter()),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: 22),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: Container(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
                decoration: BoxDecoration(
                  color: A.panel,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: bad ? A.hot : A.line),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(bad ? Icons.error_outline : Icons.qr_code_2,
                        color: bad ? A.hot : A.accent, size: 22),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _error ??
                            'Laptop pe bolo "phone pair karo" — jo QR aaye use '
                                'yahan point karo. Bas ek baar.',
                        style: TextStyle(
                          color: bad ? A.hot : A.muted,
                          height: 1.45,
                          fontSize: 13.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Corner brackets + a hairline frame — a scanner viewfinder, not a plain box.
class _ViewfinderPainter extends CustomPainter {
  const _ViewfinderPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(
        Offset.zero & size, const Radius.circular(22));
    canvas.drawRRect(
      rrect,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = A.line,
    );

    const len = 30.0;
    const inset = 10.0;
    final p = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..shader = A.gradient.createShader(Offset.zero & size);
    final w = size.width, h = size.height;
    // TL
    canvas.drawPath(
        Path()
          ..moveTo(inset, inset + len)
          ..lineTo(inset, inset)
          ..lineTo(inset + len, inset),
        p);
    // TR
    canvas.drawPath(
        Path()
          ..moveTo(w - inset - len, inset)
          ..lineTo(w - inset, inset)
          ..lineTo(w - inset, inset + len),
        p);
    // BL
    canvas.drawPath(
        Path()
          ..moveTo(inset, h - inset - len)
          ..lineTo(inset, h - inset)
          ..lineTo(inset + len, h - inset),
        p);
    // BR
    canvas.drawPath(
        Path()
          ..moveTo(w - inset - len, h - inset)
          ..lineTo(w - inset, h - inset)
          ..lineTo(w - inset, h - inset - len),
        p);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
