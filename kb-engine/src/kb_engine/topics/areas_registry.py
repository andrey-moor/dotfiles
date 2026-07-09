"""The seeded areas registry — the coarse tier of the one aboutness hierarchy.

Nine areas seeded from the taxonomy's categories (spec §6 Phase 5). Areas are
DECLARED, not discovered: the old agglomerative grouping (topics/areas.py)
retired with this module's arrival. ``CATEGORY_TO_AREA`` maps the legacy
two-level tag categories onto area slugs for the migration.
"""
from kb_engine.models import Area
from kb_engine.store import Store

SEEDED_AREAS: tuple[Area, ...] = (
    Area("ai", "AI", (), "LLMs, agents, RAG, prompting, MLOps"),
    Area("dev", "Dev", (), "Languages, developer tools, editors, Nix"),
    Area("infra", "Infra", (), "Kubernetes, GitOps, networking"),
    Area("arch", "Architecture", (), "Distributed systems, APIs, databases"),
    Area("gamedev", "GameDev", (), "Game development, pixel art, engines"),
    Area("business", "Business", (), "SaaS, marketing, startups, indie hacking"),
    Area("career", "Career", (), "Interviews, growth, leadership"),
    Area("home", "Home", (), "Improvement, organization, gear"),
    Area("personal", "Personal", (), "Fitness, travel, cooking, photography"),
)

CATEGORY_TO_AREA: dict[str, str] = {
    "AI": "ai",
    "Dev": "dev",
    "Infra": "infra",
    "Arch": "arch",
    "GameDev": "gamedev",
    "Business": "business",
    "Career": "career",
    "Home": "home",
    "Personal": "personal",
}


def seed_areas(store: Store) -> int:
    """Write the seeded registry (idempotent full replace). Returns row count."""
    store.save_areas(list(SEEDED_AREAS))
    return len(SEEDED_AREAS)
