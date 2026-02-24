"""
Supply Chain Cross-Domain Mapping for TrendVest.

Maps relationships between raw materials, manufacturing, and end products
across different markets and geographies.

Example: Copper (mined in Chile/Asia) → Semiconductors (fabricated in Taiwan/Israel)
         → Tech products (sold in US/Europe)

This enables cross-market trend detection: a copper price spike in Asia
signals potential semiconductor cost increases affecting Israeli tech companies.
"""
import time
from typing import Optional

# Cache
_chain_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes (static data)

# ──────────────────────────────────────────────────
# SUPPLY CHAIN KNOWLEDGE GRAPH
# ──────────────────────────────────────────────────

SUPPLY_CHAINS = {
    # ── SEMICONDUCTORS ──
    "semiconductors": {
        "name": "Semiconductor Supply Chain",
        "name_he": "שרשרת אספקה — מוליכים למחצה",
        "stages": [
            {
                "stage": "raw_materials",
                "name": "Raw Materials",
                "name_he": "חומרי גלם",
                "commodities": ["copper", "silicon", "gold", "silver", "palladium", "tin", "aluminum", "rare_earths"],
                "regions": ["asia", "africa", "south_america"],
                "countries": ["Chile", "China", "Congo", "Australia"],
                "companies": ["FCX", "BHP", "RIO", "VALE"],
            },
            {
                "stage": "wafer_production",
                "name": "Wafer Production",
                "name_he": "ייצור פרוסות סיליקון",
                "regions": ["asia"],
                "countries": ["Japan", "Germany"],
                "companies": ["SUMCO", "SHIN-ETSU"],
            },
            {
                "stage": "chip_design",
                "name": "Chip Design",
                "name_he": "עיצוב שבבים",
                "regions": ["us", "israel", "europe"],
                "countries": ["US", "Israel", "UK", "Netherlands"],
                "companies": ["NVDA", "AMD", "INTC", "QCOM", "AVGO", "MRVL"],
                "israeli_companies": ["MCHP", "CEVA", "CAMX"],
            },
            {
                "stage": "fabrication",
                "name": "Chip Fabrication (Foundry)",
                "name_he": "ייצור שבבים",
                "regions": ["asia", "us"],
                "countries": ["Taiwan", "South Korea", "US", "Israel"],
                "companies": ["TSM", "SAMSUNG", "INTC", "GFS"],
                "notes": "Intel has fab in Kiryat Gat, Israel",
            },
            {
                "stage": "equipment",
                "name": "Fabrication Equipment",
                "name_he": "ציוד ייצור",
                "regions": ["europe", "us", "asia"],
                "countries": ["Netherlands", "US", "Japan"],
                "companies": ["ASML", "AMAT", "LRCX", "KLAC", "TER"],
            },
            {
                "stage": "assembly_test",
                "name": "Assembly & Testing",
                "name_he": "הרכבה ובדיקות",
                "regions": ["asia"],
                "countries": ["Malaysia", "Philippines", "Vietnam", "China"],
                "companies": ["ASX"],
            },
            {
                "stage": "end_products",
                "name": "End Products",
                "name_he": "מוצרים סופיים",
                "regions": ["us", "asia", "europe"],
                "countries": ["US", "China", "South Korea", "Japan"],
                "companies": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "DELL", "HPQ"],
                "sectors": ["smartphones", "data_centers", "automotive", "defense", "iot"],
            },
        ],
        "risk_factors": [
            {"factor": "Taiwan Strait tensions", "impact": "high", "affects": ["fabrication"]},
            {"factor": "Copper price spike", "impact": "medium", "affects": ["raw_materials", "end_products"]},
            {"factor": "ASML export restrictions", "impact": "high", "affects": ["equipment", "fabrication"]},
            {"factor": "Water shortage in Taiwan", "impact": "medium", "affects": ["fabrication"]},
        ],
    },

    # ── ELECTRIC VEHICLES ──
    "ev_batteries": {
        "name": "EV Battery Supply Chain",
        "name_he": "שרשרת אספקה — סוללות לרכב חשמלי",
        "stages": [
            {
                "stage": "mining",
                "name": "Mining & Extraction",
                "name_he": "כרייה",
                "commodities": ["lithium", "cobalt", "nickel", "manganese", "graphite", "copper", "aluminum"],
                "regions": ["south_america", "africa", "asia", "australia"],
                "countries": ["Chile", "Argentina", "Congo", "Australia", "Indonesia", "China"],
                "companies": ["ALB", "SQM", "LAC", "PLL", "VALE"],
            },
            {
                "stage": "processing",
                "name": "Chemical Processing",
                "name_he": "עיבוד כימי",
                "regions": ["asia"],
                "countries": ["China", "South Korea", "Japan"],
                "companies": ["CATL (China)", "LG Chem"],
                "notes": "China processes ~60% of global lithium",
            },
            {
                "stage": "cell_manufacturing",
                "name": "Battery Cell Manufacturing",
                "name_he": "ייצור תאי סוללה",
                "regions": ["asia", "us", "europe"],
                "countries": ["China", "South Korea", "Japan", "US", "Germany"],
                "companies": ["CATL", "LG", "PANASONIC", "BYD", "QS", "MVST"],
            },
            {
                "stage": "pack_assembly",
                "name": "Battery Pack Assembly",
                "name_he": "הרכבת חבילות סוללה",
                "regions": ["us", "europe", "asia"],
                "companies": ["TSLA", "RIVN", "GM", "F", "VWAGY", "BMW"],
            },
            {
                "stage": "ev_manufacturing",
                "name": "EV Manufacturing",
                "name_he": "ייצור רכב חשמלי",
                "regions": ["us", "europe", "asia"],
                "countries": ["US", "China", "Germany", "Sweden"],
                "companies": ["TSLA", "BYD", "RIVN", "LCID", "NIO", "XPEV", "LI", "VWAGY", "BMW", "STLA"],
                "israeli_connection": "StoreDot (Israeli startup) — ultra-fast charging batteries",
            },
            {
                "stage": "recycling",
                "name": "Battery Recycling",
                "name_he": "מחזור סוללות",
                "regions": ["us", "europe"],
                "companies": ["LICY"],
            },
        ],
        "risk_factors": [
            {"factor": "Lithium price volatility", "impact": "high", "affects": ["mining", "ev_manufacturing"]},
            {"factor": "Congo cobalt mining ethics", "impact": "medium", "affects": ["mining"]},
            {"factor": "China processing dominance", "impact": "high", "affects": ["processing", "cell_manufacturing"]},
        ],
    },

    # ── ENERGY ──
    "energy": {
        "name": "Energy Supply Chain",
        "name_he": "שרשרת אספקה — אנרגיה",
        "stages": [
            {
                "stage": "extraction",
                "name": "Oil & Gas Extraction",
                "name_he": "הפקת נפט וגז",
                "commodities": ["crude_oil", "natural_gas", "brent_oil"],
                "regions": ["middle_east", "us", "europe", "asia"],
                "countries": ["Saudi Arabia", "US", "Russia", "Israel", "UAE", "Norway"],
                "companies": ["XOM", "CVX", "COP", "SLB", "OXY"],
                "israeli_connection": "Leviathan & Tamar gas fields (Delek, NewMed/Ithaca)",
            },
            {
                "stage": "refining",
                "name": "Refining & Processing",
                "name_he": "זיקוק",
                "regions": ["us", "europe", "asia"],
                "companies": ["VLO", "PSX", "MPC"],
            },
            {
                "stage": "renewables",
                "name": "Renewable Energy",
                "name_he": "אנרגיה מתחדשת",
                "commodities": ["silver", "copper", "lithium"],
                "regions": ["us", "europe", "asia", "israel"],
                "companies": ["ENPH", "SEDG", "FSLR", "RUN", "NEE", "BEP"],
                "israeli_companies": ["SEDG"],
                "notes": "SolarEdge (Israeli) — global solar inverter leader",
            },
            {
                "stage": "nuclear",
                "name": "Nuclear Energy",
                "name_he": "אנרגיה גרעינית",
                "commodities": ["uranium"],
                "regions": ["us", "europe", "asia"],
                "companies": ["CCJ", "LEU", "SMR", "OKLO"],
            },
            {
                "stage": "distribution",
                "name": "Distribution & Utilities",
                "name_he": "הפצה ושירותים",
                "regions": ["us", "europe", "israel"],
                "companies": ["NEE", "DUK", "SO", "D"],
            },
        ],
        "risk_factors": [
            {"factor": "OPEC production cuts", "impact": "high", "affects": ["extraction"]},
            {"factor": "Middle East conflict", "impact": "high", "affects": ["extraction", "distribution"]},
            {"factor": "Israel gas export disruption", "impact": "medium", "affects": ["extraction"]},
            {"factor": "Silver shortage for solar", "impact": "medium", "affects": ["renewables"]},
        ],
    },

    # ── FOOD & AGRICULTURE ──
    "food": {
        "name": "Food & Agriculture Supply Chain",
        "name_he": "שרשרת אספקה — מזון וחקלאות",
        "stages": [
            {
                "stage": "inputs",
                "name": "Farm Inputs (Fertilizers, Seeds)",
                "name_he": "תשומות חקלאיות",
                "commodities": ["natural_gas", "potash"],
                "regions": ["us", "israel", "europe"],
                "companies": ["NTR", "MOS", "CF", "FMC"],
                "israeli_companies": ["ICL"],
                "notes": "ICL (Israel Chemicals) — global potash producer",
            },
            {
                "stage": "production",
                "name": "Crop Production",
                "name_he": "ייצור חקלאי",
                "commodities": ["wheat", "corn", "soybeans", "coffee", "cocoa", "sugar", "cotton", "orange_juice"],
                "regions": ["us", "south_america", "asia", "europe", "africa"],
                "countries": ["US", "Brazil", "Argentina", "Ukraine", "India", "Ivory Coast", "Ghana", "Vietnam", "Colombia"],
            },
            {
                "stage": "processing",
                "name": "Food Processing",
                "name_he": "עיבוד מזון",
                "commodities": ["cocoa", "sugar", "coffee"],
                "regions": ["us", "europe", "asia"],
                "companies": ["ADM", "BG", "CAG", "GIS", "SJM", "MDLZ", "HSY", "NSRGY", "KHC"],
                "notes": "Mondelez, Hershey, Nestlé — major cocoa/chocolate processors",
            },
            {
                "stage": "beverages",
                "name": "Beverages & Consumer Brands",
                "name_he": "משקאות ומותגי צריכה",
                "commodities": ["coffee", "sugar", "orange_juice", "cocoa"],
                "regions": ["us", "europe"],
                "companies": ["SBUX", "KO", "PEP", "KDP", "MNST"],
            },
            {
                "stage": "textiles",
                "name": "Textiles & Apparel",
                "name_he": "טקסטיל ואופנה",
                "commodities": ["cotton"],
                "regions": ["asia", "europe", "us"],
                "countries": ["China", "Bangladesh", "Vietnam", "India", "Turkey"],
                "companies": ["NKE", "LULU", "VFC", "PVH", "HBI"],
            },
            {
                "stage": "livestock",
                "name": "Livestock & Meat",
                "name_he": "בעלי חיים ובשר",
                "commodities": ["corn", "soybeans", "live_cattle"],
                "regions": ["us", "south_america", "europe"],
                "companies": ["TSN", "HRL", "PPC"],
            },
            {
                "stage": "distribution",
                "name": "Retail & Distribution",
                "name_he": "קמעונאות",
                "regions": ["us", "europe", "israel"],
                "companies": ["WMT", "COST", "KR", "TGT"],
            },
        ],
        "risk_factors": [
            {"factor": "Ukraine-Russia war (wheat exports)", "impact": "high", "affects": ["production"]},
            {"factor": "Natural gas → fertilizer costs", "impact": "high", "affects": ["inputs"]},
            {"factor": "Climate change / droughts", "impact": "high", "affects": ["production"]},
            {"factor": "Red Sea shipping disruption", "impact": "medium", "affects": ["distribution"]},
            {"factor": "Cocoa crop disease (West Africa)", "impact": "high", "affects": ["production", "processing"]},
            {"factor": "Coffee rust / frost (Brazil)", "impact": "medium", "affects": ["production", "beverages"]},
            {"factor": "Cotton tariffs / trade war", "impact": "medium", "affects": ["textiles"]},
        ],
    },

    # ── CYBERSECURITY ──
    "cybersecurity": {
        "name": "Cybersecurity Ecosystem",
        "name_he": "שרשרת אספקה — סייבר",
        "stages": [
            {
                "stage": "infrastructure",
                "name": "Cloud & Network Infrastructure",
                "name_he": "תשתיות ענן ורשת",
                "regions": ["us", "asia"],
                "companies": ["AMZN", "MSFT", "GOOGL", "CSCO", "ANET"],
            },
            {
                "stage": "security_platforms",
                "name": "Security Platforms",
                "name_he": "פלטפורמות אבטחה",
                "regions": ["us", "israel"],
                "companies": ["PANW", "CRWD", "FTNT", "ZS"],
                "israeli_companies": ["CHKP", "CYBR"],
                "notes": "Israel is #2 globally in cybersecurity exports after US",
            },
            {
                "stage": "identity_access",
                "name": "Identity & Access Management",
                "name_he": "ניהול זהויות",
                "regions": ["us", "israel"],
                "companies": ["OKTA"],
                "israeli_companies": ["CYBR"],
                "notes": "CyberArk (Israeli) — privileged access management leader",
            },
            {
                "stage": "endpoint_protection",
                "name": "Endpoint Protection",
                "name_he": "הגנת קצה",
                "regions": ["us", "israel"],
                "companies": ["CRWD", "S"],
                "israeli_companies": ["CHKP"],
            },
            {
                "stage": "defense_gov",
                "name": "Defense & Government",
                "name_he": "ביטחון וממשלה",
                "regions": ["us", "israel", "europe"],
                "companies": ["LMT", "RTX", "BA", "NOC", "PLTR"],
                "israeli_companies": ["ESLT"],
                "notes": "Elbit Systems provides defense cyber solutions",
            },
        ],
        "risk_factors": [
            {"factor": "Major data breach", "impact": "high", "affects": ["security_platforms"]},
            {"factor": "AI-powered cyberattacks", "impact": "high", "affects": ["endpoint_protection"]},
            {"factor": "Government regulation (NIS2, SEC)", "impact": "medium", "affects": ["security_platforms", "defense_gov"]},
        ],
    },

    # ── AI & CLOUD ──
    "ai_cloud": {
        "name": "AI & Cloud Computing Supply Chain",
        "name_he": "שרשרת אספקה — AI וענן",
        "stages": [
            {
                "stage": "compute_hardware",
                "name": "AI Compute Hardware (GPUs/TPUs)",
                "name_he": "חומרת חישוב AI",
                "commodities": ["copper", "gold", "silver", "rare_earths"],
                "regions": ["us", "asia"],
                "companies": ["NVDA", "AMD", "INTC", "GOOGL"],
                "notes": "NVIDIA controls ~80% of AI GPU market",
            },
            {
                "stage": "networking",
                "name": "AI Networking & Interconnects",
                "name_he": "רשתות AI",
                "regions": ["us", "israel"],
                "companies": ["ANET", "CSCO"],
                "israeli_companies": ["MLNX (acquired by NVIDIA)"],
                "notes": "Mellanox (Israeli, now NVIDIA) — AI networking pioneer",
            },
            {
                "stage": "data_centers",
                "name": "Data Centers",
                "name_he": "מרכזי נתונים",
                "commodities": ["copper", "natural_gas"],
                "regions": ["us", "europe", "asia"],
                "companies": ["EQIX", "DLR", "AMT"],
                "notes": "Data centers consume ~1-2% of global electricity",
            },
            {
                "stage": "cloud_platforms",
                "name": "Cloud Platforms",
                "name_he": "פלטפורמות ענן",
                "regions": ["us"],
                "companies": ["AMZN", "MSFT", "GOOGL", "ORCL", "CRM"],
            },
            {
                "stage": "ai_software",
                "name": "AI Software & Applications",
                "name_he": "תוכנת AI",
                "regions": ["us", "israel"],
                "companies": ["MSFT", "GOOGL", "META", "CRM", "PLTR"],
                "israeli_companies": ["AI21 Labs", "Mobileye (MBLY)", "NICE"],
                "notes": "Israel has 500+ AI startups",
            },
        ],
        "risk_factors": [
            {"factor": "GPU shortage", "impact": "high", "affects": ["compute_hardware", "data_centers"]},
            {"factor": "Energy costs for AI training", "impact": "medium", "affects": ["data_centers"]},
            {"factor": "AI regulation (EU AI Act)", "impact": "medium", "affects": ["ai_software"]},
            {"factor": "US-China chip export ban", "impact": "high", "affects": ["compute_hardware"]},
        ],
    },

    # ── PHARMA / BIOTECH ──
    "pharma": {
        "name": "Pharmaceutical Supply Chain",
        "name_he": "שרשרת אספקה — פארמה",
        "stages": [
            {
                "stage": "research",
                "name": "Drug Discovery & Research",
                "name_he": "מחקר ופיתוח תרופות",
                "regions": ["us", "europe", "israel"],
                "companies": ["LLY", "NVO", "JNJ", "MRK", "PFE", "AZN"],
                "israeli_companies": ["TEVA"],
                "notes": "Teva — world's largest generic drug manufacturer",
            },
            {
                "stage": "clinical_trials",
                "name": "Clinical Trials",
                "name_he": "ניסויים קליניים",
                "regions": ["us", "europe", "asia"],
                "companies": ["CRL", "ICLR", "PPD"],
            },
            {
                "stage": "api_manufacturing",
                "name": "Active Ingredient Manufacturing",
                "name_he": "ייצור חומרים פעילים",
                "regions": ["asia", "europe"],
                "countries": ["India", "China", "Ireland", "Switzerland"],
                "notes": "India & China produce ~80% of global pharmaceutical APIs",
            },
            {
                "stage": "formulation",
                "name": "Drug Formulation & Packaging",
                "name_he": "פורמולציה ואריזה",
                "regions": ["us", "europe", "israel"],
                "companies": ["TMO", "DHR", "A"],
                "israeli_companies": ["TEVA"],
            },
            {
                "stage": "distribution",
                "name": "Distribution & Pharmacies",
                "name_he": "הפצה ובתי מרקחת",
                "regions": ["us", "europe"],
                "companies": ["MCK", "ABC", "CAH", "CVS", "WBA"],
            },
        ],
        "risk_factors": [
            {"factor": "India API export restrictions", "impact": "high", "affects": ["api_manufacturing"]},
            {"factor": "Patent expiration (patent cliff)", "impact": "high", "affects": ["research"]},
            {"factor": "FDA approval delays", "impact": "medium", "affects": ["clinical_trials"]},
            {"factor": "Drug pricing legislation", "impact": "medium", "affects": ["distribution"]},
        ],
    },
}


