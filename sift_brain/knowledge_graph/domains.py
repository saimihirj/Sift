"""Domain registry for the Sift Brain knowledge graph.

Each domain defines:
  - key:            unique identifier
  - label:          display name
  - geography:      "india", "global", "sea", "africa" ...
  - seed_urls:      curated public data sources to scrape for updates
  - taxonomy_keys:  existing KB taxonomy keys to merge with
  - update_days:    how often to refresh this domain (days)
  - enabled:        whether this domain is active in the updater

Add or disable domains here without touching any other file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class DomainConfig:
    key: str
    label: str
    geography: str
    seed_urls: Sequence[str]
    taxonomy_keys: Sequence[str]
    update_days: int = 7
    enabled: bool = True
    metric_benchmarks: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Domain registry
# ---------------------------------------------------------------------------

DOMAINS: dict[str, DomainConfig] = {
    # ---- SaaS ---------------------------------------------------------------
    "saas": DomainConfig(
        key="saas",
        label="SaaS",
        geography="global",
        seed_urls=[
            "https://openvc.app/blog/saas-metrics",
            "https://www.saasmetrics.co/",
            "https://www.bvp.com/atlas",
            "https://www.nsvp.com/insights",
            "https://saastr.com/category/metrics/",
            "https://baremetrics.com/blog",
        ],
        taxonomy_keys=["SaaS", "B2B_SaaS", "Enterprise_SaaS"],
        update_days=7,
        metric_benchmarks={
            "good_nrr": "120%+ enterprise, 100%+ SMB",
            "good_ltv_cac": "3:1 or higher",
            "good_gross_margin": "70-85%",
            "good_churn_monthly": "<2% SMB, <1% enterprise",
        },
    ),

    # ---- D2C ----------------------------------------------------------------
    "d2c": DomainConfig(
        key="d2c",
        label="D2C / Consumer",
        geography="global",
        seed_urls=[
            "https://www.dcinside.com/",
            "https://www.marketingweek.com/category/ecommerce/",
            "https://econsultancy.com/blog/category/e-commerce/",
            "https://www.klaviyo.com/blog",
            "https://a16z.com/tag/consumer/",
        ],
        taxonomy_keys=["D2C", "Consumer", "Ecommerce"],
        update_days=7,
        metric_benchmarks={
            "good_gross_margin": "60-70% premium, 40-50% mass-market",
            "good_repeat_rate": "30%+ in 6 months for consumables",
            "good_cac": "<1/3 first-order AOV",
        },
    ),

    # ---- Fintech -------------------------------------------------------------
    "fintech": DomainConfig(
        key="fintech",
        label="Fintech",
        geography="global",
        seed_urls=[
            "https://www.fintechfutures.com/",
            "https://www.pymnts.com/",
            "https://techcrunch.com/category/fintech/",
            "https://a16z.com/tag/fintech/",
            "https://www.cbinsights.com/research/fintech/",
        ],
        taxonomy_keys=["Fintech", "Payments", "Lending", "WealthTech", "InsurTech"],
        update_days=7,
        metric_benchmarks={
            "good_take_rate": "0.5-2% for payments",
            "good_npl_rate": "<3% for consumer lending",
        },
    ),

    # ---- India VC -----------------------------------------------------------
    "india_vc": DomainConfig(
        key="india_vc",
        label="India VC Ecosystem",
        geography="india",
        seed_urls=[
            "https://entrackr.com/",
            "https://inc42.com/features/",
            "https://the-ken.com/",
            "https://techcrunch.com/tag/india/",
            "https://www.ivca.in/",
            "https://www.bain.com/insights/india-private-equity-report-2025/",
        ],
        taxonomy_keys=["India_VC_Ecosystem_Web", "India_Fintech_Infrastructure_Web", "India_Regulation_Web"],
        update_days=7,
        metric_benchmarks={
            "seed_round_typical": "$1-3M pre-seed, $3-8M seed",
            "series_a_typical": "$8-20M",
        },
    ),

    # ---- PE / Growth --------------------------------------------------------
    "pe_growth": DomainConfig(
        key="pe_growth",
        label="PE / Growth Equity",
        geography="global",
        seed_urls=[
            "https://www.preqin.com/insights",
            "https://www.pitchbook.com/news/articles",
            "https://www.bain.com/insights/private-equity/",
            "https://www.kearney.com/service/private-equity",
        ],
        taxonomy_keys=["PE_Fund_Metrics_Web", "DCF_Valuation_Web"],
        update_days=14,
    ),

    # ---- Macro / Economy ----------------------------------------------------
    "macro": DomainConfig(
        key="macro",
        label="Macro & Economy",
        geography="global",
        seed_urls=[
            "https://fred.stlouisfed.org/",
            "https://www.imf.org/en/Publications/WEO",
            "https://www.worldbank.org/en/publication/global-economic-prospects",
            "https://www.bis.org/statistics/",
        ],
        taxonomy_keys=["Macro_Indicators_Web", "SWF_Web"],
        update_days=14,
    ),

    # ---- Regulation (India) -------------------------------------------------
    "regulation_india": DomainConfig(
        key="regulation_india",
        label="Regulation (India)",
        geography="india",
        seed_urls=[
            "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
            "https://www.sebi.gov.in/press-releases.html",
            "https://mca.gov.in/content/mca/global/en/home.html",
            "https://dpiit.gov.in/",
        ],
        taxonomy_keys=["India_Regulation_Web", "ESOP_Governance_Web"],
        update_days=14,
    ),

    # ---- Market Sizing ------------------------------------------------------
    "market_sizing": DomainConfig(
        key="market_sizing",
        label="Market Sizing",
        geography="global",
        seed_urls=[
            "https://www.grandviewresearch.com/industry-analysis/",
            "https://www.mordorintelligence.com/",
            "https://www.alliedmarketresearch.com/",
            "https://www.statista.com/markets/",
        ],
        taxonomy_keys=["Market_Sizing_Web"],
        update_days=14,
    ),

    # ---- PMF / GTM ----------------------------------------------------------
    "pmf_gtm": DomainConfig(
        key="pmf_gtm",
        label="Product-Market Fit & GTM",
        geography="global",
        seed_urls=[
            "https://a16z.com/tag/go-to-market/",
            "https://www.lennysnewsletter.com/",
            "https://caseyaccidental.com/",
            "https://www.reforge.com/blog",
        ],
        taxonomy_keys=["Product_Market_Fit_Web", "PLG_GTM_Web", "Unit_Economics_Web"],
        update_days=7,
    ),

    # ---- VC / Deal Terms ----------------------------------------------------
    "vc_terms": DomainConfig(
        key="vc_terms",
        label="VC Terms & Deal Structure",
        geography="global",
        seed_urls=[
            "https://www.ycombinator.com/library/",
            "https://www.nvca.org/research/",
            "https://venturehacks.com/",
            "https://www.cooleygo.com/glossary/",
            "https://goingvc.com/",
        ],
        taxonomy_keys=["VC_Term_Sheet_Web", "Accelerators_Web", "Unicorn_Decacorn_Web"],
        update_days=14,
    ),

    # ---- ClimateTech (new) --------------------------------------------------
    "climatetech": DomainConfig(
        key="climatetech",
        label="ClimateTech / DeepTech",
        geography="global",
        seed_urls=[
            "https://www.ctvc.co/",
            "https://climatetech.vc/",
            "https://heatmap.news/",
            "https://www.bvp.com/atlas/emerging-themes/climate",
            "https://techcrunch.com/category/climate/",
        ],
        taxonomy_keys=["ClimateTech", "CleanEnergy", "DeepTech"],
        update_days=14,
        enabled=True,
    ),

    # ---- Healthcare / HealthTech (new) --------------------------------------
    "healthtech": DomainConfig(
        key="healthtech",
        label="HealthTech / Digital Health",
        geography="global",
        seed_urls=[
            "https://rock.health/reports/",
            "https://www.healthcareitnews.com/",
            "https://techcrunch.com/category/health/",
            "https://a16z.com/tag/bio-health/",
        ],
        taxonomy_keys=["HealthTech", "DigitalHealth", "MedTech"],
        update_days=14,
        enabled=True,
    ),
}


def get_domain(key: str) -> DomainConfig | None:
    """Return a domain config by key, or None if not found."""
    return DOMAINS.get(key)


def enabled_domains() -> list[DomainConfig]:
    """Return all enabled domain configs."""
    return [d for d in DOMAINS.values() if d.enabled]


def domain_keys() -> list[str]:
    """Return all domain keys (enabled and disabled)."""
    return list(DOMAINS.keys())
