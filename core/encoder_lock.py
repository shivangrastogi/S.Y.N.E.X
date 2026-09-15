"""Global lock guarding the shared sentence encoder.

The one ``SentenceTransformer`` (``JarvisBrain.classifier.encoder``) is
reused by THREE call sites that can run on different threads at once:

  * the brain's intent prediction  (brain worker thread, in process_text)
  * the chat gate                  (same, but a second encode per turn)
  * semantic memory                (its OWN background embed thread)

A torch model's forward/``.to()`` is NOT thread-safe: two ``.encode()``
calls on the same model object concurrently corrupt the heap
(observed live — Windows fatal 0xC0000374 inside torch ``convert`` when
the semantic-memory embed thread and the chat-gate encode overlapped on
the same command). Every encode of the shared model MUST hold this lock.

RLock so a single thread re-entering (e.g. predict → gate) never
self-deadlocks.
"""
import threading

ENCODER_LOCK = threading.RLock()
