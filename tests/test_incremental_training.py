"""Warm-start head remapping for incremental training (slow lane — imports torch).

No transformer checkpoints are loaded; ``_copy_head_rows`` is exercised on
tiny hand-built tensors that mimic a classification head growing new intents.
"""

from __future__ import annotations

import torch

from core.train_intent import _copy_head_rows


def _head(n_labels, hidden=4, fill=0.0):
    return {
        "classifier.weight": torch.full((n_labels, hidden), fill),
        "classifier.bias": torch.full((n_labels,), fill),
        "distilbert.embeddings.weight": torch.full((n_labels + 100, hidden), fill),
    }


class TestCopyHeadRows:
    def test_existing_intents_keep_weights_new_stay_fresh(self):
        old_map = {"close_app": 0, "open_app": 1}
        # 'brand_new' sorts between them → every id shifts. Mapping must be
        # by NAME, not by position.
        new_map = {"brand_new": 0, "close_app": 1, "open_app": 2}
        old = _head(2, fill=7.0)
        old["classifier.weight"][0].fill_(5.0)   # close_app row
        new = _head(3, fill=0.0)
        copied = _copy_head_rows(old, new, old_map, new_map)
        assert copied == 2   # classifier.weight + classifier.bias
        assert torch.all(new["classifier.weight"][1] == 5.0)   # close_app kept
        assert torch.all(new["classifier.weight"][2] == 7.0)   # open_app kept
        assert torch.all(new["classifier.weight"][0] == 0.0)   # brand_new fresh
        assert new["classifier.bias"][1].item() == 7.0

    def test_body_weights_never_touched(self):
        old_map = {"a": 0, "b": 1}
        new_map = {"a": 0, "b": 1, "c": 2}
        old = _head(2, fill=9.0)
        new = _head(3, fill=0.0)
        _copy_head_rows(old, new, old_map, new_map)
        # The fake embedding table's first dim coincidentally != label count,
        # and its name has no 'classifier' — must remain untouched.
        assert torch.all(new["distilbert.embeddings.weight"] == 0.0)

    def test_removed_intent_row_is_dropped_silently(self):
        old_map = {"gone_intent": 0, "open_app": 1}
        new_map = {"open_app": 0}
        old = _head(2, fill=3.0)
        new = _head(1, fill=0.0)
        copied = _copy_head_rows(old, new, old_map, new_map)
        assert copied == 2
        assert torch.all(new["classifier.weight"][0] == 3.0)

    def test_shape_mismatch_is_skipped_not_crashed(self):
        old_map = {"a": 0}
        new_map = {"a": 0, "b": 1}
        old = {"classifier.weight": torch.zeros((1, 8))}   # hidden 8
        new = {"classifier.weight": torch.zeros((2, 4))}   # hidden 4
        assert _copy_head_rows(old, new, old_map, new_map) == 0
