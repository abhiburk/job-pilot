
def calculate_match_confidence(
    job_title: str | None,
    job_description: str | None,
    job_location: str | None,
    job_experience_level: str | None,
    job_salary_min: int | float | None,
    job_salary_max: int | float | None,
    candidate_resume_text: str | None,
) -> float:
    """Measure data completeness, not the probability of a good match."""
    checks = [
        (bool(job_title and job_title.strip()), 15),
        (
            bool(job_description and len(job_description.strip()) >= 200),
            30,
        ),
        (bool(job_location and job_location.strip()), 10),
        (bool(job_experience_level and job_experience_level.strip()), 10),
        (
            job_salary_min is not None or job_salary_max is not None,
            10,
        ),
        (
            bool(
                candidate_resume_text
                and len(candidate_resume_text.strip()) >= 200
            ),
            25,
        ),
    ]

    return round(
        sum(weight for available, weight in checks if available),
        2,
    )
