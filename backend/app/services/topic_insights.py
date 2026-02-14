"""
Topic & Stock Insight Generator for TrendVest.
Provides AI-powered explanations of why topics are trending and how they
connect to specific stocks. Works with or without an Anthropic API key
by providing curated fallback insights.
"""
import os
import json
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None

# ── Curated insights (lazy-loaded to save ~200KB when not used) ──

_TOPIC_INSIGHTS: dict[str, dict] | None = None
_RELATED_TOPICS: dict[str, list[dict]] | None = None
_HIDDEN_CONNECTIONS: dict[str, list[dict]] | None = None


def _load_insights():
    """Load all insight data on first access."""
    global _TOPIC_INSIGHTS, _RELATED_TOPICS, _HIDDEN_CONNECTIONS
    if _TOPIC_INSIGHTS is not None:
        return
    _TOPIC_INSIGHTS, _RELATED_TOPICS, _HIDDEN_CONNECTIONS = _build_insights()


def _get_topic_insights() -> dict[str, dict]:
    _load_insights()
    return _TOPIC_INSIGHTS


def _get_related_topics() -> dict[str, list[dict]]:
    _load_insights()
    return _RELATED_TOPICS


def _get_hidden_connections() -> dict[str, list[dict]]:
    _load_insights()
    return _HIDDEN_CONNECTIONS


