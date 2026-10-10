"""normalize email case

Revision ID: 8c2e5d1a9b47
Revises: 1abf2d56776a
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c2e5d1a9b47'
down_revision: Union[str, Sequence[str], None] = '1abf2d56776a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # Rows whose normalized email collides with another row can't be
    # lowercased without violating the unique constraint. Leave them as-is
    # and report them so an admin can resolve them manually.
    duplicates = conn.execute(sa.text("""
        SELECT lower(trim(email)) AS normalized, array_agg(discord_id) AS discord_ids
        FROM users
        WHERE email IS NOT NULL
        GROUP BY lower(trim(email))
        HAVING count(*) > 1
    """)).fetchall()
    for row in duplicates:
        print(f"WARNING: email {row.normalized} is shared by Discord accounts {row.discord_ids}; left unnormalized.")

    conn.execute(sa.text("""
        UPDATE users u
        SET email = lower(trim(u.email))
        WHERE u.email IS NOT NULL
          AND u.email <> lower(trim(u.email))
          AND NOT EXISTS (
              SELECT 1 FROM users o
              WHERE o.id <> u.id
                AND lower(trim(o.email)) = lower(trim(u.email))
          )
    """))

    conn.execute(sa.text("""
        UPDATE otp_codes
        SET email = lower(trim(email))
        WHERE email <> lower(trim(email))
    """))


def downgrade() -> None:
    """Downgrade schema."""
    # Original casing is not recoverable; nothing to undo.
    pass
