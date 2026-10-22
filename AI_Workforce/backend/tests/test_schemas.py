from app.schemas import RequirementsAnalysis


def test_requirements_analysis_defaults_are_structured():
    analysis = RequirementsAnalysis.model_validate(
        {
            "project_summary": {"summary": "An account registration service."},
            "functional_requirements": [
                {
                    "title": "Registration",
                    "description": "Users can register with email.",
                    "priority": "HIGH",
                    "priority_basis": "EXPLICIT",
                    "source_references": [
                        {"document": "srs.pdf", "page": 2, "source": "srs.pdf page 2"}
                    ],
                }
            ],
        }
    )
    assert analysis.functional_requirements[0].title == "Registration"
    assert analysis.user_stories == []