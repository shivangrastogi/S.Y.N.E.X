"""JSON format + URL codec + slugify (stdlib, offline)."""

from __future__ import annotations

import json
from urllib.parse import quote

from core.dev_format import json_format, url_convert, slugify


class TestJson:
    def test_pretty(self):
        out = json_format('json format karo {"a":1,"b":[2,3]}')
        assert "Valid JSON" in out and '"a": 1' in out

    def test_minify(self):
        out = json_format('minify karo {"a": 1,  "b": 2}')
        assert '{"a":1,"b":2}' in out

    def test_invalid(self):
        assert "Invalid JSON" in json_format("json check karo {bad}")

    def test_no_json(self):
        assert "JSON do" in json_format("format karo hello")


class TestUrl:
    def test_encode(self):
        assert url_convert("url encode karo a b") == "URL encoded: " + quote("a b", safe="")

    def test_decode_roundtrip(self):
        assert "hello world & more" in url_convert(
            "url decode karo hello%20world%20%26%20more")

    def test_empty(self):
        assert "url-encode/decode" in url_convert("url karo").lower()


class TestSlug:
    def test_basic(self):
        assert slugify("slug banao My First Blog Post!") == "Slug: my-first-blog-post"

    def test_collapse(self):
        assert slugify("slugify karo  Ye Hai   AERIS 3.0  ") == "Slug: ye-hai-aeris-3-0"

    def test_empty(self):
        assert "Kis title" in slugify("slug banao !!!")


class TestSkills:
    def test_json_skill(self):
        from skills.dev_format_skill import json_format as j
        assert "Valid JSON" in j({"raw_text": 'json format karo {"x":1}'})

    def test_url_skill(self):
        from skills.dev_format_skill import url_convert as u
        assert "encoded" in u({"raw_text": "url encode karo hi there"})

    def test_slug_skill(self):
        from skills.dev_format_skill import slugify as s
        assert "hello-world" in s({"raw_text": "slug banao Hello World"})
