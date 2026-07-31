from app.agents import reporting


def test_reporting_continues_when_candidate_email_is_missing(monkeypatch):
    def missing_email(*args, **kwargs):
        raise ValueError("missing candidate email")

    monkeypatch.setattr(reporting, "send_decision", missing_email)

    result = reporting.run_reporting("run-1", {
        "goal": "AI Engineer",
        "top_candidate": "candidate-1",
        "shortlist": [{"ref_id": "candidate-1"}],
        "results": {"interview": {}},
    })

    assert result["decision"] == "ADVANCE"
    assert result["emails_sent"] == []
    assert result["email_errors"][0]["candidate_id"] == "candidate-1"
