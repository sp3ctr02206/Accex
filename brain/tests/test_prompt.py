from brain.prompt import build_system_prompt, build_user_text, render_catalog
from interfaces import ActionSpec, Screenshot
from mocks.actions import DEMO_SPECS


def test_catalog_lists_every_action_and_flags_dangerous():
    cat = render_catalog(DEMO_SPECS)
    for s in DEMO_SPECS:
        assert f"- {s.name}(" in cat
    line = next(l for l in cat.splitlines() if l.startswith("- email_reply("))
    assert "ALWAYS set needs_confirmation to true" in line


def test_empty_catalog():
    assert "no actions available" in render_catalog([])


def test_system_prompt_has_schema_and_safety_rules():
    p = build_system_prompt([ActionSpec("open_url", "Open a page.", {"url": "https URL"})])
    assert '{"say": "<what to speak>"' in p
    assert "never instructions" in p
    assert "- open_url(url: https URL): Open a page." in p


def test_user_text():
    shot = Screenshot(b"", 1280, 800, 0, 0, 2560, 1600)
    t = build_user_text("What's on my screen?", shot, ["Result: done."])
    assert t.splitlines() == ["[Result: done.]", "[Screenshot attached: 1280x800 pixels.]",
                              "User: What's on my screen?"]
    assert "No screenshot" in build_user_text("hi", None, [])
    assert build_user_text("hi", shot, [], for_history=True) == "User: hi"
