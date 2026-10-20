"""Link an existing, unowned candidate profile to a user account.

Candidates created before authentication existed have no owner and are not
reachable through the API. Register an account in the UI first, then run:

    uv run python -m backend.app.commands.claim_candidate \\
        --candidate-email you@example.com --user-email you@example.com

Use --list to see unowned candidates. Claiming is deliberately an operator
action: matching accounts to candidates by email automatically would let
anyone who registers with that address take over the profile.
"""

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models import Candidate, User


async def list_unowned() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Candidate.id, Candidate.full_name, Candidate.email)
            .where(Candidate.user_id.is_(None))
            .order_by(Candidate.created_at)
        )
        rows = result.all()

    if not rows:
        print("No unowned candidates.")
        return 0

    for candidate_id, full_name, email in rows:
        print(f"{candidate_id}  {full_name}  <{email}>")
    return 0


async def claim(candidate_email: str, user_email: str) -> int:
    async with AsyncSessionLocal() as db:
        candidate = await db.scalar(
            select(Candidate).where(
                func.lower(Candidate.email) == candidate_email.strip().lower()
            )
        )
        if candidate is None:
            print(f"No candidate with email {candidate_email}.", file=sys.stderr)
            return 1

        user = await db.scalar(
            select(User).where(User.email == user_email.strip().lower())
        )
        if user is None:
            print(
                f"No user account with email {user_email}. Register first.",
                file=sys.stderr,
            )
            return 1

        if candidate.user_id == user.id:
            print("Candidate is already linked to this account.")
            return 0

        if candidate.user_id is not None:
            print(
                "Candidate already belongs to another account; refusing.",
                file=sys.stderr,
            )
            return 1

        existing = await db.scalar(
            select(Candidate.id).where(Candidate.user_id == user.id)
        )
        if existing is not None:
            print(
                f"Account already owns candidate {existing}; an account can "
                "own one profile.",
                file=sys.stderr,
            )
            return 1

        candidate.user_id = user.id
        await db.commit()

    print(f"Linked candidate {candidate.id} to {user.email}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="List unowned candidates")
    parser.add_argument("--candidate-email")
    parser.add_argument("--user-email")
    args = parser.parse_args()

    if args.list:
        raise SystemExit(asyncio.run(list_unowned()))

    if not args.candidate_email or not args.user_email:
        parser.error("--candidate-email and --user-email are required")

    raise SystemExit(asyncio.run(claim(args.candidate_email, args.user_email)))


if __name__ == "__main__":
    main()
