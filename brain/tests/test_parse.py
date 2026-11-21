from brain.parse import EMPTY_REPLY, parse_llm_reply
from interfaces import Action


def test_clean_json():
    r = parse_llm_reply('{"say": "Hi.", "action": null, "needs_confirmation": false}')
    assert r.say == "Hi." and r.action is None and r.needs_confirmation is False


def test_fenced_json_with_action():
    text = ('```json\n{"say": "Opening YouTube.", "action": {"type": "open_url", '
            '"params": {"url": "https://youtube.com"}}, "needs_confirmation": false}\n```')
    r = parse_llm_reply(text)
    assert r.action == Action("open_url", {"url": "https://youtube.com"})
    assert r.raw == text


def test_prose_around_json_and_braces_inside_strings():
    r = parse_llm_reply('Sure! {"say": "It says {draft}.", "action": null} Hope that helps.')
    assert r.say == "It says {draft}."


def test_skips_unrelated_json_object():
    assert parse_llm_reply('{"a": 1} then {"say": "Real answer."}').say == "Real answer."


def test_flat_action_params_and_string_bool():
    r = parse_llm_reply('{"say": "Sending?", "action": {"type": "email_reply", '
                        '"body": "Thanks"}, "needs_confirmation": "true"}')
    assert r.action == Action("email_reply", {"body": "Thanks"})
    assert r.needs_confirmation is True


def test_action_without_type_is_dropped():
    r = parse_llm_reply('{"say": "Ok.", "action": {"params": {}}}')
    assert r.action is None and r.say == "Ok."


def test_action_only_keeps_empty_say():
    r = parse_llm_reply('{"action": {"type": "scroll", "params": {"direction": "down"}}}')
    assert r.say == "" and r.action.type == "scroll"


def test_plain_text_fallback():
    r = parse_llm_reply("The chart shows rising sales.")
    assert r.say == "The chart shows rising sales." and r.action is None


def test_broken_json_falls_back_to_text():
    r = parse_llm_reply('{"say": "unterminated')
    assert r.say.startswith('{"say"') and r.action is None


def test_empty_reply():
    assert parse_llm_reply("").say == EMPTY_REPLY
    assert parse_llm_reply('{"say": "", "action": null}').say == EMPTY_REPLY


def test_long_text_is_truncated():
    r = parse_llm_reply("word " * 500)
    assert len(r.say) <= 404 and r.say.endswith("...")
