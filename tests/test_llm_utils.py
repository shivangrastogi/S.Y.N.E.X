"""Local-LLM utility skills — payload extraction + prompt building (mocked LLM)."""

from __future__ import annotations

import pytest


class _FakeLLM:
    def __init__(self, reply="FAKE", available=True):
        self.reply = reply
        self._av = available
        self.calls = []

    def available(self):
        return self._av

    def generate(self, prompt, system="", max_tokens=260, temperature=0.4):
        self.calls.append({"prompt": prompt, "system": system})
        return self.reply


@pytest.fixture
def fake(monkeypatch):
    import core.local_llm as ll
    f = _FakeLLM()
    monkeypatch.setattr(ll, "get", lambda: f)
    return f


class TestFixGrammar:
    def test_extracts_sentence_and_calls_llm(self, fake):
        from skills.llm_utils_skill import fix_grammar
        out = fix_grammar({"raw_text": "grammar theek karo he go to school"})
        assert out == "FAKE"
        assert "he go to school" in fake.calls[0]["prompt"]
        assert "grammar" in fake.calls[0]["system"].lower()

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import fix_grammar
        assert "Kaunsa sentence" in fix_grammar({"raw_text": "grammar theek karo"})
        assert fake.calls == []

    def test_no_model_message(self, monkeypatch):
        import core.local_llm as ll
        monkeypatch.setattr(ll, "get", lambda: _FakeLLM(available=False))
        from skills.llm_utils_skill import fix_grammar
        out = fix_grammar({"raw_text": "grammar theek karo he go to school"})
        assert "gguf" in out


class TestBrainstorm:
    def test_payload_trailing_keyword_kept(self, fake):
        # regression: "…ke ideas" must not be stripped as a second match
        from skills.llm_utils_skill import brainstorm_ideas
        brainstorm_ideas({"raw_text": "brainstorm karo chai startup ke naam ke ideas"})
        assert "chai startup ke naam" in fake.calls[0]["prompt"]

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import brainstorm_ideas
        assert "Kis baare" in brainstorm_ideas({"raw_text": "ideas do"})


class TestExplainSimply:
    def test_extracts_concept(self, fake):
        from skills.llm_utils_skill import explain_simply
        explain_simply({"raw_text": "simple bhasha me samjhao blockchain kya hai"})
        assert "blockchain" in fake.calls[0]["prompt"]
        assert "simple" in fake.calls[0]["system"].lower()

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import explain_simply
        assert "Kya samjhau" in explain_simply({"raw_text": "samjhao"})


class TestNoPersonaLeak:
    """These use the persona-free generate() path — no 'sir'/TTS-cap leak."""

    def test_systems_are_task_prompts(self, fake):
        from skills.llm_utils_skill import fix_grammar, explain_simply
        fix_grammar({"raw_text": "grammar theek karo test sentence here"})
        explain_simply({"raw_text": "samjhao gravity kya hai"})
        for c in fake.calls:
            assert "sir" not in c["system"].lower()


class TestMakeTitle:
    def test_extracts_text(self, fake):
        from skills.llm_utils_skill import make_title
        make_title({"raw_text": "iska title banao a robot learns to paint"})
        assert "robot learns to paint" in fake.calls[0]["prompt"]

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import make_title
        assert "Kis baare" in make_title({"raw_text": "title banao"})


class TestShortenText:
    def test_long_body_shortened(self, fake):
        from skills.llm_utils_skill import shorten_text
        long = "isko chhota karo " + ("this is a long sentence about aeris " * 3)
        shorten_text({"raw_text": long})
        assert "aeris" in fake.calls[0]["prompt"].lower()

    def test_short_body_prompts(self, fake, monkeypatch):
        import skills.llm_utils_skill as m
        # no clipboard fallback content
        monkeypatch.setitem(__import__("sys").modules, "pyperclip",
                            type("P", (), {"paste": staticmethod(lambda: "")}))
        from skills.llm_utils_skill import shorten_text
        assert "Kya chhota" in shorten_text({"raw_text": "tldr do"})


class TestDefineWord:
    def test_extracts_word(self, fake):
        from skills.llm_utils_skill import define_word
        define_word({"raw_text": "define karo serendipity"})
        assert "serendipity" in fake.calls[0]["prompt"]

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import define_word
        assert "Kaunsa word" in define_word({"raw_text": "define karo"})


class TestProsCons:
    def test_payload_before_keyword(self, fake):
        # regression: "<topic> ke fayde nuksan batao" — payload precedes cmd
        from skills.llm_utils_skill import pros_cons
        pros_cons({"raw_text": "electric car ke fayde nuksan batao"})
        assert "electric car" in fake.calls[0]["prompt"].lower()
        assert "pros" in fake.calls[0]["system"].lower()

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import pros_cons
        assert "Kis cheez" in pros_cons({"raw_text": "pros cons do"})


