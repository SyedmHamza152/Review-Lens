"""SQLAlchemy models package — import all models so mappers register."""
from app.models.analysis import AnalysisJob, ProductAnalysis  # noqa: F401
from app.models.benchmark import BenchmarkJob, DatasetBenchmark  # noqa: F401
from app.models.campaign import Campaign, CampaignPerformance  # noqa: F401
from app.models.google_connection import GoogleConnection  # noqa: F401
from app.models.ml import MLPrediction, ModelRegistryEntry  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.recommendation import BudgetRecommendation, OptimizationRun  # noqa: F401
from app.models.research import AudienceInsight, ResearchVideo  # noqa: F401
from app.models.report import GeneratedReport  # noqa: F401
from app.models.settings_kv import AppSetting  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "User",
    "GoogleConnection",
    "Product",
    "ProductAnalysis",
    "AnalysisJob",
    "Campaign",
    "CampaignPerformance",
    "ResearchVideo",
    "AudienceInsight",
    "BudgetRecommendation",
    "OptimizationRun",
    "MLPrediction",
    "ModelRegistryEntry",
    "DatasetBenchmark",
    "BenchmarkJob",
    "GeneratedReport",
    "AppSetting",
]
