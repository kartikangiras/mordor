from notify import fallback, service, validate

WINDOWS = [{"fromIst": "08:00", "toIst": "10:00", "tier": "T1", "peakAqi": 280},
           {"fromIst": "10:00", "toIst": "16:00", "tier": "T2", "peakAqi": 350}]


def test_templates_pass_the_validator_for_every_tier():
    for tier in ("T0", "T1", "T2", "T3", "T4"):
        m = fallback.render("Govt Boys SSS Rohini Sector 3", "2026-10-09", tier, WINDOWS, 350)
        ok, reasons = validate.check(m)
        assert ok, (tier, reasons, m)
        assert m["chars"] <= 400 and m["hi"].startswith(("🌫", "🌤"))
        assert "closed" not in m["en"].lower() and "स्कूल बंद" not in m["hi"]


def test_template_names_concrete_times_from_windows():
    m = fallback.render("KV Rohini", "2026-10-09", "T2", WINDOWS, 350)
    assert "10 बजे" in m["hi"] and "10 am" in m["en"] and "3 pm" in m["en"]


def test_validator_rejects_bad_messages():
    bad = {"hi": "School closed tomorrow", "en": "स्कूल बंद"}
    ok, reasons = validate.check(bad)
    assert not ok and "hindi part must be in devanagari" in reasons
    long = {"hi": "🌫 " + "क" * 300, "en": "x" * 200 + " 3 pm"}
    assert "chars > 400" in " ".join(validate.check(long)[1])
    assert any("medication" in r for r in validate.check({"hi": "🌫 3 बजे दवा दें", "en": "give medicine at 3 pm"})[1])
    assert any("emergency" in r for r in validate.check({"hi": "🌫 3 बजे", "en": "emergency at 3 pm"})[1])
    assert any("emoji" in r for r in validate.check({"hi": "🌫 3 बजे 🌫", "en": "3 pm"})[1])


def test_service_falls_back_to_template_without_agent(monkeypatch):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    out = service.generate({"schoolId": "s1", "school": "KV Rohini", "date": "2026-10-09", "tier": "T2",
                            "windows": WINDOWS, "peakAqi": 350, "actions": ["pt_indoors"]}, use_agent=False)
    assert out["source"] == "template" and out["chars"] <= 400 and len(out["cacheKey"]) == 24
    # agent path with strands unreachable (no credentials) must also end in the template
    out2 = service.generate({"schoolId": "s1", "school": "KV Rohini", "date": "2026-10-09", "tier": "T2",
                             "windows": WINDOWS, "peakAqi": 350}, use_agent=True)
    assert out2["source"] in ("template", "agent") and out2["hi"]


def test_provider_prefers_anthropic_when_the_key_exists(monkeypatch):
    from common import aws
    from notify import agent
    aws.secret.cache_clear()
    monkeypatch.delenv("TABLE_NAME", raising=False)
    monkeypatch.delenv("DATA_BUCKET", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NOTIFY_PROVIDER", raising=False)
    assert agent.provider() == "none"              # no key anywhere: the template, never a hanging Bedrock call
    aws.secret.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert agent.provider() == "anthropic"
    monkeypatch.setenv("NOTIFY_PROVIDER", "bedrock")
    assert agent.provider() == "bedrock"           # Bedrock only when asked for explicitly
    aws.secret.cache_clear()


def test_agent_path_returns_the_structured_message(monkeypatch):
    import pytest
    pytest.importorskip("strands")
    import strands

    from notify import agent

    class FakeAgent:
        def __init__(self, **kw): self.kw = kw
        def __call__(self, prompt, structured_output_model=None):
            assert "KV Rohini" in prompt and structured_output_model is agent.ParentMessage
            return type("R", (), {"structured_output": agent.ParentMessage(hi="🌫 कल 10 बजे से", en="Mask for the 3 pm pickup")})()

    monkeypatch.setattr(strands, "Agent", FakeAgent)
    monkeypatch.setattr(agent, "_model", lambda: (object(), "anthropic"))
    out = agent.generate({"school": "KV Rohini", "date": "2026-10-11", "tier": "T2", "windows": WINDOWS})
    assert out == {"hi": "🌫 कल 10 बजे से", "en": "Mask for the 3 pm pickup"}
    monkeypatch.setattr(agent, "_model", lambda: (None, "none"))
    assert agent.generate({"school": "KV Rohini", "date": "2026-10-11", "tier": "T2", "windows": WINDOWS}) is None


def test_service_retries_once_with_the_validator_reasons(monkeypatch):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    from notify import agent as agent_mod
    calls = []
    def fake(inputs, feedback=None):
        calls.append(feedback)
        return {"hi": "🌫 कल खिड़कियाँ बंद", "en": "school closure tomorrow"} if feedback is None else {"hi": "🌫 कल 10 बजे से खिड़कियाँ बंद", "en": "Windows shut from 10 am; send a mask for the 3 pm pickup."}
    monkeypatch.setattr(agent_mod, "generate", fake)
    out = service.generate({"schoolId": "s9", "school": "KV Rohini", "date": "2026-10-11", "tier": "T2", "windows": WINDOWS, "peakAqi": 350}, use_agent=True)
    assert out["source"] == "agent" and len(calls) == 2 and calls[1] and any("closure" in r or "time" in r for r in calls[1])
