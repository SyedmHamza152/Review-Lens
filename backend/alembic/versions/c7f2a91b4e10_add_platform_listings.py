"""add platform_listings (marketplace rating aggregates)

Revision ID: c7f2a91b4e10
Revises: afb0d1ea9230
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa

revision = "c7f2a91b4e10"
down_revision = "afb0d1ea9230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=36),
                  sa.ForeignKey("search_jobs.id"), nullable=False, index=True),
        sa.Column("platform", sa.String(length=40), nullable=False, index=True),
        sa.Column("external_id", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_text", sa.String(length=120), nullable=True),
        sa.Column("seller", sa.String(length=200), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("sold_count_text", sa.String(length=60), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=12), nullable=False, server_default="live"),
        sa.UniqueConstraint("job_id", "platform", "external_id", name="uq_listing_external"),
    )


def downgrade() -> None:
    op.drop_table("platform_listings")
