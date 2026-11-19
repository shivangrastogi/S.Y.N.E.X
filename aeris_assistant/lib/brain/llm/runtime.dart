// The LLM runtime behind the brain. [BrainRuntime] is the seam: the real
// one is llama.cpp via llamadart (a native worker isolate — never the UI
// thread); tests use a scripted fake.
//
// Phone facts (plan §4.1, measured on the RMX3741 with Qwen3 1.7B Q4_K_M):
// ~5.5 tok/s decode and a ~35 s cold prompt that drops to ~3 s once the
// system prompt's KV cache is reused. So: keep the long system prefix
// byte-stable, reuse it across turns (reusePromptPrefix), and persist its KV
// state to a file so even the first turn after an app restart is fast.
import 'dart:async';
import 'dart:io';

import 'package:llamadart/llamadart.dart';

class BrainGeneration {
  final String text;
  final int ms; // whole call
  final int firstTokenMs; // prompt processing + first token
  final int tokens; // generated (stream chunks — close to tokens)
  const BrainGeneration(this.text, this.ms, this.firstTokenMs, this.tokens);
  double get tokPerSec => tokens <= 1 || ms <= firstTokenMs ? 0 : (tokens - 1) * 1000 / (ms - firstTokenMs);
}

abstract class BrainRuntime {
  bool get isLoaded;
  Future<void> load(String modelPath, {int threads, int contextSize});

  /// Evaluate [prefix] so later prompts starting with it skip it. Loads the
  /// KV state from [cacheFile] when it matches, else computes and saves it.
  /// Returns true if the file was reused.
  Future<bool> warmPrefix(String prefix, String cacheFile);

  Future<BrainGeneration> complete(String prompt,
      {String? grammar, int maxTokens = 256, List<String> stop = const []});
  void cancel();
  Future<void> unload();
}

class LlamaRuntime implements BrainRuntime {
  LlamaEngine? _engine;
  int _ctx = 4096;

  @override
  bool get isLoaded => _engine?.isReady ?? false;

  @override
  Future<void> load(String modelPath, {int threads = 4, int contextSize = 4096}) async {
    await unload();
    final engine = LlamaEngine(LlamaBackend());
    _ctx = contextSize;
    await engine.loadModel(modelPath,
        modelParams: ModelParams(
          contextSize: contextSize,
          numberOfThreads: threads,
          numberOfThreadsBatch: threads,
          // CPU: Android Vulkan is opt-in/experimental in llama.cpp, and
          // Phase 0 found the Mali GPU path corrupting numbers in LiteRT.
          gpuLayers: 0,
        ));
    _engine = engine;
  }

  @override
  Future<bool> warmPrefix(String prefix, String cacheFile) async {
    final e = _engine!;
    final f = File(cacheFile);
    final tokens = await e.tokenize(prefix);
    if (e.supportsStatePersistence && await f.exists()) {
      try {
        final r = await e.stateLoadFile(cacheFile, tokenCapacity: _ctx);
        if (_sameTokens(r.tokens, tokens)) return true;
      } catch (_) {/* stale/foreign file → recompute below */}
    }
    // Evaluate the prefix without sampling, then snapshot the KV cache.
    await e.scoreNextToken(prefix, topK: 1);
    if (e.supportsStatePersistence) {
      try {
        await f.parent.create(recursive: true);
        await e.stateSaveFile(cacheFile, tokens: tokens);
      } catch (_) {/* a cache is an optimisation, never a failure */}
    }
    return false;
  }

  static bool _sameTokens(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  @override
  Future<BrainGeneration> complete(String prompt,
      {String? grammar, int maxTokens = 256, List<String> stop = const []}) async {
    final e = _engine!;
    final sw = Stopwatch()..start();
    var first = -1, n = 0;
    final b = StringBuffer();
    await for (final chunk in e.generate(prompt,
        params: GenerationParams(
          maxTokens: maxTokens,
          temp: 0.0, // greedy: same input → same action
          topK: 1,
          topP: 1.0,
          penalty: 1.0, // a repeat penalty would fight copying names/numbers
          seed: 1,
          grammar: grammar,
          stopSequences: stop,
          reusePromptPrefix: true,
        ))) {
      if (first < 0) first = sw.elapsedMilliseconds;
      n++;
      b.write(chunk);
    }
    return BrainGeneration(b.toString(), sw.elapsedMilliseconds, first < 0 ? sw.elapsedMilliseconds : first, n);
  }

  @override
  void cancel() => _engine?.cancelGeneration();

  @override
  Future<void> unload() async {
    final e = _engine;
    _engine = null;
    if (e != null) await e.dispose();
  }
}