def get_supply_chains(chain: Optional[str] = None) -> dict | list[dict]:
    """
    Get supply chain mapping data.

    Args:
        chain: Specific chain key (semiconductors, ev_batteries, energy, food, cybersecurity, ai_cloud, pharma)

    Returns:
        Single chain dict or list of all chains
    """
    if chain:
        data = SUPPLY_CHAINS.get(chain)
        if not data:
            return {}
        return data

    return [
        {"key": k, "name": v["name"], "name_he": v["name_he"], "stages": len(v["stages"])}
        for k, v in SUPPLY_CHAINS.items()
    ]


def get_cross_domain_impacts(commodity: str) -> list[dict]:
    """
    Given a commodity, find all supply chains it affects.

    Args:
        commodity: Commodity key (copper, lithium, gold, crude_oil, etc.)

    Returns:
        List of affected supply chains with specific stages
    """
    cache_key = f"impact:{commodity}"
    now = time.time()

    if cache_key in _chain_cache:
        cached = _chain_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    impacts = []
    for chain_key, chain in SUPPLY_CHAINS.items():
        for stage in chain["stages"]:
            commodities = stage.get("commodities", [])
            if commodity in commodities:
                impacts.append({
                    "chain": chain_key,
                    "chain_name": chain["name"],
                    "chain_name_he": chain["name_he"],
                    "stage": stage["stage"],
                    "stage_name": stage["name"],
                    "stage_name_he": stage["name_he"],
                    "regions": stage.get("regions", []),
                    "companies": stage.get("companies", []),
                    "israeli_companies": stage.get("israeli_companies", []),
                })

    _chain_cache[cache_key] = {"time": now, "data": impacts}
    return impacts


