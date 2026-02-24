"""
Supply Chain Insights — "Did You Know?" tips for TrendVest.

Curated correlation-based insights that teach users about real-world
commodity and supply-chain relationships.  Each tip links two (or more)
commodities / sectors and explains the causal mechanism.

Tips are returned via API and shown as rotating "הידעת?" cards in the
SupplyChainExplorer component.
"""

from __future__ import annotations

import random
from typing import Optional

# ── Insight definitions ──

SUPPLY_CHAIN_TIPS: list[dict] = [
    # ── Agriculture → Meat chain ──
    {
        "id": "corn_cattle",
        "tip_he": "כשמחיר התירס עולה, מחיר הבשר בדרך כלל עולה בהמשך — כי תירס הוא מרכיב מרכזי במזון לבקר.",
        "tip_en": "When corn prices rise, meat prices usually follow — because corn is a key ingredient in cattle feed.",
        "commodities": ["corn", "live_cattle"],
        "chains": ["food"],
        "category": "agriculture",
    },
    {
        "id": "soybeans_cattle",
        "tip_he": "סויה ותירס הם שני מרכיבי המזון העיקריים לבעלי חיים. עלייה בשניהם מעלה את עלות ייצור הבשר בעולם.",
        "tip_en": "Soybeans and corn are the two main livestock feed ingredients. When both rise, global meat production costs spike.",
        "commodities": ["soybeans", "corn", "live_cattle"],
        "chains": ["food"],
        "category": "agriculture",
    },
    # ── Cocoa & Coffee ──
    {
        "id": "cocoa_chocolate",
        "tip_he": "קקאו זינק ב-300% בין 2023-2025 בגלל מחלות עצים במערב אפריקה. זה הכה ישירות ברווחיות של Hershey ו-Mondelez.",
        "tip_en": "Cocoa surged 300% in 2023-2025 due to crop disease in West Africa, directly hitting profits at Hershey and Mondelez.",
        "commodities": ["cocoa"],
        "chains": ["food"],
        "companies": ["HSY", "MDLZ"],
        "category": "agriculture",
    },
    {
        "id": "coffee_frost",
        "tip_he": "כ-35% מהקפה בעולם מגיע מברזיל. כפור אחד בולט יכול לזעזע את מחירי הקפה העולמיים לחודשים.",
        "tip_en": "~35% of the world's coffee comes from Brazil. A single major frost event can shake global coffee prices for months.",
        "commodities": ["coffee"],
        "chains": ["food"],
        "companies": ["SBUX", "KDP"],
        "category": "agriculture",
    },
    {
        "id": "sugar_ethanol",
        "tip_he": "בברזיל, קני סוכר משמשים גם לאתנול. כשמחיר הנפט עולה, יותר סוכר הולך לדלק — ופחות לאוכל.",
        "tip_en": "In Brazil, sugarcane is also used for ethanol. When oil prices rise, more sugar goes to fuel — and less to food.",
        "commodities": ["sugar", "crude_oil"],
        "chains": ["food", "energy"],
        "category": "agriculture",
    },
    {
        "id": "oj_climate",
        "tip_he": "מיץ תפוזים הוא אחת הסחורות התנודתיות ביותר. הוריקן אחד בפלורידה יכול להקפיץ מחירים ב-30% ביום.",
        "tip_en": "Orange juice is one of the most volatile commodities. A single hurricane in Florida can spike prices 30% in a day.",
        "commodities": ["orange_juice"],
        "chains": ["food"],
        "category": "agriculture",
    },
    # ── Cotton & Textiles ──
    {
        "id": "cotton_apparel",
        "tip_he": "כשכותנה מתייקרת, חברות אופנה כמו Nike ו-Lululemon סופגות עלויות — או מעלות מחירים לצרכן.",
        "tip_en": "When cotton prices rise, apparel companies like Nike and Lululemon either absorb costs or pass them to consumers.",
        "commodities": ["cotton"],
        "chains": ["food"],
        "companies": ["NKE", "LULU"],
        "category": "agriculture",
    },
    # ── Energy chains ──
    {
        "id": "natgas_fertilizer",
        "tip_he": "גז טבעי הוא חומר הגלם המרכזי לייצור דשנים. עליית מחירי גז → דשנים יקרים → מזון יקר.",
        "tip_en": "Natural gas is the key feedstock for fertilizer production. Gas price spike → expensive fertilizers → expensive food.",
        "commodities": ["natural_gas", "wheat", "corn"],
        "chains": ["energy", "food"],
        "category": "energy",
    },
    {
        "id": "oil_gasoline",
        "tip_he": "בנזין מהווה כ-45% מהתפוקה של בית זיקוק. כשנפט עולה, הבנזין עולה — אבל לא תמיד באותו קצב.",
        "tip_en": "Gasoline makes up ~45% of a refinery's output. When crude rises, gasoline follows — but not always at the same rate.",
        "commodities": ["crude_oil", "gasoline"],
        "chains": ["energy"],
        "category": "energy",
    },
    {
        "id": "brent_wti_spread",
        "tip_he": "הפער בין נפט ברנט ל-WTI מעיד על ביקוש גלובלי. פער גדול = אירופה ואסיה צמאות לנפט יותר מארה\"ב.",
        "tip_en": "The Brent-WTI spread signals global demand. A wide spread = Europe and Asia need oil more than the US.",
        "commodities": ["brent_oil", "crude_oil"],
        "chains": ["energy"],
        "category": "energy",
    },
    {
        "id": "heating_oil_winter",
        "tip_he": "סולר (heating oil) נוטה לזנק לקראת החורף באירופה. חורף קשה = ביקוש מטורף = מחירי אנרגיה גבוהים.",
        "tip_en": "Heating oil tends to spike ahead of European winters. A harsh winter = surging demand = high energy prices.",
        "commodities": ["heating_oil", "natural_gas"],
        "chains": ["energy"],
        "category": "energy",
    },
    {
        "id": "carbon_regulation",
        "tip_he": "קרדיט פחמן יקר = תמריץ חזק לאנרגיה ירוקה. כשמחירי הפחמן עולים, מניות סולאריות ורוח נוטות לעלות.",
        "tip_en": "Expensive carbon credits = strong incentive for green energy. When carbon prices rise, solar and wind stocks tend to follow.",
        "commodities": ["carbon"],
        "chains": ["energy"],
        "companies": ["ENPH", "SEDG", "FSLR"],
        "category": "energy",
    },
    {
        "id": "uranium_renaissance",
        "tip_he": "אורניום חווה רנסנס. יפן הפעילה מחדש כורים, אירופה סיווגה גרעין כ\"ירוק\" — הביקוש משתנה אחרי 15 שנות שקט.",
        "tip_en": "Uranium is in a renaissance. Japan restarted reactors, Europe classified nuclear as 'green' — demand is shifting after 15 quiet years.",
        "commodities": ["uranium"],
        "chains": ["energy"],
        "category": "energy",
    },
    # ── Metals & Industry ──
    {
        "id": "copper_economy",
        "tip_he": "לנחושת קוראים \"ד\"ר נחושת\" כי היא מנבאת כלכלה. עלייה = צמיחה תעשייתית. ירידה = האטה.",
        "tip_en": "Copper is called 'Dr. Copper' because it predicts the economy. Rising = industrial growth. Falling = slowdown.",
        "commodities": ["copper"],
        "chains": ["semiconductors", "ev_batteries", "energy"],
        "category": "metals",
    },
    {
        "id": "lithium_ev",
        "tip_he": "ליתיום הוא ה\"נפט הלבן\" של עידן הרכב החשמלי. מחירו נפל 80% ב-2023 בגלל עודף היצע מסין.",
        "tip_en": "Lithium is the 'white oil' of the EV era. Its price fell 80% in 2023 due to oversupply from China.",
        "commodities": ["lithium"],
        "chains": ["ev_batteries"],
        "companies": ["TSLA", "ALB"],
        "category": "industrial",
    },
    {
        "id": "nickel_batteries",
        "tip_he": "ניקל הוא מרכיב מפתח בסוללות NMC לרכב חשמלי. אינדונזיה שולטת ב-50% מהייצור העולמי.",
        "tip_en": "Nickel is a key component in NMC EV batteries. Indonesia controls ~50% of global production.",
        "commodities": ["nickel"],
        "chains": ["ev_batteries"],
        "category": "industrial",
    },
    {
        "id": "palladium_catalysts",
        "tip_he": "80% מהפלדיום הולך לממירים קטליטיים. כשרגולציית זיהום מתחזקת, הביקוש לפלדיום עולה — גם אם הרכב הופך חשמלי.",
        "tip_en": "80% of palladium goes to catalytic converters. When emission regulations tighten, palladium demand rises — even as EVs grow.",
        "commodities": ["palladium"],
        "chains": ["ev_batteries"],
        "category": "metals",
    },
    {
        "id": "gold_fear",
        "tip_he": "זהב הוא \"ביטוח הפחד\". כשהשווקים מפחדים (VIX עולה) או הריבית יורדת — המשקיעים בורחים לזהב.",
        "tip_en": "Gold is the 'fear insurance'. When markets panic (VIX rises) or rates drop — investors flee to gold.",
        "commodities": ["gold"],
        "chains": [],
        "category": "metals",
    },
    {
        "id": "silver_solar",
        "tip_he": "כסף הוא לא רק מתכת יקרה — 10% מהביקוש מגיע מפאנלים סולאריים. צמיחת הסולאר מגדילה ביקוש.",
        "tip_en": "Silver isn't just a precious metal — 10% of demand comes from solar panels. Solar growth boosts silver demand.",
        "commodities": ["silver"],
        "chains": ["energy"],
        "companies": ["FSLR", "ENPH"],
        "category": "metals",
    },
    {
        "id": "aluminum_packaging",
        "tip_he": "אלומיניום נמצא בכל מקום — מפחיות שתייה ועד מטוסים. ייצורו צורך כמות עצומה של חשמל, לכן מחירו קשור למחירי אנרגיה.",
        "tip_en": "Aluminum is everywhere — from soda cans to aircraft. Its production uses massive electricity, so its price is tied to energy costs.",
        "commodities": ["aluminum"],
        "chains": ["semiconductors"],
        "category": "metals",
    },
    {
        "id": "tin_semiconductors",
        "tip_he": "בדיל הוא חומר הלחמה העיקרי בתעשיית השבבים. בלי בדיל, אין חיבור שבבים ללוחות אלקטרוניים.",
        "tip_en": "Tin is the primary soldering material in the chip industry. Without tin, chips can't be connected to circuit boards.",
        "commodities": ["tin"],
        "chains": ["semiconductors"],
        "category": "metals",
    },
    # ── Cross-domain ──
    {
        "id": "lumber_housing",
        "tip_he": "מחיר עצים קשור ישירות לשוק הנדל\"ן בארה\"ב. עלייה חדה = בנייה פעילה. ירידה חדה = האטה בדיור.",
        "tip_en": "Lumber prices are directly tied to US housing. Sharp rise = active construction. Sharp drop = housing slowdown.",
        "commodities": ["lumber"],
        "chains": ["food"],
        "category": "agriculture",
    },
    {
        "id": "copper_silver_chips",
        "tip_he": "כל סמארטפון מכיל נחושת, כסף, בדיל, ליתיום ומתכות נדירות. עליית מחיר של אחד מהם משפיעה על כל שרשרת הטכנולוגיה.",
        "tip_en": "Every smartphone contains copper, silver, tin, lithium, and rare earths. A price spike in any of them ripples through the entire tech supply chain.",
        "commodities": ["copper", "silver", "tin", "lithium"],
        "chains": ["semiconductors", "ev_batteries"],
        "category": "industrial",
    },
    {
        "id": "oil_everything",
        "tip_he": "נפט משפיע על הכל. תחבורה, פלסטיק, דשנים, כימיקלים — כשנפט עולה ב-20%, האינפלציה עולה בהתאמה.",
        "tip_en": "Oil affects everything. Transport, plastics, fertilizers, chemicals — when oil rises 20%, inflation follows.",
        "commodities": ["crude_oil"],
        "chains": ["energy", "food"],
        "category": "energy",
    },
    {
        "id": "wheat_geopolitics",
        "tip_he": "רוסיה ואוקראינה מייצרות ~30% מהחיטה בעולם. המלחמה ב-2022 הכפילה את מחיר החיטה תוך שבועות.",
        "tip_en": "Russia and Ukraine produce ~30% of the world's wheat. The 2022 war doubled wheat prices within weeks.",
        "commodities": ["wheat"],
        "chains": ["food"],
        "category": "agriculture",
    },
    {
        "id": "platinum_hydrogen",
        "tip_he": "פלטינום הוא מרכיב חיוני בתאי דלק מימן. אם כלכלת המימן תמריא — הביקוש לפלטינום יזנק.",
        "tip_en": "Platinum is essential for hydrogen fuel cells. If the hydrogen economy takes off, platinum demand will surge.",
        "commodities": ["platinum"],
        "chains": ["ev_batteries", "energy"],
        "category": "metals",
    },
    {
        "id": "cobalt_congo",
        "tip_he": "70% מהקובלט בעולם מגיע מקונגו. סיכונים גיאופוליטיים שם משפיעים ישירות על מחירי סוללות EV.",
        "tip_en": "70% of the world's cobalt comes from Congo. Geopolitical risks there directly affect EV battery prices.",
        "commodities": ["cobalt"],
        "chains": ["ev_batteries"],
        "companies": ["TSLA", "RIVN"],
        "category": "industrial",
    },
]


def get_supply_chain_tips(
    commodity: Optional[str] = None,
    chain: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 3,
) -> list[dict]:
    """Return relevant tips, optionally filtered by commodity / chain / category."""
    pool = SUPPLY_CHAIN_TIPS

    if commodity:
        pool = [t for t in pool if commodity in t["commodities"]]
    if chain:
        pool = [t for t in pool if chain in t["chains"]]
    if category:
        pool = [t for t in pool if t["category"] == category]

    if not pool:
        pool = SUPPLY_CHAIN_TIPS

    if len(pool) <= limit:
        return pool
    return random.sample(pool, limit)


def get_random_tip() -> dict:
    """Return a single random tip — useful for "tip of the day"."""
    return random.choice(SUPPLY_CHAIN_TIPS)
