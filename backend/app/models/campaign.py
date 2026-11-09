from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import utcnow


class Campaign(Base):
    """A YouTube video campaign (live-synced from Google Ads or demo-seeded)."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("google_connections.id"), nullable=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), index=True)  # Google Ads campaign resource name/id
    name: Mapped[str] = mapped_column(String(300))
    channel_type: Mapped[str] = mapped_column(String(40), default="VIDEO")
    channel_subtype: Mapped[str] = mapped_column(String(60), default="")
    # Canonical AdPilot format key: in_stream | shorts | in_feed
    format_key: Mapped[str] = mapped_column(String(20), default="in_stream")
    status: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    objective: Mapped[str] = mapped_column(String(60), default="")
    data_source_label: Mapped[str] = mapped_column(String(40), default="SYNTHETIC DEMO DATA")
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    performances: Mapped[list["CampaignPerformance"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignPerformance(Base):
    """Daily campaign performance row (cost stored in micros of the currency)."""

    __tablename__ = "campaign_performance"
    __table_args__ = (UniqueConstraint("campaign_id", "date", "age_group", "gender", name="uq_perf_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    cost_micros: Mapped[int] = mapped_column(Integer, default=0)  # 1e6 = 1 currency unit
    conversions: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_value: Mapped[float] = mapped_column(Float, default=0.0)
    video_views: Mapped[int] = mapped_column(Integer, default=0)
    video_impressions: Mapped[int] = mapped_column(Integer, default=0)  # eligible views for view-rate

    age_group: Mapped[str] = mapped_column(String(20), default="unknown")
    gender: Mapped[str] = mapped_column(String(20), default="unknown")
    device: Mapped[str] = mapped_column(String(20), default="unknown")
    city: Mapped[str] = mapped_column(String(60), default="")

    data_source_label: Mapped[str] = mapped_column(String(40), default="SYNTHETIC DEMO DATA")

    campaign: Mapped["Campaign"] = relationship(back_populates="performances")
