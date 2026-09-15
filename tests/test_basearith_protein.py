"""Base-N arithmetic + protein needs (offline)."""

from __future__ import annotations

from core.number_props import base_arithmetic
from core.health_calc import protein_needs


class TestBaseArithmetic:
    def test_binary_add(self):
        out = base_arithmetic("1010 + 110 binary")
        assert "10000" in out and "16 (decimal)" in out

    def test_hex_add(self):
        out = base_arithmetic("ff + 1 hex")
        assert "100" in out and "256" in out

    def test_octal_multiply(self):
        out = base_arithmetic("17 * 2 octal")
        assert "36" in out and "30 (decimal)" in out

    def test_prompt(self):
        assert "Base batao" in base_arithmetic("add karo")


class TestProtein:
    def test_muscle(self):
        assert "112-154" in protein_needs("weight 70 protein muscle building")

    def test_active(self):
        assert "72-96" in protein_needs("60 kg protein active")

    def test_prompt(self):
        assert "Apna weight batao" in protein_needs("protein batao")


class TestSkills:
    def test_base_skill(self):
        from skills.number_props_skill import base_arithmetic as b
        assert "binary" in b({"raw_text": "1010 + 110 binary add karo"})

    def test_protein_skill(self):
        from skills.health_split_skill import protein_needs as p
        assert "protein" in p({"raw_text": "weight 70 protein kitna chahiye"})
