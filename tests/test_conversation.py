from core.conversation import ConversationHistory


def test_add_and_export():
    h = ConversationHistory(max_turns=2)
    h.add_user("hi")
    h.add_assistant("hello!")
    msgs = h.as_messages()
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "hi"}
    assert msgs[1] == {"role": "assistant", "content": "hello!"}


def test_max_turns_drops_oldest():
    h = ConversationHistory(max_turns=2)  # cap = 4 messages
    for i in range(3):
        h.add_user(f"u{i}")
        h.add_assistant(f"a{i}")
    msgs = h.as_messages()
    assert len(msgs) == 4
    # u0/a0 should have been evicted by the deque
    assert msgs[0]["content"] == "u1"
    assert msgs[-1]["content"] == "a2"


def test_sentiment_tracked_on_user_turn():
    h = ConversationHistory()
    h.add_user("bahut accha", sentiment_label="positive")
    h.add_assistant("thanks!")
    assert h.last_user_sentiment() == "positive"


def test_clear():
    h = ConversationHistory()
    h.add_user("hi")
    h.add_assistant("hello")
    h.clear()
    assert len(h) == 0
    assert h.as_messages() == []
