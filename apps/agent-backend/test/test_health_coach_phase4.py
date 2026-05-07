from app.medplum.health_coach import (
    build_medical_export_pdf_bytes,
    evaluate_alert_rules,
    run_synthetic_coach_evaluation,
)


def test_synthetic_coach_evaluation_passes() -> None:
    result = run_synthetic_coach_evaluation()

    assert result["passed"] is True
    assert {item["scenario"] for item in result["results"]} == {
        "donnees_absentes",
        "tendance_positive",
        "tendance_negative",
        "medicament_manquant",
        "symptome_inquietant",
    }


def test_alert_rules_detect_missing_medication() -> None:
    result = evaluate_alert_rules(
        {
            "dataQuality": {
                "freshness": {
                    "medications": {"latestDate": None, "daysSinceLatest": None},
                },
            },
            "spirometryTrends": [],
            "recentEvents": [],
        }
    )

    assert any(alert["ruleId"] == "medication_missing" for alert in result["alerts"])


def test_pdf_export_is_pdf() -> None:
    content = build_medical_export_pdf_bytes("# Test\ncontenu")

    assert content.startswith(b"%PDF-1.4")
    assert b"%%EOF" in content