class TestHowTo:
    def test_keeps_task_verb(self, fake):
        from skills.llm_utils_skill import how_to_steps
        how_to_steps({"raw_text": "chai kaise banaye step by step batao"})
        p = fake.calls[0]["prompt"].lower()
        assert "chai" in p and "kaise banaye" in p   # verb retained

    def test_empty_prompts(self, fake):
        from skills.llm_utils_skill import how_to_steps
        assert "Kis kaam" in how_to_steps({"raw_text": "steps batao"})


class TestCreative:
    def test_poem_shayari_form(self, fake):
        from skills.llm_utils_skill import write_poem
        write_poem({"raw_text": "dosti pe shayari sunao"})
        p = fake.calls[0]["prompt"].lower()
        assert "shayari" in p and "dosti" in p

    def test_poem_english_form(self, fake):
        from skills.llm_utils_skill import write_poem
        write_poem({"raw_text": "nature pe ek poem likho"})
        assert "poem" in fake.calls[0]["prompt"].lower()
        assert "nature" in fake.calls[0]["prompt"].lower()

    def test_motivate_with_context(self, fake):
        from skills.llm_utils_skill import motivate_me
        motivate_me({"raw_text": "motivate karo mujhe exam ke liye"})
        assert "exam" in fake.calls[0]["prompt"].lower()

    def test_motivate_bare(self, fake):
        from skills.llm_utils_skill import motivate_me
        out = motivate_me({"raw_text": "himmat badhao"})
        assert out == "FAKE" and fake.calls

    def test_joke_calls_llm(self, fake):
        from skills.llm_utils_skill import tell_joke
        assert tell_joke({}) == "FAKE"
        assert "joke" in fake.calls[0]["prompt"].lower()

    def test_no_model_message(self, monkeypatch):
        import core.local_llm as ll
        monkeypatch.setattr(ll, "get", lambda: _FakeLLM(available=False))
        from skills.llm_utils_skill import tell_joke, write_poem
        assert "gguf" in tell_joke({})
        assert "gguf" in write_poem({"raw_text": "shayari sunao"})


class TestStoryRiddle:
    def test_story_with_theme(self, fake):
        from skills.llm_utils_skill import tell_story
        tell_story({"raw_text": "ek chhoti story sunao robot pe"})
        assert "robot" in fake.calls[0]["prompt"].lower()

    def test_story_bare(self, fake):
        from skills.llm_utils_skill import tell_story
        assert tell_story({"raw_text": "kahani sunao"}) == "FAKE"

    def test_riddle_calls_llm(self, fake):
        from skills.llm_utils_skill import tell_riddle
        assert tell_riddle({}) == "FAKE"
        assert "riddle" in fake.calls[0]["prompt"].lower()

    def test_no_model(self, monkeypatch):
        import core.local_llm as ll
        monkeypatch.setattr(ll, "get", lambda: _FakeLLM(available=False))
        from skills.llm_utils_skill import tell_story, tell_riddle
        assert "gguf" in tell_story({"raw_text": "kahani sunao"})
        assert "gguf" in tell_riddle({})


class TestSynonymsRephrase:
    def test_synonyms(self, fake):
        from skills.llm_utils_skill import synonyms_antonyms
        synonyms_antonyms({"raw_text": "happy ke synonyms batao"})
        assert "happy" in fake.calls[0]["prompt"].lower()
        assert "synonyms" in fake.calls[0]["prompt"].lower()

    def test_antonyms_detected(self, fake):
        from skills.llm_utils_skill import synonyms_antonyms
        synonyms_antonyms({"raw_text": "happy ka antonym batao"})
        assert "antonym" in fake.calls[0]["prompt"].lower()

    def test_synonym_empty(self, fake):
        from skills.llm_utils_skill import synonyms_antonyms
        assert "Kaunsa word" in synonyms_antonyms({"raw_text": "synonym batao"})

    def test_rephrase(self, fake):
        from skills.llm_utils_skill import rephrase_text
        rephrase_text({"raw_text": "rephrase karo I am very tired today"})
        assert "tired today" in fake.calls[0]["prompt"].lower()

    def test_rephrase_empty(self, fake):
        from skills.llm_utils_skill import rephrase_text
        assert "Kya rephrase" in rephrase_text({"raw_text": "rephrase karo"})


class TestFactCompliment:
    def test_fun_fact_topic(self, fake):
        from skills.llm_utils_skill import fun_fact
        fun_fact({"raw_text": "fun fact batao space ke baare me"})
        assert "space" in fake.calls[0]["prompt"].lower()

    def test_fun_fact_bare(self, fake):
        from skills.llm_utils_skill import fun_fact
        assert fun_fact({"raw_text": "fun fact batao"}) == "FAKE"

    def test_compliment(self, fake):
        from skills.llm_utils_skill import give_compliment
        assert give_compliment({"raw_text": "compliment do"}) == "FAKE"

    def test_no_model(self, monkeypatch):
        import core.local_llm as ll
        monkeypatch.setattr(ll, "get", lambda: _FakeLLM(available=False))
        from skills.llm_utils_skill import fun_fact, give_compliment
        assert "gguf" in fun_fact({"raw_text": "fun fact batao"})
        assert "gguf" in give_compliment({})
