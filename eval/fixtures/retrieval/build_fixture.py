"""Build the synthetic retrieval-eval universe and its graded relevance labels.

Every company here is invented. Each one has a **true business** (written down below, before any
scores were run); relevance labels follow mechanically from it with the rubric in ``RUBRIC``. The
dataset labels (``sector``/``industry``/``sub_industry`` in the records) are what a data file would
say, and are deliberately wrong for the companies tagged ``mislabelled``: relevance is judged from
the true business, never from those labels.

Run from the repo root to regenerate ``companies.json``, ``fx_rates.json`` and ``labels.json``:

    .venv/bin/python eval/fixtures/retrieval/build_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

RUBRIC = {
    "3": "same business (true sub-industry)",
    "2": "same industry, different business",
    "1": "same sector, different industry",
    "0": "different sector",
}

# business -> (sector, industry, dataset sub_industry label)
TAXONOMY = {
    "regional_bank": ("Financials", "Banks", "Regional Banks"),
    "mortgage_lender": ("Financials", "Banks", "Mortgage Finance"),
    "payments": ("Financials", "Payments", "Payment Processing"),
    "wind_power": ("Utilities", "Renewable Power", "Wind Power"),
    "solar_power": ("Utilities", "Renewable Power", "Solar Power"),
    "oil_gas_drilling": ("Energy", "Oil & Gas", "Contract Drilling"),
    "lab_diagnostics": ("Health Care", "Diagnostics", "Laboratory Diagnostics"),
    "orthopedic_devices": ("Health Care", "Medical Devices", "Orthopedic Devices"),
    "hr_software": ("Technology", "Software", "HR & Payroll Software"),
    "cybersecurity": ("Technology", "Software", "Cybersecurity Software"),
    "container_shipping": ("Industrials", "Transportation", "Container Shipping"),
    "trucking": ("Industrials", "Transportation", "Trucking"),
    "quick_service_restaurants": ("Consumer Discretionary", "Restaurants", "Quick Service Restaurants"),
}

BOILERPLATE = (
    "The company is committed to long-term value creation, operational excellence and disciplined capital "
    "allocation. Its experienced management team focuses on customers, employees and shareholders, and it "
    "continues to invest in growth, innovation and sustainability across its markets."
)

# (ticker, name, country, business, tags, description, dataset-label override or None)
COMPANIES: list[tuple[str, str, str, str, tuple[str, ...], str, str | None]] = [
    # --- regional banks
    (
        "RBNA",
        "Harbor State Bank",
        "US",
        "regional_bank",
        (),
        "Harbor State Bank is a regional bank based in the United States that takes deposits from households and "
        "small businesses and lends them out as commercial loans, home mortgages and lines of credit through a "
        "network of local branches.",
        None,
    ),
    (
        "RBNB",
        "Midvale Bancorp",
        "US",
        "regional_bank",
        ("paraphrase",),
        "Midvale Bancorp runs a community lending franchise: checking and savings customers fund the balance "
        "sheet, which finances local companies, farms and homebuyers. Most income is net interest margin.",
        None,
    ),
    (
        "RBNC",
        "Thames County Bank",
        "GB",
        "regional_bank",
        ("cross_country",),
        "Thames County Bank, based in the United Kingdom, is a regional bank serving retail savers and small "
        "firms with current accounts, deposits, business loans and residential mortgages through local branches.",
        None,
    ),
    (
        "RBND",
        "Rheinland Volksbank",
        "DE",
        "regional_bank",
        ("cross_country", "geo_trap"),
        "Rheinland Volksbank is based in Germany and operates as a cooperative regional bank, collecting deposits "
        "from local members and providing loans to small and medium-sized businesses and households.",
        None,
    ),
    (
        "RBNE",
        "Prairie Trust Financial",
        "US",
        "regional_bank",
        ("boilerplate",),
        BOILERPLATE + " Prairie Trust Financial operates a regional bank that gathers deposits and makes "
        "commercial and consumer loans.",
        None,
    ),
    # --- mortgage lenders
    (
        "MTGA",
        "Keystone Home Loans",
        "US",
        "mortgage_lender",
        (),
        "Keystone Home Loans originates and services residential mortgages in the United States, funding loans "
        "through warehouse lines and selling them into mortgage-backed securities while keeping servicing rights.",
        None,
    ),
    (
        "MTGB",
        "Brightdoor Mortgage",
        "US",
        "mortgage_lender",
        ("paraphrase",),
        "Brightdoor Mortgage helps families buy or refinance houses: it underwrites home loans online, packages "
        "them for government-sponsored agencies and earns fees from collecting borrower payments.",
        None,
    ),
    (
        "MTGC",
        "Maple Residential Lending",
        "CA",
        "mortgage_lender",
        ("cross_country",),
        "Maple Residential Lending, based in Canada, originates residential mortgages through brokers and sells "
        "insured mortgages into securitization programs, retaining servicing fees.",
        None,
    ),
    (
        "MTGD",
        "Northgate Mortgage Trust",
        "US",
        "mortgage_lender",
        ("mislabelled",),
        "Northgate Mortgage Trust originates residential mortgage loans for homebuyers and refinancing borrowers "
        "and earns servicing income on the loans it sells to investors.",
        "Trucking",
    ),
    # --- payments
    (
        "PAYA",
        "Swiftpay Networks",
        "US",
        "payments",
        (),
        "Swiftpay Networks processes card payments for merchants, providing point-of-sale terminals, online "
        "checkout and settlement, and earns a fee on each transaction it processes.",
        None,
    ),
    (
        "PAYB",
        "Ledgerline",
        "US",
        "payments",
        ("paraphrase",),
        "Ledgerline lets shops and websites accept money from shoppers: its gateway authorizes purchases, moves "
        "funds to sellers' accounts and charges a small percentage of every sale.",
        None,
    ),
    (
        "PAYC",
        "Euroclear Pay",
        "DE",
        "payments",
        ("cross_country", "geo_trap"),
        "Euroclear Pay is based in Germany and provides payment processing for European merchants, including "
        "card acquiring, online checkout and settlement of transactions.",
        None,
    ),
    (
        "PAYD",
        "Tokai Payment Systems",
        "JP",
        "payments",
        ("cross_country",),
        "Tokai Payment Systems, based in Japan, runs a merchant acquiring business that processes credit card and "
        "QR code payments for retailers and charges transaction fees.",
        None,
    ),
    (
        "PAYE",
        "Coinbridge Merchant Services",
        "US",
        "payments",
        ("boilerplate",),
        BOILERPLATE + " Coinbridge Merchant Services processes card transactions for small merchants.",
        None,
    ),
    # --- wind power
    (
        "WNDA",
        "Gale Ridge Energy",
        "US",
        "wind_power",
        (),
        "Gale Ridge Energy develops, owns and operates onshore wind farms in the United States and sells the "
        "electricity under long-term power purchase agreements with utilities.",
        None,
    ),
    (
        "WNDB",
        "Northsea Turbine Holdings",
        "GB",
        "wind_power",
        ("cross_country",),
        "Northsea Turbine Holdings, based in the United Kingdom, operates offshore wind farms and sells "
        "renewable electricity to the grid under contracts for difference.",
        None,
    ),
    (
        "WNDC",
        "Highplains Renewables",
        "US",
        "wind_power",
        ("paraphrase",),
        "Highplains Renewables builds fleets of turbines on leased ranch land and earns revenue by delivering "
        "clean generation to grid operators under multi-decade offtake contracts.",
        None,
    ),
    (
        "WNDD",
        "Brisa Power",
        "DE",
        "wind_power",
        ("cross_country", "geo_trap", "mislabelled"),
        "Brisa Power is based in Germany and owns onshore wind parks that generate renewable electricity sold "
        "under feed-in tariffs and power purchase agreements.",
        "Regional Banks",
    ),
    (
        "WNDE",
        "Westerly Wind Partners",
        "US",
        "wind_power",
        (),
        "Westerly Wind Partners owns wind farms and sells the electricity they generate to utilities through "
        "long-term power purchase agreements.",
        None,
    ),
    # --- solar power
    (
        "SOLA",
        "Sunmesa Power",
        "US",
        "solar_power",
        (),
        "Sunmesa Power develops and operates utility-scale solar farms in the United States and sells the "
        "electricity under long-term power purchase agreements.",
        None,
    ),
    (
        "SOLB",
        "Photon Fields",
        "US",
        "solar_power",
        ("paraphrase",),
        "Photon Fields installs photovoltaic panels across desert acreage and earns contracted revenue by "
        "supplying daytime generation and battery-shifted output to grid operators.",
        None,
    ),
    (
        "SOLC",
        "Iberia Sol Renovables",
        "ES",
        "solar_power",
        ("cross_country",),
        "Iberia Sol Renovables, based in Spain, owns solar photovoltaic plants and sells the electricity under "
        "power purchase agreements and in the wholesale market.",
        None,
    ),
    (
        "SOLD",
        "Rooftop Grid Co",
        "US",
        "solar_power",
        ("boilerplate",),
        BOILERPLATE + " Rooftop Grid Co owns solar installations and sells the electricity they produce.",
        None,
    ),
    # --- oil and gas drilling
    (
        "DRLA",
        "Permian Rig Services",
        "US",
        "oil_gas_drilling",
        (),
        "Permian Rig Services provides contract drilling rigs and crews to oil and gas producers in the United "
        "States, earning day rates for drilling horizontal wells.",
        None,
    ),
    (
        "DRLB",
        "Deepwater Bore",
        "GB",
        "oil_gas_drilling",
        ("cross_country",),
        "Deepwater Bore, based in the United Kingdom, operates offshore drilling rigs that it charters to oil "
        "companies on day-rate contracts.",
        None,
    ),
    (
        "DRLC",
        "Basin Wellworks",
        "CA",
        "oil_gas_drilling",
        ("paraphrase", "cross_country"),
        "Basin Wellworks, based in Canada, leases its fleet of land rigs and crews to exploration companies that "
        "need new hydrocarbon wells, billing per day of operation.",
        None,
    ),
    (
        "DRLD",
        "Gulf Coast Drilling",
        "US",
        "oil_gas_drilling",
        (),
        "Gulf Coast Drilling owns jackup and land drilling rigs and contracts them to oil and gas producers at "
        "day rates.",
        None,
    ),
    # --- laboratory diagnostics
    (
        "LABA",
        "Clearpath Diagnostics",
        "US",
        "lab_diagnostics",
        (),
        "Clearpath Diagnostics makes blood testing analysers, reagents and point-of-care test kits for hospital "
        "and reference laboratories, with recurring revenue from consumables.",
        None,
    ),
    (
        "LABB",
        "Assaygen",
        "US",
        "lab_diagnostics",
        ("paraphrase",),
        "Assaygen places instruments in clinical labs and then sells the chemistry cartridges those machines "
        "consume to measure patient samples for disease markers.",
        None,
    ),
    (
        "LABC",
        "Rhine Labor Diagnostik",
        "DE",
        "lab_diagnostics",
        ("cross_country", "geo_trap"),
        "Rhine Labor Diagnostik is based in Germany and supplies laboratory analysers, reagents and test kits to "
        "hospitals and clinical laboratories.",
        None,
    ),
    (
        "LABD",
        "Kanto Medical Testing",
        "JP",
        "lab_diagnostics",
        ("cross_country",),
        "Kanto Medical Testing, based in Japan, manufactures diagnostic analysers and reagents for blood and "
        "urine testing in hospital laboratories.",
        None,
    ),
    (
        "LABE",
        "Veritas Assay Group",
        "US",
        "lab_diagnostics",
        ("mislabelled",),
        "Veritas Assay Group sells diagnostic analysers, reagents and test consumables to hospital laboratories.",
        "Payment Processing",
    ),
    # --- orthopedic devices
    (
        "ORTA",
        "Stridewell Orthopedics",
        "US",
        "orthopedic_devices",
        (),
        "Stridewell Orthopedics designs and sells hip and knee replacement implants and surgical instruments to "
        "hospitals and orthopedic surgeons.",
        None,
    ),
    (
        "ORTB",
        "Jointcraft Medical",
        "US",
        "orthopedic_devices",
        ("paraphrase",),
        "Jointcraft Medical makes artificial joints and the tools surgeons use to fit them, helping patients with "
        "arthritis walk again after replacement procedures.",
        None,
    ),
    (
        "ORTC",
        "Alpine Spine Systems",
        "CH",
        "orthopedic_devices",
        ("cross_country",),
        "Alpine Spine Systems, based in Switzerland, develops spinal implants, bone screws and orthopedic "
        "surgical instruments sold to hospitals.",
        None,
    ),
    (
        "ORTD",
        "Bonebridge Implants",
        "US",
        "orthopedic_devices",
        ("boilerplate",),
        BOILERPLATE + " Bonebridge Implants sells knee and hip implants to orthopedic surgeons.",
        None,
    ),
    # --- HR and payroll software
    (
        "HRSA",
        "Paydeck Software",
        "US",
        "hr_software",
        (),
        "Paydeck Software provides cloud payroll and human resources software that lets employers run payroll, "
        "manage benefits and track employee time, sold as a monthly subscription per employee.",
        None,
    ),
    (
        "HRSB",
        "Crewbase",
        "US",
        "hr_software",
        ("paraphrase",),
        "Crewbase gives companies one online place to pay staff, file wage taxes, onboard new hires and handle "
        "workforce records, charging a subscription for each worker.",
        None,
    ),
    (
        "HRSC",
        "Peoplegrid",
        "GB",
        "hr_software",
        ("cross_country",),
        "Peoplegrid, based in the United Kingdom, sells cloud human resources and payroll software to "
        "mid-sized employers on a subscription basis.",
        None,
    ),
    (
        "HRSD",
        "Talentloop",
        "DE",
        "hr_software",
        ("cross_country", "geo_trap"),
        "Talentloop is based in Germany and offers subscription software for payroll, time tracking and human "
        "resources administration.",
        None,
    ),
    (
        "HRSE",
        "Staffline Cloud",
        "US",
        "hr_software",
        ("mislabelled",),
        "Staffline Cloud sells payroll processing and HR management software to small businesses as a "
        "subscription service.",
        "Container Shipping",
    ),
    # --- cybersecurity
    (
        "CYBA",
        "Bastion Security",
        "US",
        "cybersecurity",
        (),
        "Bastion Security sells endpoint protection and threat detection software that stops malware and "
        "ransomware on corporate laptops and servers, on an annual subscription.",
        None,
    ),
    (
        "CYBB",
        "Nightwatch Labs",
        "US",
        "cybersecurity",
        ("paraphrase",),
        "Nightwatch Labs monitors corporate networks around the clock, spotting intruders and shutting down "
        "attacks before data is stolen, for customers paying yearly licences.",
        None,
    ),
    (
        "CYBC",
        "Shieldware",
        "IL",
        "cybersecurity",
        ("cross_country",),
        "Shieldware, based in Israel, develops firewall and cloud security software that protects enterprise "
        "networks from cyberattacks, sold by subscription.",
        None,
    ),
    (
        "CYBD",
        "Cipherline",
        "US",
        "cybersecurity",
        ("boilerplate",),
        BOILERPLATE + " Cipherline sells cybersecurity software that detects and blocks threats.",
        None,
    ),
    # --- container shipping
    (
        "SHPA",
        "Bluewater Container Lines",
        "US",
        "container_shipping",
        (),
        "Bluewater Container Lines operates a fleet of container ships carrying cargo between Asian and North "
        "American ports, earning freight rates per container.",
        None,
    ),
    (
        "SHPB",
        "Hanseatic Box Shipping",
        "DE",
        "container_shipping",
        ("cross_country", "geo_trap"),
        "Hanseatic Box Shipping is based in Germany and runs container vessels on liner routes between Europe "
        "and Asia, charging freight rates for each container moved.",
        None,
    ),
    (
        "SHPC",
        "Oceanic Freight Carriers",
        "SG",
        "container_shipping",
        ("paraphrase", "cross_country"),
        "Oceanic Freight Carriers, based in Singapore, moves exporters' goods across the Pacific in standard "
        "steel boxes aboard its own vessels, billing per box and voyage.",
        None,
    ),
    (
        "SHPD",
        "Tidewater Liner Co",
        "US",
        "container_shipping",
        (),
        "Tidewater Liner Co owns container ships and charters vessels to carry containerized cargo on "
        "transpacific routes.",
        None,
    ),
    # --- trucking
    (
        "TRKA",
        "Interstate Haulers",
        "US",
        "trucking",
        (),
        "Interstate Haulers provides truckload freight transportation across the United States with a fleet of "
        "tractors and trailers, earning revenue per mile hauled.",
        None,
    ),
    (
        "TRKB",
        "Roadrunner Logistics",
        "US",
        "trucking",
        ("paraphrase",),
        "Roadrunner Logistics moves retailers' pallets between warehouses and stores using its own big rigs and "
        "drivers, billing shippers by the load.",
        None,
    ),
    (
        "TRKC",
        "Northern Freightways",
        "CA",
        "trucking",
        ("cross_country",),
        "Northern Freightways, based in Canada, runs less-than-truckload and truckload trucking services with "
        "a fleet of tractors and trailers.",
        None,
    ),
    (
        "TRKD",
        "Autobahn Spedition",
        "DE",
        "trucking",
        ("cross_country", "geo_trap"),
        "Autobahn Spedition is based in Germany and operates road freight trucking services for manufacturers "
        "and retailers across Europe.",
        None,
    ),
    # --- quick-service restaurants
    (
        "QSRA",
        "Burgerbarn",
        "US",
        "quick_service_restaurants",
        (),
        "Burgerbarn operates and franchises quick-service restaurants serving burgers, fries and shakes, earning "
        "royalties from franchisees and sales from company-owned restaurants.",
        None,
    ),
    (
        "QSRB",
        "Tacoloco",
        "US",
        "quick_service_restaurants",
        ("paraphrase",),
        "Tacoloco runs fast counter-service eateries selling tacos and burritos, most of them owned by local "
        "operators who pay it a share of their sales.",
        None,
    ),
    (
        "QSRC",
        "Maple Fry House",
        "CA",
        "quick_service_restaurants",
        ("cross_country",),
        "Maple Fry House, based in Canada, franchises quick-service restaurants serving fries, burgers and coffee.",
        None,
    ),
    (
        "QSRD",
        "Wurst Express",
        "DE",
        "quick_service_restaurants",
        ("cross_country", "geo_trap", "boilerplate"),
        BOILERPLATE + " Wurst Express is based in Germany and franchises quick-service restaurants serving "
        "sausages and fries.",
        None,
    ),
]

# A second listing of Gale Ridge Energy under an unrelated ticker, with different financials: the same
# company, so it must be skipped as a near-duplicate, never returned as a peer. Excluded from scoring.
DUPLICATES = {"WNDX": "WNDA"}


def _record(i: int, ticker: str, name: str, country: str, business: str, description: str, label: str | None):
    sector, industry, sub = TAXONOMY[business]
    if label is not None:  # a wrong dataset label: take the whole classification from the labelled business
        business_of_label = next(b for b, t in TAXONOMY.items() if t[2] == label)
        sector, industry, sub = TAXONOMY[business_of_label]
    return {
        "id": f"ev{i:03d}",
        "ticker": ticker,
        "name": name,
        "description": description,
        "sector": sector,
        "industry": industry,
        "sub_industry": sub,
        "country": country,
        "price_currency": "USD",
        "reporting_currency": "USD",
        "units": "millions",
        "fiscal_year_end": "12-31",
        "price": 10.0 + i,
        "price_date": "2026-10-01",
        "shares_outstanding": 50.0 + 3 * i,
        "total_debt": 100.0 + 7 * i,
        "cash": 20.0 + i,
        "revenue": 400.0 + 25 * i,
        "ebitda": 60.0 + 4 * i,
        "net_income": 20.0 + 2 * i,
    }


def relevance(a: str, b: str) -> int:
    sa, ia, _ = TAXONOMY[a]
    sb, ib, _ = TAXONOMY[b]
    if a == b:
        return 3
    if ia == ib:
        return 2
    if sa == sb:
        return 1
    return 0


def build(out: Path = HERE) -> None:
    records = [_record(i, t, n, c, b, d, lab) for i, (t, n, c, b, _, d, lab) in enumerate(COMPANIES)]
    by_ticker = {t: (c, b, d) for t, _, c, b, _, d, _ in COMPANIES}
    for dup, original in DUPLICATES.items():
        country, business, description = by_ticker[original]
        rec = _record(len(records), dup, "Gale Ridge Energy Holdings", country, business, description, None)
        rec["revenue"], rec["net_income"] = 9999.0, 1.0
        records.append(rec)

    keys = {t: f"{c}:{t}" for t, _, c, *_ in COMPANIES}
    business = {keys[t]: b for t, _, _, b, *_ in COMPANIES}
    tags = {keys[t]: list(tg) for t, _, _, _, tg, *_ in COMPANIES}

    # 50/50 split. Within each business the halves alternate (so both cover every business); ties go to
    # the half with fewer companies of the same hard-case tags, then to the smaller half, so the tags are
    # spread evenly too. Decided before held-out was ever scored.
    halves: dict[str, list[str]] = {"dev": [], "held_out": []}
    tag_count = {
        h: {t: 0 for t in ("paraphrase", "cross_country", "mislabelled", "boilerplate", "geo_trap")} for h in halves
    }
    for b in TAXONOMY:
        members = sorted(k for k, v in business.items() if v == b)
        in_business = {h: 0 for h in halves}
        for key in members:
            half = min(
                halves,
                key=lambda h: (in_business[h], sum(tag_count[h][t] for t in tags[key]), len(halves[h]), h),
            )
            halves[half].append(key)
            in_business[half] += 1
            for t in tags[key]:
                tag_count[half][t] += 1
    dev, held_out = halves["dev"], halves["held_out"]

    labels = {
        target: {other: relevance(business[target], business[other]) for other in sorted(business) if other != target}
        for target in sorted(business)
    }
    # A duplicate listing is the same company: it scores as its original, and only once.
    aliases = {f"{by_ticker[orig][0]}:{dup}": keys[orig] for dup, orig in DUPLICATES.items()}
    spec = {
        "_about": "Synthetic retrieval-eval labels. Relevance follows from each company's true business via the "
        "rubric; dataset labels are not used (some are deliberately wrong). See build_fixture.py.",
        "rubric": RUBRIC,
        "relevant_threshold": 3,
        "business": dict(sorted(business.items())),
        "tags": dict(sorted(tags.items())),
        "splits": {"dev": sorted(dev), "held_out": sorted(held_out)},
        "aliases": aliases,
        "labels": labels,
    }
    (out / "companies.json").write_text(json.dumps(records, indent=2) + "\n")
    (out / "fx_rates.json").write_text(json.dumps({"base": "USD", "rates": {"USD": 1.0}}, indent=2) + "\n")
    (out / "labels.json").write_text(json.dumps(spec, indent=2) + "\n")


if __name__ == "__main__":
    build()
