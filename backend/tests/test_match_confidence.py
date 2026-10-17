
from backend.app.services.match_confidence import calculate_match_confidence


def test_complete_job_and_resume_have_high_confidence():
    confidence = calculate_match_confidence(
        job_title="Senior Backend Engineer",
        job_description="A detailed job description " * 20,
        job_location="Remote",
        job_experience_level="Senior",
        job_salary_min=100000,
        job_salary_max=150000,
        candidate_resume_text="Experienced backend engineer " * 20,
    )

    assert confidence == 100.0


def test_missing_job_information_reduces_confidence():
    confidence = calculate_match_confidence(
        job_title="Backend Engineer",
        job_description="Short description",
        job_location=None,
        job_experience_level=None,
        job_salary_min=None,
        job_salary_max=None,
        candidate_resume_text=None,
    )

    assert confidence == 15


def test_salary_range_is_not_required_for_high_confidence():
    confidence = calculate_match_confidence(
        job_title="Backend Engineer",
        job_description="Detailed description " * 20,
        job_location="Remote",
        job_experience_level="Senior",
        job_salary_min=None,
        job_salary_max=None,
        candidate_resume_text="Backend engineer " * 20,
    )

    assert confidence == 90
