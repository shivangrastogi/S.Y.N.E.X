"""Password generator + text hash + UUID (pure stdlib, offline)."""

from __future__ import annotations

import hashlib
import re
import uuid as _uuid

from core.gen_tools import generate_password, text_hash, generate_uuid


class TestPassword:
    def test_length_and_pools(self):
        body = generate_password("12 char password").split(": ")[1]
        assert len(body) == 12
        assert any(c.islower() for c in body)
        assert any(c.isupper() for c in body)
        assert any(c.isdigit() for c in body)

    def test_length_clamped(self):
        assert len(generate_password("500 char password").split(": ")[1]) == 64
        assert len(generate_password("2 char password").split(": ")[1]) == 6

    def test_no_symbol(self):
        body = generate_password("password bina symbol 12").split(": ")[1]
        assert not any(c in "!@#$%^&*-_=+?" for c in body)

    def test_uniqueness(self):
        a = generate_password("16 password")
        b = generate_password("16 password")
        assert a != b  # crypto-random — collision practically impossible


class TestHash:
    def test_sha256(self):
        out = text_hash("hello ka sha256 nikaalo")
        assert hashlib.sha256(b"hello").hexdigest() in out

    def test_md5_isolates_payload(self):
        out = text_hash("is text ka md5 banao aeris")
        assert hashlib.md5(b"aeris").hexdigest() in out

    def test_quoted_verbatim(self):
        out = text_hash('sha256 of "hello world"')
        assert hashlib.sha256(b"hello world").hexdigest() in out

    def test_empty_prompts(self):
        assert "Kis text" in text_hash("hash nikaalo")


class TestUUID:
    def test_single(self):
        out = generate_uuid("ek uuid banao").split("UUID: ")[1].strip()
        _uuid.UUID(out)  # raises if malformed

    def test_multiple(self):
        out = generate_uuid("3 uuid generate karo")
        found = re.findall(r"[0-9a-f-]{36}", out)
        assert len(found) == 3
        assert len(set(found)) == 3


class TestSkills:
    def test_pw_skill(self):
        from skills.gen_tools_skill import password_generate
        assert "Password" in password_generate({"raw_text": "strong password banao"})

    def test_hash_skill(self):
        from skills.gen_tools_skill import text_hash as th
        assert "SHA256" in th({"raw_text": "hello ka sha256 nikaalo"})

    def test_uuid_skill(self):
        from skills.gen_tools_skill import uuid_generate
        assert "UUID" in uuid_generate({"raw_text": "ek uuid banao"})
