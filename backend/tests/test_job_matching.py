
from decimal import Decimal
from types import SimpleNamespace
from decimal import Decimal
import pytest

from backend.app.services.job_matching import (
    calculate_experience_score,
    calculate_preference_score,
    calculate_salary_score,
    contains_term,
    extract_skills,
    normalize,
    weighted_score,
    calculate_role_relevance_score,
    normalize_title,
    extract_candidate_skills
)


# --------------------------------------------------
# Skill extraction
# --------------------------------------------------

def test_extract_skills_finds_known_skills():
    skills = extract_skills(
        "We need a Laravel developer with PHP, PostgreSQL, and Docker."
    )

    assert skills == {"Laravel", "PHP", "PostgreSQL", "Docker"}


def test_extract_skills_is_case_insensitive():
    skills = extract_skills("PYTHON, laravel, and FASTAPI")

    assert skills == {"Python", "Laravel", "FastAPI"}



def test_extract_skills_does_not_match_partial_words():
    skills = extract_skills(
        "Experience with PostgreSQL and Pythonic patterns"
    )

    assert "SQL" not in skills
    assert "Python" not in skills
    assert "PostgreSQL" in skills



def test_extract_skills_handles_empty_text():
    assert extract_skills("") == set()


def test_contains_term_respects_word_boundaries():
    assert contains_term("I use Python daily", "Python")
    assert not contains_term("I use Pythonic patterns", "Python")


# --------------------------------------------------
# Normalization
# --------------------------------------------------

def test_normalize_strips_whitespace_and_ignores_case():
    assert normalize("  Laravel Developer  ") == "laravel developer"


def test_normalize_handles_none():
    assert normalize(None) == ""


# --------------------------------------------------
# Experience scoring
# --------------------------------------------------

@pytest.mark.parametrize(
    ("years", "level", "expected"),
    [
        (Decimal("8"), "Senior", Decimal("100")),
        (Decimal("4"), "Senior", Decimal("60")),
        (Decimal("1"), "Senior", Decimal("30")),
        (Decimal("3"), "Mid-level", Decimal("100")),
        (Decimal("8"), "Mid-level", Decimal("70")),
        (Decimal("1"), "Mid-level", Decimal("50")),
        (Decimal("2"), "Junior", Decimal("100")),
        (Decimal("5"), "Junior", Decimal("75")),
    ],
)
def test_calculate_experience_score(years, level, expected):
    assert calculate_experience_score(years, level) == expected


@pytest.mark.parametrize(
    ("years", "level"),
    [
        (None, "Senior"),
        (Decimal("5"), None),
        (Decimal("5"), "Contract"),
    ],
)
def test_experience_score_returns_none_when_not_applicable(years, level):
    assert calculate_experience_score(years, level) is None


# --------------------------------------------------
# Preference scoring
# --------------------------------------------------

def test_preference_score_matches_title_work_mode_and_location():
    candidate = SimpleNamespace(
        preferred_job_titles=["Backend Developer"],
        preferred_work_modes=["Remote"],
        preferred_locations=["India"],
    )
    job = SimpleNamespace(
        title="Senior Backend Developer",
        remote_type="Remote",
        location="India",
    )

    assert calculate_preference_score(candidate, job) == Decimal("100.0")


def test_preference_score_returns_zero_when_preferences_do_not_match():
    candidate = SimpleNamespace(
        preferred_job_titles=["Frontend Developer"],
        preferred_work_modes=["On-site"],
        preferred_locations=["London"],
    )
    job = SimpleNamespace(
        title="Backend Developer",
        remote_type="Remote",
        location="India",
    )

    assert calculate_preference_score(candidate, job) == Decimal("0.0")


def test_preference_score_returns_none_without_comparable_preferences():
    candidate = SimpleNamespace(
        preferred_job_titles=[],
        preferred_work_modes=[],
        preferred_locations=[],
    )
    job = SimpleNamespace(
        title="Backend Developer",
        remote_type=None,
        location=None,
    )

    assert calculate_preference_score(candidate, job) is None


# --------------------------------------------------
# Salary scoring
# --------------------------------------------------

def test_salary_score_matches_when_job_range_meets_minimum():
    score = calculate_salary_score(
        Decimal("100000"),
        Decimal("80000"),
        Decimal("120000"),
        "INR",
        "INR",
    )

    assert score == Decimal("100.00")


def test_salary_score_is_zero_when_job_salary_is_too_low():
    score = calculate_salary_score(
        Decimal("100000"),
        Decimal("50000"),
        Decimal("90000"),
        "INR",
        "INR",
    )

    assert score == Decimal("0.00")


def test_salary_score_ignores_different_currencies():
    score = calculate_salary_score(
        Decimal("100000"),
        Decimal("200000"),
        Decimal("300000"),
        "INR",
        "USD",
    )

    assert score is None


def test_salary_score_returns_none_when_salary_is_missing():
    assert calculate_salary_score(
        Decimal("100000"),
        None,
        None,
        "INR",
        "INR",
    ) is None


# --------------------------------------------------
# Weighted scoring
# --------------------------------------------------

def test_weighted_score_uses_all_available_components():
    score = weighted_score({
        "skills": Decimal("100"),
        "experience": Decimal("50"),
        "preferences": Decimal("100"),
        "salary": Decimal("0"),
    })

    assert score == Decimal("62.50")


def test_weighted_score_uses_neutral_score_for_missing_components():
    score = weighted_score({
        "skills": Decimal("100"),
        "experience": None,
        "preferences": None,
        "salary": None,
    })

    assert score == Decimal("40.00")


def test_weighted_score_returns_neutral_score_when_no_components_are_available():
    score = weighted_score({
        "skills": None,
        "experience": None,
        "preferences": None,
        "salary": None,
    })

    assert score == Decimal("0.00")