def _build_insights():
    """Build all insight data structures. Called once on first access."""
    topic_insights: dict[str, dict] = {
    "ai": {
        "why_trending_en": "AI is the dominant tech trend of the decade. The explosive growth of large language models (ChatGPT, Gemini, Claude), enterprise AI adoption, and the AI chip arms race are driving massive investment. Companies are racing to integrate AI into every product, creating unprecedented demand for GPU computing power and AI infrastructure.",
        "why_trending_he": "בינה מלאכותית היא הטרנד הטכנולוגי המוביל של העשור. הצמיחה המטאורית של מודלי שפה גדולים (ChatGPT, Gemini, Claude), אימוץ AI בארגונים ומרוץ החימוש בשבבי AI מניעים השקעות עצומות. חברות מתחרות על שילוב AI בכל מוצר, ויוצרות ביקוש חסר תקדים לכוח עיבוד GPU ותשתיות AI.",
        "stock_connections_en": {
            "NVDA": "Nvidia dominates the AI chip market with ~80% share. Their H100/B100 GPUs are essential for training and running AI models. Every major AI company is their customer.",
            "MSFT": "Microsoft invested $13B in OpenAI and integrated Copilot AI across Office, Azure, and GitHub. Azure cloud revenue is growing fast as companies build AI infrastructure.",
            "GOOGL": "Google built Gemini (their ChatGPT competitor), owns DeepMind, and has AI across Search, YouTube, and Cloud. They also design their own TPU AI chips.",
            "PLTR": "Palantir's AI Platform (AIP) helps enterprises deploy AI for decision-making. Government and commercial AI contracts are growing rapidly.",
            "AMD": "AMD's MI300 chips are the main competitor to Nvidia in the AI GPU market. Growing data center revenue as companies diversify their AI chip suppliers.",
        },
        "stock_connections_he": {
            "NVDA": "אנבידיה שולטת בשוק שבבי ה-AI עם ~80% נתח שוק. ה-GPU שלהם חיוניים לאימון והרצת מודלי AI. כל חברת AI גדולה היא לקוחה שלהם.",
            "MSFT": "מיקרוסופט השקיעה $13 מיליארד ב-OpenAI ושילבה Copilot AI בכל מוצריה. הכנסות Azure צומחות במהירות עם בניית תשתיות AI.",
            "GOOGL": "גוגל בנתה את Gemini, מחזיקה ב-DeepMind, ומשלבת AI בחיפוש, יוטיוב וענן. גם מתכננת שבבי TPU משלה.",
            "PLTR": "פלטפורמת ה-AI של פלנטיר עוזרת לארגונים לפרוס AI לקבלת החלטות. חוזי AI ממשלתיים ומסחריים צומחים.",
            "AMD": "שבבי MI300 של AMD הם המתחרה העיקרי לאנבידיה. הכנסות מרכזי נתונים צומחות ככל שחברות מגוונות ספקים.",
        },
    },
    "nuclear": {
        "why_trending_en": "Nuclear energy is experiencing a renaissance driven by AI data center power demands, government clean energy policies, and energy security concerns. Tech giants like Microsoft, Google, and Amazon are signing nuclear power deals to fuel their AI infrastructure. Uranium prices are surging as supply can't keep up.",
        "why_trending_he": "אנרגיה גרעינית חווה רנסנס בזכות הביקוש לחשמל ממרכזי נתונים של AI, מדיניות אנרגיה נקייה ודאגות ביטחון אנרגטי. ענקיות טק כמו מיקרוסופט וגוגל חותמות על עסקאות אנרגיה גרעינית. מחירי אורניום עולים כשההיצע לא עומד בביקוש.",
        "stock_connections_en": {
            "CCJ": "Cameco is the world's largest publicly traded uranium producer. They directly benefit from rising uranium prices and long-term supply contracts with utilities.",
            "LEU": "Centrus Energy enriches uranium for nuclear fuel. They're one of only two US-authorized enrichers — a critical national security asset.",
            "SMR": "NuScale is developing small modular reactors (SMRs) — smaller, cheaper nuclear plants that can be deployed faster. Ideal for AI data centers.",
            "NNE": "Nano Nuclear develops micro-reactors for portable and remote power. Potential game-changer for off-grid AI data centers and military applications.",
            "UEC": "Uranium Energy Corp mines uranium in the Americas. Benefits from the push for domestic uranium supply as countries reduce dependence on Russian fuel.",
        },
        "stock_connections_he": {
            "CCJ": "קמקו היא יצרנית האורניום הגדולה בעולם. נהנית ישירות מעליית מחירי אורניום וחוזי אספקה ארוכי טווח.",
            "LEU": "סנטרוס מעשירה אורניום לדלק גרעיני. אחת משתי חברות אמריקאיות מורשות — נכס ביטחון לאומי קריטי.",
            "SMR": "NuScale מפתחת כורים מודולריים קטנים — תחנות גרעיניות קטנות וזולות יותר. אידיאליים למרכזי נתונים של AI.",
            "NNE": "Nano Nuclear מפתחת מיקרו-כורים לאנרגיה ניידת. פוטנציאל למרכזי נתונים מנותקים מהרשת.",
            "UEC": "Uranium Energy כורה אורניום באמריקה. נהנית מהדחיפה לאספקה מקומית כשמדינות מפחיתות תלות בדלק רוסי.",
        },
    },
    "glp1": {
        "why_trending_en": "GLP-1 drugs like Ozempic and Mounjaro are revolutionizing obesity treatment, one of the largest addressable health markets. Analysts estimate this could become a $150B+ market. These drugs are also showing benefits for heart disease, liver disease, and addiction, expanding the opportunity dramatically.",
        "why_trending_he": "תרופות GLP-1 כמו Ozempic ו-Mounjaro מחוללות מהפכה בטיפול בהשמנה — אחד השווקים הבריאותיים הגדולים ביותר. אנליסטים מעריכים שוק של $150+ מיליארד. התרופות גם מראות יתרונות למחלות לב, כבד והתמכרויות.",
        "stock_connections_en": {
            "LLY": "Eli Lilly makes Mounjaro/Zepbound — the most effective weight loss drug on the market. Their stock has tripled as GLP-1 revenue exceeded expectations every quarter.",
            "NVO": "Novo Nordisk makes Ozempic/Wegovy — the original GLP-1 blockbuster. They're racing to expand manufacturing to meet overwhelming demand.",
            "AMGN": "Amgen is developing MariTide, a next-gen obesity drug that could work better with less frequent dosing. A potential challenger to Lilly and Novo.",
            "VKTX": "Viking Therapeutics has VK2735 in clinical trials — showing strong weight loss results that could make them an acquisition target by big pharma.",
        },
        "stock_connections_he": {
            "LLY": "אלי לילי מייצרת Mounjaro/Zepbound — תרופת ההרזיה היעילה ביותר. המניה שלהם שילשה את ערכה כשהכנסות GLP-1 עלו על הציפיות.",
            "NVO": "נובו נורדיסק מייצרת Ozempic/Wegovy — הבלוקבסטר המקורי. מתחרות להרחיב ייצור כדי לעמוד בביקוש.",
            "AMGN": "אמג'ן מפתחת MariTide — תרופת השמנה מהדור הבא שעשויה לעבוד טוב יותר עם מינון פחות תכוף.",
            "VKTX": "ויקינג תרפיוטיקס עם VK2735 בניסויים קליניים — מראה תוצאות הרזיה חזקות שיכולות להפוך אותם למטרת רכישה.",
        },
    },
    "quantum": {
        "why_trending_en": "Quantum computing hit major milestones with Google's Willow chip achieving quantum error correction breakthroughs. The technology promises to revolutionize drug discovery, cryptography, materials science, and financial modeling. Government and corporate investment is accelerating.",
        "why_trending_he": "מחשוב קוונטי הגיע לאבני דרך משמעותיות עם שבב Willow של גוגל שהשיג פריצות בתיקון שגיאות קוונטיות. הטכנולוגיה מבטיחה לחולל מהפכה בתגלית תרופות, הצפנה, מדע החומרים ומידול פיננסי.",
        "stock_connections_en": {
            "IONQ": "IonQ builds trapped-ion quantum computers and sells quantum computing as a cloud service. Partnerships with major cloud providers give them distribution.",
            "RGTI": "Rigetti makes superconducting quantum processors and offers quantum cloud computing. Their hybrid quantum-classical approach targets near-term practical applications.",
            "QBTS": "D-Wave pioneered quantum annealing — a different approach that's already solving optimization problems for enterprises like Mastercard and Volkswagen.",
        },
        "stock_connections_he": {
            "IONQ": "IonQ בונה מחשבים קוונטיים ומוכרת מחשוב קוונטי כשירות ענן. שותפויות עם ספקי ענן גדולים נותנות להם הפצה.",
            "RGTI": "ריג'טי מייצרת מעבדים קוונטיים על-מוליכים ומציעה מחשוב קוונטי בענן. הגישה ההיברידית שלהם מכוונת ליישומים מעשיים.",
            "QBTS": "D-Wave חלצה דרך עם quantum annealing — גישה שונה שכבר פותרת בעיות אופטימיזציה עבור ארגונים כמו Mastercard ו-Volkswagen.",
        },
    },
    "ev": {
        "why_trending_en": "The EV transition continues with falling battery costs, expanding charging infrastructure, and government mandates. Tesla's dominance is being challenged by Chinese manufacturers and legacy automakers. The market is shifting from early adopters to mainstream buyers.",
        "why_trending_he": "המעבר לרכבים חשמליים נמשך עם ירידת עלויות סוללות, הרחבת תשתיות טעינה ותקנות ממשלתיות. הדומיננטיות של טסלה מאותגרת על ידי יצרנים סיניים ויצרני רכב ותיקים.",
        "stock_connections_en": {
            "TSLA": "Tesla leads global EV sales but is also an energy/AI/robotics company. Robotaxi, Optimus robot, and energy storage are major growth catalysts beyond cars.",
            "RIVN": "Rivian makes premium electric trucks and SUVs. Amazon partnership for delivery vans provides revenue stability while consumer sales grow.",
            "NIO": "NIO is China's premium EV maker with innovative battery-swap technology. Expanding into Europe while competing in the world's largest EV market.",
            "LI": "Li Auto makes extended-range EVs that solve range anxiety. One of the most profitable Chinese EV companies with strong sales growth.",
        },
        "stock_connections_he": {
            "TSLA": "טסלה מובילה מכירות EV עולמית אך היא גם חברת אנרגיה/AI/רובוטיקה. רובוטקסי, רובוט אופטימוס ואגירת אנרגיה הם קטליזטורים מעבר לרכבים.",
            "RIVN": "ריביאן מייצרת טנדרים ו-SUV חשמליים פרימיום. שותפות עם אמזון לרכבי משלוח מספקת יציבות.",
            "NIO": "NIO היא יצרנית ה-EV הפרימיום של סין עם טכנולוגיית החלפת סוללות. מתרחבת לאירופה.",
            "LI": "Li Auto מייצרת רכבים חשמליים בטווח מורחב. אחת מחברות ה-EV הסיניות הרווחיות ביותר.",
        },
    },
    "cyber": {
        "why_trending_en": "Cybersecurity spending is surging as AI-powered attacks become more sophisticated, ransomware threats escalate, and governments mandate stronger security. The shift to cloud and remote work expanded the attack surface dramatically. Every major breach drives more corporate security spending.",
        "why_trending_he": "ההוצאות על סייבר זינקו עם התקפות מונעות AI מתוחכמות יותר, איומי כופר מתגברים ומנדטים ממשלתיים. המעבר לענן ועבודה מרחוק הרחיב את משטח התקיפה.",
        "stock_connections_en": {
            "CRWD": "CrowdStrike's Falcon platform is the leader in endpoint security using AI. Their cloud-native approach makes them the go-to for modern enterprises replacing legacy antivirus.",
            "PANW": "Palo Alto Networks offers the broadest security platform — firewalls, cloud security, SOC automation. Their platformization strategy consolidates multiple security tools into one.",
            "ZS": "Zscaler pioneered Zero Trust security for cloud. As companies move away from VPNs, Zscaler's cloud security platform handles internet traffic for Fortune 500 companies.",
        },
        "stock_connections_he": {
            "CRWD": "פלטפורמת Falcon של CrowdStrike מובילה באבטחת נקודות קצה באמצעות AI. הגישה העננית שלהם מחליפה אנטי-וירוס מסורתי.",
            "PANW": "פאלו אלטו מציעה את פלטפורמת האבטחה הרחבה ביותר — חומות אש, אבטחת ענן, אוטומציית SOC.",
            "ZS": "Zscaler חלצה דרך באבטחת Zero Trust לענן. כשחברות עוזבות VPN, Zscaler מטפלת בתעבורת אינטרנט של חברות Fortune 500.",
        },
    },
    "crypto": {
        "why_trending_en": "Bitcoin hit all-time highs with the approval of Bitcoin ETFs, institutional adoption surging, and the 2024 halving reducing supply. Regulatory clarity is improving globally and major financial institutions now offer crypto products to their clients.",
        "why_trending_he": "ביטקוין הגיע לשיאים חדשים עם אישור ETF ביטקוין, אימוץ מוסדי גובר והאלבינג של 2024 שצמצם את ההיצע. הרגולציה משתפרת ומוסדות פיננסיים גדולים מציעים מוצרי קריפטו.",
        "stock_connections_en": {
            "MSTR": "MicroStrategy holds ~200K+ Bitcoin, making it essentially a leveraged Bitcoin proxy. When BTC rises, MSTR tends to amplify the move.",
            "COIN": "Coinbase is the largest US crypto exchange. Revenue grows with trading volume and they earn fees on Bitcoin ETF custody for major issuers.",
            "MARA": "Marathon Digital is one of the largest Bitcoin miners. They profit when Bitcoin price exceeds their mining cost, which benefits from economies of scale.",
        },
        "stock_connections_he": {
            "MSTR": "MicroStrategy מחזיקה 200K+ ביטקוין, מה שהופך אותה למעשה למנוף ביטקוין. כשביטקוין עולה, MSTR נוטה להגביר את התנועה.",
            "COIN": "Coinbase היא בורסת הקריפטו הגדולה בארה\"ב. הכנסות גדלות עם נפח מסחר ועמלות משמורת ETF ביטקוין.",
            "MARA": "Marathon Digital היא אחת מכורות הביטקוין הגדולות. רווחית כשמחיר ביטקוין עולה על עלות הכרייה.",
        },
    },
    "space": {
        "why_trending_en": "The space economy is booming with falling launch costs, satellite internet expansion, and growing defense spending. SpaceX's Starlink success proved the commercial viability of mega-constellations. Government space budgets are increasing globally.",
        "why_trending_he": "כלכלת החלל פורחת עם ירידת עלויות שיגור, הרחבת אינטרנט לווייני והגדלת תקציבי ביטחון. הצלחת Starlink של SpaceX הוכיחה כדאיות מסחרית.",
        "stock_connections_en": {
            "RKLB": "Rocket Lab is the second most frequently launching rocket company after SpaceX. Their Electron rocket serves small satellites and Neutron will compete for larger payloads.",
            "ASTS": "AST SpaceMobile is building a space-based cellular network — connecting regular phones directly to satellites. Partnerships with AT&T and Vodafone for global coverage.",
        },
        "stock_connections_he": {
            "RKLB": "Rocket Lab היא חברת השיגור השנייה בתדירות אחרי SpaceX. רקטת Electron שלהם משרתת לוויינים קטנים ו-Neutron יתחרה על מטענים גדולים.",
            "ASTS": "AST SpaceMobile בונה רשת סלולרית מהחלל — מחברת טלפונים רגילים ישירות ללוויינים. שותפויות עם AT&T ו-Vodafone.",
        },
    },
    "solar": {
        "why_trending_en": "Solar energy is growing rapidly as costs continue to fall and governments push renewable mandates. The Inflation Reduction Act provides massive subsidies for US solar. Global solar installations hit record levels as countries race to decarbonize.",
        "why_trending_he": "אנרגיה סולארית צומחת במהירות ככל שהעלויות ממשיכות לרדת וממשלות דוחפות מנדטים ירוקים. חוק הפחתת האינפלציה מספק סובסידיות עצומות לסולארי בארה\"ב.",
        "stock_connections_en": {
            "ENPH": "Enphase makes microinverters — the brains of solar systems. Their technology maximizes energy production and they benefit from the residential solar boom.",
            "FSLR": "First Solar manufactures thin-film solar panels in the US. They benefit from tariffs on Chinese panels and IRA manufacturing credits.",
        },
        "stock_connections_he": {
            "ENPH": "Enphase מייצרת מיקרו-ממירים — המוח של מערכות סולאריות. הטכנולוגיה שלהם ממקסמת ייצור אנרגיה.",
            "FSLR": "First Solar מייצרת פאנלים סולאריים בארה\"ב. נהנית ממכסים על פאנלים סיניים ומענקי ייצור.",
        },
    },
    "semi": {
        "why_trending_en": "Semiconductors are the backbone of the AI revolution, driving unprecedented demand for advanced chips. Government CHIPS Acts globally are reshoring manufacturing. The industry is consolidating around leading-edge producers as chip complexity increases.",
        "why_trending_he": "מוליכים למחצה הם עמוד השדרה של מהפכת ה-AI. חוקי CHIPS ממשלתיים מחזירים ייצור. התעשייה מתגבשת סביב יצרנים מתקדמים ככל שמורכבות השבבים גדלה.",
        "stock_connections_en": {
            "TSM": "TSMC manufactures ~90% of the world's most advanced chips. Every major chip designer (Apple, Nvidia, AMD, Qualcomm) depends on them.",
            "AVGO": "Broadcom designs chips for networking, storage, and custom AI accelerators. They're building custom AI chips for Google and other hyperscalers.",
            "INTC": "Intel is investing $100B+ to rebuild US chip manufacturing. Their foundry business aims to compete with TSMC by making chips for other companies.",
        },
        "stock_connections_he": {
            "TSM": "TSMC מייצרת ~90% מהשבבים המתקדמים בעולם. כל מתכנן שבבים גדול (Apple, Nvidia, AMD) תלוי בהם.",
            "AVGO": "Broadcom מתכננת שבבים לרשתות, אחסון ומאיצי AI מותאמים. בונים שבבי AI מותאמים לגוגל.",
            "INTC": "אינטל משקיעה $100+ מיליארד לבנות מחדש ייצור שבבים בארה\"ב. עסקי המפעל שלהם מכוונים להתחרות ב-TSMC.",
        },
    },
    }

    related_topics: dict[str, list[dict]] = {
    "ai": [
        {"slug": "semi", "name": "Semiconductors", "connection": "AI runs on chips — every AI advance drives chip demand"},
        {"slug": "nuclear", "name": "Nuclear Energy", "connection": "AI data centers need massive power — nuclear is the solution"},
        {"slug": "cyber", "name": "Cybersecurity", "connection": "AI powers both cyberattacks and cyber defense"},
        {"slug": "cloud", "name": "Cloud Computing", "connection": "AI models run on cloud infrastructure"},
    ],
    "nuclear": [
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI data centers are driving nuclear power demand"},
        {"slug": "lithium", "name": "Lithium & Batteries", "connection": "Nuclear + batteries = baseload + storage energy solution"},
        {"slug": "defense", "name": "Defense", "connection": "Nuclear propulsion for submarines, carriers, and space"},
    ],
    "ev": [
        {"slug": "lithium", "name": "Lithium & Batteries", "connection": "EVs depend entirely on lithium-ion battery supply chains"},
        {"slug": "solar", "name": "Solar Energy", "connection": "Solar + EV = home charging with free energy from the sun"},
        {"slug": "semi", "name": "Semiconductors", "connection": "Modern EVs use 3,000+ chips per vehicle"},
    ],
    "glp1": [
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI accelerates drug discovery and clinical trial design"},
        {"slug": "crispr", "name": "Gene Editing", "connection": "Next-gen obesity treatments may combine GLP-1 with gene therapy"},
    ],
    "quantum": [
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "Quantum computing could exponentially speed up AI training"},
        {"slug": "cyber", "name": "Cybersecurity", "connection": "Quantum threatens current encryption — drives post-quantum crypto"},
        {"slug": "crispr", "name": "Gene Editing", "connection": "Quantum simulation could model molecular interactions for drug design"},
    ],
    "cyber": [
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI is used in both offensive attacks and defensive security"},
        {"slug": "cloud", "name": "Cloud Computing", "connection": "Cloud migration expands the attack surface — drives security spend"},
        {"slug": "defense", "name": "Defense", "connection": "Nation-state cyber warfare drives government security budgets"},
    ],
    "space": [
        {"slug": "defense", "name": "Defense", "connection": "Space is a military domain — satellites for intelligence, GPS, comms"},
        {"slug": "semi", "name": "Semiconductors", "connection": "Satellites need radiation-hardened chips"},
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI processes satellite imagery and autonomous spacecraft navigation"},
    ],
    "crypto": [
        {"slug": "fintech", "name": "Fintech", "connection": "Crypto infrastructure merges with traditional finance"},
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI trading bots, AI-powered DeFi, and crypto + AI convergence"},
        {"slug": "semi", "name": "Semiconductors", "connection": "Bitcoin mining drives demand for specialized ASIC chips"},
    ],
    "solar": [
        {"slug": "ev", "name": "Electric Vehicles", "connection": "Solar + EV charging is a growing residential combo"},
        {"slug": "lithium", "name": "Lithium & Batteries", "connection": "Solar needs battery storage for when the sun doesn't shine"},
    ],
    "semi": [
        {"slug": "ai", "name": "Artificial Intelligence", "connection": "AI is the biggest growth driver for advanced chip demand"},
        {"slug": "ev", "name": "Electric Vehicles", "connection": "Each EV uses thousands of semiconductors"},
        {"slug": "defense", "name": "Defense", "connection": "Military systems depend on advanced chips — CHIPS Act is partly about security"},
    ],
    }

    hidden_connections: dict[str, list[dict]] = {
    "ai": [
        {"ticker": "VRT", "company": "Vertiv Holdings", "connection_en": "Makes cooling systems and power infrastructure for AI data centers. Data centers overheat without Vertiv's thermal management.", "connection_he": "מייצרת מערכות קירור ותשתיות חשמל למרכזי נתונים של AI. מרכזי נתונים מתחממים ללא ניהול התרמי של Vertiv."},
        {"ticker": "EQIX", "company": "Equinix", "connection_en": "Largest data center REIT — owns the physical buildings where AI models run. More AI = more data center demand.", "connection_he": "קרן הנדל\"ן הגדולה למרכזי נתונים — בעלת המבנים הפיזיים שבהם מודלי AI רצים."},
        {"ticker": "FCX", "company": "Freeport-McMoRan", "connection_en": "World's largest copper miner. AI data centers use massive amounts of copper for wiring and electrical systems.", "connection_he": "כורת הנחושת הגדולה בעולם. מרכזי נתונים של AI צורכים כמויות עצומות של נחושת לחיווט ומערכות חשמל."},
    ],
    "nuclear": [
        {"ticker": "BWX", "company": "BWX Technologies", "connection_en": "Makes nuclear components and fuel for US Navy reactors. Also supplies parts for commercial nuclear plants.", "connection_he": "מייצרת רכיבים גרעיניים ודלק לכורים של הצי האמריקאי. גם מספקת חלקים לתחנות גרעיניות מסחריות."},
        {"ticker": "FLR", "company": "Fluor Corporation", "connection_en": "Major engineering firm that builds nuclear power plants. Benefits from the nuclear construction boom.", "connection_he": "חברת הנדסה גדולה שבונה תחנות כוח גרעיניות. נהנית מפריחת הבנייה הגרעינית."},
    ],
    "ev": [
        {"ticker": "ALB", "company": "Albemarle", "connection_en": "Top lithium producer — lithium is the critical material in every EV battery. No lithium = no EVs.", "connection_he": "יצרנית ליתיום מובילה — ליתיום הוא החומר הקריטי בכל סוללת EV. בלי ליתיום אין רכבים חשמליים."},
        {"ticker": "APTV", "company": "Aptiv", "connection_en": "Makes electrical architecture and advanced wiring for EVs. Every EV needs their high-voltage connectors.", "connection_he": "מייצרת ארכיטקטורה חשמלית וחיווט מתקדם ל-EV. כל רכב חשמלי צריך את המחברים שלהם."},
        {"ticker": "ON", "company": "ON Semiconductor", "connection_en": "Makes silicon carbide (SiC) chips for EV powertrains. These chips handle high voltage more efficiently than regular silicon.", "connection_he": "מייצרת שבבי סיליקון קרביד (SiC) למערכות הנעה חשמליות. שבבים אלה מטפלים במתח גבוה ביעילות."},
    ],
    "space": [
        {"ticker": "HWM", "company": "Howmet Aerospace", "connection_en": "Makes precision titanium and nickel parts for rocket engines. SpaceX and Rocket Lab use their components.", "connection_he": "מייצרת חלקי טיטניום וניקל מדויקים למנועי רקטות. SpaceX ו-Rocket Lab משתמשות ברכיבים שלהם."},
        {"ticker": "LHX", "company": "L3Harris Technologies", "connection_en": "Builds satellite communication payloads and sensors. Key supplier for military and commercial satellite constellations.", "connection_he": "בונה מטעני תקשורת לווייניים וחיישנים. ספק מפתח למערכי לוויינים צבאיים ומסחריים."},
    ],
    "cyber": [
        {"ticker": "FTNT", "company": "Fortinet", "connection_en": "Makes network security appliances with custom ASIC chips for faster threat detection. Especially strong in operational technology (OT) security.", "connection_he": "מייצרת מכשירי אבטחת רשת עם שבבי ASIC מותאמים. חזקה במיוחד באבטחת טכנולוגיה תפעולית (OT)."},
        {"ticker": "AKAM", "company": "Akamai", "connection_en": "CDN giant pivoting to security — protects websites from DDoS attacks and bot traffic. Handles 30% of global web traffic.", "connection_he": "ענקית CDN שעוברת לאבטחה — מגנה על אתרים מהתקפות DDoS ותעבורת בוטים."},
    ],
    "glp1": [
        {"ticker": "HOLX", "company": "Hologic", "connection_en": "Medical devices company that benefits from the weight loss drug trend — healthier patients get more preventive screenings.", "connection_he": "חברת מכשירים רפואיים שנהנית ממגמת תרופות ההרזיה — חולים בריאים יותר עושים יותר בדיקות מניעתיות."},
        {"ticker": "WST", "company": "West Pharmaceutical", "connection_en": "Makes drug delivery systems (syringes, vials, injection pens). GLP-1 drugs are injected weekly — massive demand for delivery devices.", "connection_he": "מייצרת מערכות משלוח תרופות (מזרקים, בקבוקונים, עטי הזרקה). תרופות GLP-1 מוזרקות שבועית — ביקוש עצום."},
    ],
    "crypto": [
        {"ticker": "XYZ", "company": "Block Inc", "connection_en": "Block's Cash App lets users buy Bitcoin. They also mine Bitcoin and are building Bitcoin-focused products.", "connection_he": "Cash App של Block מאפשרת למשתמשים לקנות ביטקוין. גם כורים ביטקוין ובונים מוצרים מבוססי ביטקוין."},
    ],
    "semi": [
        {"ticker": "ASML", "company": "ASML Holding", "connection_en": "Makes EUV lithography machines — the ONLY company that can manufacture the equipment needed to make advanced chips. Global monopoly.", "connection_he": "מייצרת מכונות ליתוגרפיה EUV — החברה היחידה שיכולה לייצר ציוד לשבבים מתקדמים. מונופול עולמי."},
        {"ticker": "LRCX", "company": "Lam Research", "connection_en": "Makes wafer fabrication equipment. Every chip factory needs Lam's etching and deposition tools.", "connection_he": "מייצרת ציוד לייצור רקיקים. כל מפעל שבבים צריך את כלי החריטה וההשקעה של Lam."},
        {"ticker": "KLAC", "company": "KLA Corporation", "connection_en": "Makes chip inspection and quality control equipment. As chips get smaller, defect detection becomes more critical.", "connection_he": "מייצרת ציוד בדיקה ובקרת איכות לשבבים. ככל שהשבבים קטנים יותר, גילוי פגמים קריטי יותר."},
    ],
    "solar": [
        {"ticker": "SEDG", "company": "SolarEdge", "connection_en": "Israeli company making solar inverters and optimizers. Competes with Enphase for the residential solar market.", "connection_he": "חברה ישראלית שמייצרת ממירים ואופטימייזרים סולאריים. מתחרה ב-Enphase בשוק הסולארי הביתי."},
    ],
    }

    return topic_insights, related_topics, hidden_connections


