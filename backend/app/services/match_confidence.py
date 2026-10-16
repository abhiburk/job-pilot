
def calculate_match_confidence(
    job_title: str | None,
    job_description: str | None,
    job_location: str | None,
    job_experience_level: str | None,
    job_salary_min: int | float | None,
    job_salary_max: int | float | None,
    candidate_resume_text: str | None,
) -> float:
    """
    Estimate how complete the data is for evaluating a job match.
    This is data completeness, not a probability of being a good match.
    """
    checks = [
        bool(job_title and job_title.strip()),
        bool(job_description and len(job_description.strip()) >= 200),
        bool(job_location and job_location.strip()),
        bool(job_experience_level and job_experience_level.strip()),
        job_salary_min is not None or job_salary_max is not None,
        bool(
            candidate_resume_text
            and len(candidate_resume_text.strip()) >= 200
        ),
    ]

    return round(sum(checks) / len(checks) * 100, 2)
