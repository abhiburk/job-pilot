
from decimal import Decimal

from backend.app.services.job_matching import build_match_explanation


def test_strong_match_explains_matching_and_missing_skills():
    explanation = build_match_explanation(
        score=Decimal("85.00"),
        title_skills={"laravel", "php"},
        description_skills={"laravel", "php", "docker"},
        candidate_skills={"laravel", "php"},
        matched=["laravel", "php"],
        gaps=["docker"],
        preference_score=Decimal("100"),
        experience_score=Decimal("90"),
        salary_score=None,
    )

    assert explanation.startswith("Strong match: 85.00/100.")
    assert "Matched 2 of 2 recognized skills in the job title." in explanation
    assert "Matching skills: laravel, php." in explanation
    assert "Skills not found in your profile: docker." in explanation
    assert "matches at least one saved job preference" in explanation
    assert "Salary fit could not be assessed" in explanation


def test_partial_match_reports_missing_experience():
    explanation = build_match_explanation(
        score=Decimal("50.00"),
        title_skills={"laravel"},
        description_skills={"laravel", "docker"},
        candidate_skills={"laravel"},
        matched=["laravel"],
        gaps=["docker"],
        preference_score=None,
        experience_score=None,
        salary_score=Decimal("80"),
    )

    assert explanation.startswith("Partial match: 50.00/100.")
    assert "Experience fit could not be fully assessed." in explanation


def test_low_match_without_recognized_skills():
    explanation = build_match_explanation(
        score=Decimal("15.00"),
        title_skills=set(),
        description_skills=set(),
        candidate_skills=set(),
        matched=[],
        gaps=[],
        preference_score=None,
        experience_score=Decimal("20"),
        salary_score=None,
    )

    assert explanation.startswith("Low match: 15.00/100.")
    assert "No recognized technical skills were identified" in explanation
    assert "Salary fit could not be assessed" in explanation