def get_israeli_connections() -> list[dict]:
    """
    Get all Israeli connections across supply chains.
    Shows how Israel fits into global supply chains.
    """
    connections = []
    for chain_key, chain in SUPPLY_CHAINS.items():
        for stage in chain["stages"]:
            il_companies = stage.get("israeli_companies", [])
            il_connection = stage.get("israeli_connection", "")
            regions = stage.get("regions", [])
            notes = stage.get("notes", "")

            if il_companies or il_connection or "israel" in regions:
                connections.append({
                    "chain": chain_key,
                    "chain_name": chain["name"],
                    "chain_name_he": chain["name_he"],
                    "stage": stage["stage"],
                    "stage_name": stage["name"],
                    "stage_name_he": stage["name_he"],
                    "israeli_companies": il_companies,
                    "israeli_connection": il_connection,
                    "notes": notes,
                })

    return connections


def get_risk_analysis(chain: Optional[str] = None) -> list[dict]:
    """Get risk factors across supply chains."""
    risks = []
    chains = {chain: SUPPLY_CHAINS[chain]} if chain and chain in SUPPLY_CHAINS else SUPPLY_CHAINS

    for chain_key, chain_data in chains.items():
        for risk in chain_data.get("risk_factors", []):
            risks.append({
                "chain": chain_key,
                "chain_name": chain_data["name"],
                "chain_name_he": chain_data["name_he"],
                **risk,
            })

    # Sort by impact severity
    impact_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda x: impact_order.get(x.get("impact", "low"), 99))
    return risks