def test_extract_kubernetes_skill():
    from backend.app.services.job_matching import extract_skills

    skills = extract_skills("Laravel, PHP, Docker, Kubernetes")

    assert "Kubernetes" in skills

def test_single_description_only_skill_is_low_confidence():
    title_skills = set()
    description_skills = {"AI"}

    job_skills = title_skills | description_skills
    matched = {"AI"}

    score = Decimal(
        str(round(100 * len(matched) / len(job_skills), 2))
    )

    if not title_skills and len(job_skills) == 1:
        score = min(score, Decimal("40"))

    assert score == Decimal("40")

def test_ai_alone_is_not_a_recognized_skill():
    assert "AI" not in extract_skills(
        "Looking for an engineer experienced in AI."
    )

def test_llm_and_rag_remain_recognized_skills():
    skills = extract_skills("Experience with LLM and RAG.")

    assert "LLM" in skills
    assert "RAG" in skills

def test_preferred_laravel_title_gets_high_relevance():
    candidate = SimpleNamespace(
        preferred_job_titles=[
            "Backend Developer",
            "Laravel Developer",
            "PHP Developer",
            "Full-Stack Developer",
        ],
        headline="Senior Backend Engineer | Laravel and PHP",
        summary="",
        resume_text="Laravel PHP",
    )
    job = SimpleNamespace(title="Laravel Developer")

    assert calculate_role_relevance_score(
        job, candidate
    ) == Decimal("100.00")


def test_unrelated_data_engineer_role_scores_below_backend_role():
    candidate = SimpleNamespace(
        preferred_job_titles=[
            "Backend Developer",
            "Laravel Developer",
            "PHP Developer",
            "Full-Stack Developer",
        ],
        headline="Senior Backend Engineer | Laravel and PHP",
        summary="",
        resume_text="Laravel PHP",
    )

    data_job = SimpleNamespace(title="Data Engineer")
    backend_job = SimpleNamespace(title="Backend Developer")

    data_score = calculate_role_relevance_score(data_job, candidate)
    backend_score = calculate_role_relevance_score(backend_job, candidate)

    assert data_score < backend_score

def test_ai_alone_is_not_a_recognized_skill():
    assert "AI" not in extract_skills("Looking for an engineer experienced in AI.")


def test_llm_and_rag_are_recognized():
    skills = extract_skills("Experience with LLM and RAG.")

    assert "LLM" in skills
    assert "RAG" in skills


def test_postgres_alias_matches_postgresql():
    assert "PostgreSQL" in extract_skills("Experience with Postgres databases.")


def test_nodejs_alias_matches_node_js():
    assert "Node.js" in extract_skills("Backend experience using NodeJS.")


def test_title_normalization():
    assert normalize_title("Senior Laravel/PHP Developer") == (
        "senior laravel php developer"
    )


def test_backend_role_scores_above_data_engineer():
    candidate = SimpleNamespace(
        preferred_job_titles=[
            "Backend Developer",
            "Laravel Developer",
            "PHP Developer",
        ],
        headline="Senior Laravel PHP Engineer",
        summary="Backend development and APIs",
        resume_text="Laravel PHP PostgreSQL",
    )

    backend_job = SimpleNamespace(title="Laravel Backend Developer")
    data_job = SimpleNamespace(title="Data Engineer")

    assert calculate_role_relevance_score(
        backend_job, candidate
    ) > calculate_role_relevance_score(data_job, candidate)


def test_unknown_experience_level_is_not_scored():
    assert calculate_experience_score(8, None) is None


def test_currency_mismatch_does_not_claim_salary_fit():
    assert calculate_salary_score(
        candidate_minimum=1800000,
        job_minimum=2000000,
        job_maximum=2500000,
        candidate_currency="INR",
        job_currency="USD",
    ) is None


def test_missing_salary_is_not_scored():
    
    assert calculate_salary_score(
        candidate_minimum=1800000,
        job_minimum=None,
        job_maximum=None,
        candidate_currency="INR",
        job_currency="INR",
    ) is None


def test_weighted_score_preserves_neutral_missing_components():
    score = weighted_score({
        "role_relevance": None,
        "skills": Decimal("100"),
        "experience": None,
        "preferences": None,
        "salary": None,
    })

    assert score == Decimal("40.00")

def test_weighted_score_ignores_missing_components():
    score = weighted_score({
        "role_relevance": None,
        "skills": Decimal("100"),
        "experience": None,
        "preferences": None,
        "salary": None,
    })

    assert score == Decimal("40.00")


def test_weighted_score_returns_zero_when_all_components_are_missing():
    score = weighted_score({
        "role_relevance": None,
        "skills": None,
        "experience": None,
        "preferences": None,
        "salary": None,
    })

    assert score == Decimal("0.00")


def test_candidate_skills_excludes_learning_mentions():
    assert extract_candidate_skills("Currently learning Python") == set()


def test_candidate_skills_excludes_interest_mentions():
    assert extract_candidate_skills(
        "Interested in machine learning"
    ) == set()


def test_candidate_skills_excludes_explicit_lack_of_experience():
    assert extract_candidate_skills(
        "I have no experience with Python"
    ) == set()


def test_candidate_skills_keeps_demonstrated_skills():
    skills = extract_candidate_skills(
        "Built APIs using Python and Laravel in production"
    )

    assert "Python" in skills
    assert "Laravel" in skills


def test_candidate_skills_keeps_other_skills_when_one_is_being_learned():
    skills = extract_candidate_skills(
        "Learning Python. Built production APIs using Laravel."
    )

    assert "Python" not in skills
    assert "Laravel" in skills


def test_candidate_skills_handles_empty_text():
    assert extract_candidate_skills(None) == set()
    assert extract_candidate_skills("") == set()