def get_topic_insight(slug: str, language: str = "en") -> Optional[dict]:
    """Get curated insight for a topic, including related topics and hidden connections."""
    insight = _get_topic_insights().get(slug)
    if not insight:
        return None

    lang_key = "he" if language == "he" else "en"

    # Build related topics
    related = _get_related_topics().get(slug, [])

    # Build hidden connections with language-appropriate text
    raw_hidden = _get_hidden_connections().get(slug, [])
    hidden = []
    for hc in raw_hidden:
        hidden.append({
            "ticker": hc["ticker"],
            "company": hc["company"],
            "connection": hc.get(f"connection_{lang_key}", hc.get("connection_en", "")),
        })

    return {
        "slug": slug,
        "why_trending": insight.get(f"why_trending_{lang_key}", ""),
        "stock_connections": insight.get(f"stock_connections_{lang_key}", {}),
        "related_topics": related,
        "hidden_connections": hidden,
    }


def get_all_insights(language: str = "en") -> list[dict]:
    """Get all available topic insights."""
    results = []
    for slug in _get_topic_insights():
        insight = get_topic_insight(slug, language)
        if insight:
            results.append(insight)
    return results


async def generate_ai_insight(slug: str, topic_name: str, stocks: list[dict],
                               language: str = "en", momentum_score: float = 0) -> Optional[dict]:
    """Generate a fresh AI insight using Claude (requires API key)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not anthropic:
        return None

    lang = "Hebrew" if language == "he" else "English"
    stock_list = ", ".join([f"{s['ticker']} ({s.get('company_name', s.get('name', ''))})" for s in stocks[:5]])

    prompt = f"""You are a financial analyst for TrendVest, a trend-tracking stock platform.

Write a brief, insightful analysis in {lang} about why "{topic_name}" is trending in financial markets right now.

Related stocks: {stock_list}
Current momentum score: {momentum_score}/100

Include:
1. Why this trend matters NOW (2-3 sentences about recent catalysts)
2. For each stock listed, one sentence explaining how it connects to this trend

Rules:
- Keep it under 250 words total
- Be educational and informative
- NEVER give buy/sell recommendations
- Add a brief disclaimer at the end
- Write in {lang}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "slug": slug,
            "ai_analysis": response.content[0].text,
            "generated": True,
        }
    except Exception as e:
        print(f"AI insight generation error: {e}")
        return None
