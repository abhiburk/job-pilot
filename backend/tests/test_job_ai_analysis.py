
import pytest

from backend.app.services.job_ai_analysis import (
    JobAIAnalysisError,
    _parse_analysis,
)


def test_parse_valid_analysis():
    result = _parse_analysis(
        """
        {
          "fit_score": 86,
          "recommendation": "strong_fit",
          "summary": "Relevant backend experience.",
          "strengths": ["Laravel experience"],
          "missing_requirements": [],
          "evidence_gaps": ["Cloud deployment experience unclear"],
          "concerns": []
        }
        """
    )

    assert result["fit_score"] == 86
    assert result["recommendation"] == "strong_fit"
    assert result["strengths"] == ["Laravel experience"]


def test_reject_invalid_fit_score():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis(
            """
            {
              "fit_score": 150,
              "recommendation": "strong_fit",
              "summary": "Looks good",
              "strengths": [],
              "missing_requirements": [],
              "evidence_gaps": [],
              "concerns": []
            }
            """
        )


def test_reject_invalid_json():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis("This is not JSON")
