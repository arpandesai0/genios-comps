"""Look-alike-name synthetic retrieval universe for peer-retrieval evaluation.

Run `python build_fixture.py` to (re)write companies.json, fx_rates.json and
labels.json next to this file. Everything is held as Python literals below.

All companies are invented. Real data has invented company names such as
"Irovaiva Air Group" / "Irovaor Fibre Inc" and every description starts with
the company's own name. Here, 14 invented name STEMS (Velor, Quint, Ostra, ...)
are each shared by 5 companies in 5 DIFFERENT businesses and sectors, while the
5 true peers of every business all carry names from different stems. So a
ranker that is drawn to shared name prefixes is pulled toward wrong companies,
and names never help find the true peers.

Labels are derived mechanically from the TAXONOMY below.
"""

from __future__ import annotations

import json
from pathlib import Path

# business id -> (sector, industry, sub_industry)
TAXONOMY: dict[str, tuple[str, str, str]] = {
    "hr_software": ("Information Technology", "Software", "Human Capital Management Software"),
    "semiconductors": ("Information Technology", "Semiconductors", "Analog & Power Semiconductors"),
    "oncology_biotech": ("Health Care", "Pharmaceuticals & Biotechnology", "Oncology Biotechnology"),
    "generic_pharma": ("Health Care", "Pharmaceuticals & Biotechnology", "Generic Pharmaceuticals"),
    "regional_banks": ("Financials", "Banks", "Regional Banks"),
    "pc_insurance": ("Financials", "Insurance", "Property & Casualty Insurance"),
    "airlines": ("Industrials", "Transportation", "Passenger Airlines"),
    "trucking_logistics": ("Industrials", "Transportation", "Trucking & Logistics"),
    "cement": ("Materials", "Construction Materials", "Cement & Aggregates"),
    "paper_packaging": ("Materials", "Containers & Packaging", "Paper & Fibre Packaging"),
    "regulated_electric": ("Utilities", "Electric Utilities", "Regulated Electric Utilities"),
    "packaged_snacks": ("Consumer Staples", "Food & Beverage", "Packaged Snacks"),
    "upstream_oil_gas": ("Energy", "Oil & Gas", "Exploration & Production"),
    "auto_parts": ("Consumer Discretionary", "Automobiles", "Auto Parts & Equipment"),
}

# Name stems (shared leading letters). Every name below starts with one of these
# (the ending differs per company: Velorin, Velorix, Velora, ...). 5 companies per stem,
# each in a different business AND a different sector. Business peers never
# share a stem.
STEMS = [
    "Velor", "Quint", "Ostr", "Karv", "Zephr", "Belm", "Tarix",
    "Lumer", "Dorva", "Halcor", "Pyrel", "Sandor", "Evand", "Fenwi",
]  # fmt: skip

# (business, country, ticker, name, description template)
# {N} = full name (must open the description), {S} = first word of the name.
RAW: list[tuple[str, str, str, str, str]] = [
    # ---- hr_software
    (
        "hr_software", "US", "VLRXP", "Velorin Payroll Systems Inc.",
        "{N} provides cloud software that runs payroll, benefits enrolment, time tracking and recruiting for mid-sized employers. Customers pay an annual subscription per employee, and most use the platform alongside their existing accounting systems.",
    ),
    (
        "hr_software", "GB", "OSTRP", "Ostrel People Cloud plc",
        "{N} sells a web-based people-management platform covering hiring, onboarding, pay runs and performance reviews. Revenue is recurring and billed monthly by headcount, and {S} serves employers based in the United Kingdom with 100 to 3,000 staff.",
    ),
    (
        "hr_software", "DE", "KRVXP", "Karvex Personal AG",
        "{N} develops hosted human resources software for payroll, working-time recording, applicant tracking and employee self-service. Based in Germany, the company licenses its modules to firms across the DACH region on multi-year contracts.",
    ),
    (
        "hr_software", "IN", "DRVXH", "Dorvanix Technologies Ltd.",
        "{N} helps employers manage staff from the first interview to the last working day on a single portal: recruitment, joining formalities, salary disbursement, attendance, leave and appraisals. Clients pay a monthly fee per head, and the product is built around Indian statutory filings.",
    ),
    (
        "hr_software", "AU", "EVNXH", "Evandix Workforce Pty Ltd",
        "{N} offers rostering, leave booking and award-wage calculation tools for employers with large hourly-paid workforces, especially in retail, hospitality and aged care. {S}'s subscriptions are priced per employee, and the tools connect to leading accounting packages.",
    ),
    # ---- semiconductors
    (
        "semiconductors", "US", "QNTXM", "Quintex Microdevices Inc.",
        "{N} designs and sells analog and power management integrated circuits, including voltage regulators, battery chargers and motor drivers, for industrial and automotive equipment. It uses outside foundries and earns most of its revenue from long-lived products chosen in design-in programmes.",
    ),
    (
        "semiconductors", "JP", "ZPHRN", "Zephrin Semiconductor Co., Ltd.",
        "{N} is a fabless chipmaker supplying power semiconductors and mixed-signal chips used in factory automation, electric vehicles and consumer electronics. Customers design its parts into products that stay on the market for many years, and the company sells mainly to Asian manufacturers.",
    ),
    (
        "semiconductors", "DE", "LMRXH", "Lumerix Halbleiter AG",
        "{N} makes silicon power devices such as MOSFETs and IGBTs, together with sensor interface chips, at its own wafer plant. The components switch and regulate electricity inside drives, inverters and vehicles, and {S} sells mainly to European industrial customers.",
    ),
    (
        "semiconductors", "CA", "PYRXS", "Pyrelix Silicon Corp.",
        "{N} creates the small chips that control how electricity flows in machines and gadgets: voltage converters, signal amplifiers and charging controllers. It outsources manufacturing to foundries and sells through distributors to equipment makers across North America.",
    ),
    (
        "semiconductors", "IN", "SNDXS", "Sandorix Semiconductors Ltd.",
        "{N} designs analog integrated circuits, data converters and power management chips for telecom, medical and industrial equipment, working with contract fabs and test houses. Its research team is based in Bengaluru, India, and revenue is driven by design wins.",
    ),
    # ---- oncology_biotech
    (
        "oncology_biotech", "US", "OSTXO", "Ostrix Oncology Inc.",
        "{N} is a clinical-stage biopharmaceutical company developing antibody-drug conjugates for solid tumours. Its lead candidate is in a Phase 2 trial for ovarian cancer, and the company has no approved products or product revenue.",
    ),
    (
        "oncology_biotech", "AU", "ZPHXT", "Zephrax Therapeutics Pty Ltd",
        "{N} develops targeted small-molecule medicines for lung and bowel cancers driven by specific genetic mutations. A pivotal trial of the lead drug is under way in Australia and Asia, and {S} plans to file for approval next year.",
    ),
    (
        "oncology_biotech", "DE", "DRVNB", "Dorvano Biopharma AG",
        "{N} researches cancer immunotherapies, including checkpoint inhibitor combinations and personalised mRNA vaccines, with several candidates in Phase 1 and Phase 2 trials. The German company funds its work through partnerships and equity raises rather than product sales.",
    ),
    (
        "oncology_biotech", "GB", "SNDLB", "Sandorel Biosciences plc",
        "{N} is building living treatments for blood cancers: a patient's own immune cells are re-engineered to find and destroy leukaemia and lymphoma, then returned by infusion. Early studies are enrolling at hospitals in London and Manchester.",
    ),
    (
        "oncology_biotech", "JP", "FNWXP", "Fenwixa Pharma Co., Ltd.",
        "{N} discovers and develops anticancer agents, with a PD-1 combination programme for gastric cancer in late-stage testing and a licensed antibody candidate in earlier studies. The company generates no sales from medicines yet and relies on milestone payments from partners.",
    ),
    # ---- generic_pharma
    (
        "generic_pharma", "IN", "QNTRP", "Quintara Pharmaceuticals Ltd.",
        "{N} manufactures and sells generic medicines, including heart, diabetes and antibiotic tablets and capsules, from regulator-inspected plants in Gujarat. About half of its sales come from exports to the United States and Europe.",
    ),
    (
        "generic_pharma", "US", "KRVNG", "Karvenor Generics Inc.",
        "{N} develops, manufactures and markets generic prescription drugs, holding more than 120 approved abbreviated applications and focusing on complex generics such as inhalers and injectables. Most of its revenue comes from pharmacy wholesalers in the United States.",
    ),
    (
        "generic_pharma", "GB", "BLMRH", "Belmoran Healthcare plc",
        "{N} supplies off-patent medicines to hospitals and pharmacies at low prices. It buys active ingredients in bulk, makes tablets and sterile injections in its own factories, and also distributes products made by others across Britain and Ireland.",
    ),
    (
        "generic_pharma", "CA", "HLCXP", "Halcorex Pharma Inc.",
        "{N} makes lower-cost copies of brand-name drugs, including biosimilars, once their patents expire, and sells them to provincial drug plans and pharmacy chains in Canada. {S}'s growth depends on winning contracts as patents lapse.",
    ),
    (
        "generic_pharma", "JP", "PYRLP", "Pyrelan Pharmaceutical Co., Ltd.",
        "{N} produces generic pharmaceuticals and active ingredients for the Japanese market, supplying hospitals and dispensing pharmacies with affordable versions of established medicines. The company follows government drug-price revisions closely.",
    ),
    # ---- regional_banks
    (
        "regional_banks", "US", "VLRXB", "Velorix Bancorp",
        "{N} is the holding company for a community bank with 84 branches across the Midwest. It takes deposits and makes commercial real estate, farm and small business loans, earning most of its income from net interest margin.",
    ),
    (
        "regional_banks", "GB", "QNTLB", "Quintel Banking Group plc",
        "{N} is a regional lender serving households and local companies through branches in northern England. Lending is mostly residential mortgages and business loans funded by retail savings deposits.",
    ),
    (
        "regional_banks", "DE", "OSTVK", "Ostravia Kreditbank AG",
        "{N} is a commercial bank for medium-sized companies and private clients in western Germany. Its lending consists mainly of mortgages and working-capital credit to family-owned manufacturers, funded by customer deposits.",
    ),
    (
        "regional_banks", "AU", "HLCRB", "Halcora Bank Ltd",
        "{N} offers savings accounts, home loans and business lending to customers in the western half of the country. It funds its mortgage book mostly with local deposits and is the largest locally headquartered bank in its home state.",
    ),
    (
        "regional_banks", "CA", "PYRLO", "Pyrelo Financial Corp.",
        "{N} is a mid-sized lender in western Canada with branches and credit-union partnerships. {S} funds residential mortgages and farm operating loans mainly from retail deposits.",
    ),
    # ---- pc_insurance
    (
        "pc_insurance", "US", "KRVNI", "Karvian Insurance Group",
        "{N} writes commercial property, general liability and workers' compensation insurance through independent agents. It reported a combined ratio of 94% last year and manages catastrophe exposure with a reinsurance programme.",
    ),
    (
        "pc_insurance", "JP", "ZPHRL", "Zephral Fire & Marine Insurance Co., Ltd.",
        "{N} writes fire, marine, motor and personal accident insurance, and is expanding into liability cover for corporate clients overseas. Results depend on typhoon and earthquake claims and on the cost of reinsurance.",
    ),
    (
        "pc_insurance", "GB", "BLMXU", "Belmex Underwriting plc",
        "{N} is a specialty insurer in the Lloyd's market, underwriting marine, aviation and political-risk policies. Earnings swing with large loss events and the pricing of excess-of-loss reinsurance.",
    ),
    (
        "pc_insurance", "AU", "TRXLI", "Tarixel Insurance Holdings Ltd",
        "{N} sells home, car and small-business cover directly to households and through brokers. When storms, floods or bushfires strike, {S} pays out for damage to houses and vehicles.",
    ),
    (
        "pc_insurance", "DE", "EVNDR", "Evandor Versicherung AG",
        "{N} insures vehicles, homes and small companies in northern Germany and also takes on reinsurance business from smaller regional insurers. Profit depends on claims from storms and hail.",
    ),
    # ---- airlines
    (
        "airlines", "US", "QNTRX", "Quintrix Air Group Inc.",
        "{N} operates a hub-and-spoke network of 640 daily departures across North America and the Caribbean. Management guides to a rise in revenue per available seat mile as capacity grows.",
    ),
    (
        "airlines", "IN", "KRVLA", "Karvell Airways Ltd.",
        "{N} is a low-cost carrier flying domestic routes and short international flights with a single-type narrowbody fleet. Revenue comes from ticket sales and ancillary fees such as baggage and seat selection.",
    ),
    (
        "airlines", "AU", "DRVNA", "Dorvane Aviation Ltd",
        "{N} flies people between cities and remote towns, carrying holidaymakers, business travellers and mine workers on jets and propeller planes. Seats are sold online and through travel agents across Australia.",
    ),
    (
        "airlines", "JP", "SNDRA", "Sandoria Air Lines Co., Ltd.",
        "{N} offers scheduled passenger flights between major Japanese cities and several Asian destinations, and operates a cargo subsidiary. Fuel prices and exchange rates drive its margins.",
    ),
    (
        "airlines", "CA", "FNWRL", "Fenwiral Airlines Inc.",
        "{N} is a regional airline serving small Canadian airports and northern communities with turboprop aircraft. Besides scheduled passenger service, it earns income from charter flights for resource companies.",
    ),
    # ---- trucking_logistics
    (
        "trucking_logistics", "US", "OSTRN", "Ostrane Freight Group Inc.",
        "{N} operates 14,000 tractors and 45,000 trailers delivering full-truckload and less-than-truckload shipments. It also offers freight brokerage and dedicated contract carriage.",
    ),
    (
        "trucking_logistics", "DE", "ZPHRV", "Zephrova Logistik AG",
        "{N} transports goods by road across Europe and runs contract warehousing and customs clearance for industrial clients. Its fleet of 3,200 lorries is mostly fitted with telematics.",
    ),
    (
        "trucking_logistics", "GB", "BLMRI", "Belmira Haulage plc",
        "{N} carries pallets and parcels over Britain's roads for manufacturers and retailers, with overnight network hubs and a fleet of vans and heavy goods vehicles.",
    ),
    (
        "trucking_logistics", "CA", "LMRLT", "Lumerel Transport Corp.",
        "{N} moves freight by truck and rail-linked intermodal service across Canada and operates cross-dock terminals and a cold-chain network.",
    ),
    (
        "trucking_logistics", "IN", "EVNDL", "Evandra Logistics Ltd.",
        "{N} provides road freight, warehousing and supply-chain services to Indian manufacturers and retailers, with a pan-India network of truck terminals. A growing share of revenue comes from temperature-controlled deliveries.",
    ),
    # ---- cement
    (
        "cement", "IN", "QNTOC", "Quinto Cement Ltd.",
        "{N} produces cement, ready-mix concrete and aggregates from integrated plants and quarries in southern India. Volumes follow housing and infrastructure spending, and energy costs are the largest expense.",
    ),
    (
        "cement", "US", "ZPHRO", "Zephrio Materials Inc.",
        "{N} manufactures cement and ready-mixed concrete and quarries crushed stone and sand for road and building projects in the American South. Its plants run kilns that burn petroleum coke and coal.",
    ),
    (
        "cement", "DE", "HLCRI", "Halcorin Baustoffe AG",
        "{N} makes cement, concrete and building aggregates at plants in Bavaria and Saxony, supplying construction firms and precast producers. Rising carbon-permit costs are a major earnings headwind.",
    ),
    (
        "cement", "AU", "PYRLK", "Pyrelka Cement Holdings Ltd",
        "{N} grinds limestone into cement and also supplies sand, gravel and premixed concrete to builders in eastern Australia. Its operations include a deepwater import terminal for clinker.",
    ),
    (
        "cement", "JP", "SNDRL", "Sandoral Cement Co., Ltd.",
        "{N} manufactures Portland cement and slag cement and sells concrete aggregates to Japanese construction companies, with a small export business to Southeast Asia.",
    ),
    # ---- paper_packaging
    (
        "paper_packaging", "US", "VLRXA", "Velora Packaging Corp.",
        "{N} manufactures corrugated boxes and folding cartons from recycled paperboard for food, e-commerce and consumer goods companies. It operates 40 converting plants and two paper mills.",
    ),
    (
        "paper_packaging", "GB", "BLMSA", "Belmosa Fibre plc",
        "{N} produces paper-based packaging, including cartons and moulded fibre trays, for supermarkets and food producers across the UK. Recycled fibre is its main raw material.",
    ),
    (
        "paper_packaging", "JP", "TRXON", "Tarixon Paper Co., Ltd.",
        "{N} makes paper and board used to pack consumer products, running paper machines and box-making plants in Japan. Its mills convert waste paper into liner and corrugating medium.",
    ),
    (
        "paper_packaging", "DE", "LMRIN", "Lumerin Verpackung AG",
        "{N} supplies shipping boxes, cartons and protective inserts made from board to German manufacturers and online retailers. Its plants make packaging to customer specifications.",
    ),
    (
        "paper_packaging", "CA", "FNWCO", "Fenwico Containerboard Inc.",
        "{N} produces containerboard from recycled and virgin fibre at mills in Quebec and Ontario, and sells it to box makers. Selling prices move with fibre costs.",
    ),
    # ---- regulated_electric
    (
        "regulated_electric", "US", "VLRXL", "Velorel Power Co.",
        "{N} is a vertically integrated electric utility serving 2.1 million customers across three states. Earnings are driven by growth in rate base, regulated returns set by state commissions and recovery of investment through rate cases.",
    ),
    (
        "regulated_electric", "AU", "TRXLA", "Tarixa Energy Networks Ltd",
        "{N} owns the poles, wires and substations that carry electricity to 1.6 million customers in regional Australia. It does not sell energy itself; retailers pay it network charges set by the regulator.",
    ),
    (
        "regulated_electric", "IN", "LMRAN", "Lumeran Power Ltd.",
        "{N} generates, transmits and sells electricity to households and industry in one of the country's states, under government-approved tariffs. Its fleet includes hydro and thermal stations.",
    ),
    (
        "regulated_electric", "GB", "EVNDE", "Evandel Electricity plc",
        "{N} owns and operates the electricity distribution network across southern England under a licence regulated by Ofgem, delivering power to 3.4 million homes and businesses. Revenue is set by the regulator through a price control.",
    ),
    (
        "regulated_electric", "JP", "FNWRN", "Fenwiron Electric Power Co., Inc.",
        "{N} generates, transmits and sells electricity to residential and industrial customers in its franchise area on Honshu. It runs thermal, hydro and nuclear plants and is subject to tariff regulation.",
    ),
    # ---- packaged_snacks
    (
        "packaged_snacks", "US", "OSTRM", "Ostrimo Foods, Inc.",
        "{N} makes potato chips, tortilla chips, pretzels and popcorn sold through grocery and convenience stores across the United States. It operates a direct-store-delivery network that restocks shelves several times a week.",
    ),
    (
        "packaged_snacks", "JP", "TRXEN", "Tarixen Foods Co., Ltd.",
        "{N} produces rice crackers, seaweed snacks and small confectionery for the domestic market, selling mostly through convenience stores in Japan.",
    ),
    (
        "packaged_snacks", "IN", "DRVNL", "Dorvanel Snacks Ltd.",
        "{N} sells spicy fried and roasted nibbles such as bhujia, chivda and masala peanuts, packed in pouches and sold through neighbourhood shops and modern retail.",
    ),
    (
        "packaged_snacks", "CA", "HLCRN", "Halcorne Foods Corp.",
        "{N} makes crisps, popcorn and nut mixes for supermarkets in Canada and the northern United States, along with private-label snack lines for retailers.",
    ),
    (
        "packaged_snacks", "GB", "FNWKK", "Fenwikk Foods plc",
        "{N} bakes biscuits, crackers and savoury snack bars sold under household brands in supermarkets. Own-label contracts with the large grocers account for roughly a quarter of sales.",
    ),
    # ---- upstream_oil_gas
    (
        "upstream_oil_gas", "US", "BLMTK", "Belmotek Energy Inc.",
        "{N} explores for and produces crude oil and natural gas from shale acreage in Texas, with proved reserves of 480 million barrels of oil equivalent. Production is mostly sold at market prices, so earnings follow commodity prices.",
    ),
    (
        "upstream_oil_gas", "CA", "LMRVA", "Lumerova Resources Corp.",
        "{N} is an independent oil and gas producer with conventional and oil-sands assets in Alberta, producing around 90,000 barrels of oil equivalent per day. Capital spending is directed at drilling new wells.",
    ),
    (
        "upstream_oil_gas", "AU", "DRVAN", "Dorvaan Petroleum Ltd",
        "{N} finds and extracts natural gas and condensate from offshore and onshore fields in Western Australia and sells the output under long-term contracts to LNG plants.",
    ),
    (
        "upstream_oil_gas", "GB", "HLCRS", "Halcoris Exploration plc",
        "{N} holds licences in the North Sea and drills wells to produce oil and gas from mature fields, selling its output at world market prices. A production-sharing arrangement covers one West African block.",
    ),
    (
        "upstream_oil_gas", "IN", "PYRLN", "Pyrelon Oil & Gas Ltd.",
        "{N} explores for and produces crude oil and natural gas from fields in Gujarat and Assam, selling output to state refiners, with gas sold at government-approved prices.",
    ),
    # ---- auto_parts
    (
        "auto_parts", "US", "VLRND", "Velorand Automotive Inc.",
        "{N} is a Tier 1 supplier of transmissions, axles and driveline modules to global automakers for light trucks and SUVs. About 60% of sales come from three customers, with contracts awarded on five to seven year platform cycles.",
    ),
    (
        "auto_parts", "DE", "KRVNA", "Karvenia Fahrzeugteile AG",
        "{N} makes brake discs, steering components and chassis parts for German carmakers and the spare-parts market. Its plants serve car assembly lines on just-in-time schedules.",
    ),
    (
        "auto_parts", "IN", "TRXOA", "Tarixo Auto Components Ltd.",
        "{N} manufactures seats, dashboards, door panels and wiring harnesses for passenger car assemblers, working from plants near vehicle factories in western India.",
    ),
    (
        "auto_parts", "JP", "SNDVO", "Sandorvo Motor Parts Co., Ltd.",
        "{N} produces engine valves, fuel injection components and bearings for domestic automakers, with overseas plants in Thailand and Mexico.",
    ),
    (
        "auto_parts", "GB", "EVNDO", "Evandro Components plc",
        "{N} supplies exhaust systems, suspension components and aftermarket replacement parts to vehicle makers and garages in Britain and Europe.",
    ),
]  # fmt: skip

FISCAL_YE = {"US": "12-31", "CA": "12-31", "GB": "03-31", "DE": "12-31", "JP": "03-31", "AU": "06-30", "IN": "03-31"}
FX = {"USD": 1.0, "GBP": 1.27, "EUR": 1.08, "CAD": 0.73}
SPLIT_DEV, SPLIT_HELD = "dev", "held_out"


def _currency(i: int, country: str) -> str:
    if country == "GB":
        return "GBP" if i % 2 == 0 else "USD"
    if country == "DE":
        return "EUR" if i % 3 == 0 else "USD"
    if country == "CA":
        return "CAD" if i % 2 == 1 else "USD"
    return "USD"


def _record(i: int, country: str, ticker: str, name: str, desc: str, labels: tuple[str, str, str]) -> dict:
    # every numeric field differs per record index, so no two records share
    # issuer-level data (and none can be fused as share classes)
    revenue = round(180 + (i * 53 % 311) * 4.7 + i * 0.3, 1)
    margin = 0.08 + (i * 7 % 13) / 100
    ebitda = round(revenue * margin, 1)
    cur = _currency(i, country)
    return {
        "id": f"ll{i:03d}",
        "ticker": ticker,
        "name": name,
        "description": desc,
        "sector": labels[0],
        "industry": labels[1],
        "sub_industry": labels[2],
        "country": country,
        "price_currency": cur,
        "reporting_currency": cur,
        "units": "millions",
        "fiscal_year_end": FISCAL_YE[country],
        "price_date": "2026-10-01",
        "price": round(8 + (i * 37 % 91) * 0.83 + i * 0.01, 2),
        "shares_outstanding": round(30 + (i * 41 % 113) * 1.7 + i * 0.1, 1),
        "total_debt": round(40 + (i * 29 % 97) * 3.1 + i * 0.2, 1),
        "cash": round(10 + (i * 17 % 59) * 1.9 + i * 0.1, 1),
        "revenue": revenue,
        "ebitda": ebitda,
        "net_income": round(ebitda * (0.3 + (i * 3 % 7) / 20), 1),
    }


def build(out: Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    business: dict[str, str] = {}
    tags: dict[str, list[str]] = {}
    country_of: dict[str, str] = {}
    name_of: dict[str, str] = {}
    order: list[str] = []

    for i, (biz, country, ticker, name, template) in enumerate(RAW):
        assert 3 <= len(ticker) <= 5 and ticker.isupper() and ticker.isalpha(), ticker
        key = f"{country}:{ticker}"
        assert key not in business, f"duplicate key {key}"
        assert template.startswith("{N} "), name
        assert template.count("{N}") == 1 and template.count("{S}") <= 1, name
        short = name.split()[0]
        assert any(short.startswith(s) for s in STEMS), name
        desc = template.replace("{N}", name).replace("{S}", short)
        assert "{" not in desc and desc.startswith(name + " "), desc
        records.append(_record(i, country, ticker, name, desc, TAXONOMY[biz]))
        business[key] = biz
        tags[key] = ["lookalike_name"]
        country_of[key] = country
        name_of[key] = name
        order.append(key)

    # name-family structure: each stem in 4-6 companies, all in different businesses and sectors,
    # and no two companies of the same business share a stem
    def stem_of(key: str) -> str:
        first = name_of[key].split()[0]
        return next(s for s in STEMS if first.startswith(s))

    for s in STEMS:
        members = [k for k in order if stem_of(k) == s]
        assert 4 <= len(members) <= 6, (s, members)
        assert len({business[k] for k in members}) == len(members), s
        assert len({TAXONOMY[business[k]][0] for k in members}) == len(members), s
    for biz in TAXONOMY:
        stems = [stem_of(k) for k in order if business[k] == biz]
        assert len(set(stems)) == len(stems), biz
    # every company's full name is unique
    assert len(set(name_of.values())) == len(order)

    # cross_country: none of the same-business peers sits in the company's own country
    for key in order:
        peers = [k for k in order if k != key and business[k] == business[key]]
        if all(country_of[k] != country_of[key] for k in peers):
            tags[key] = sorted(set(tags[key]) | {"cross_country"})

    # splits: alternate dev/held_out inside each business; flip the starting side per business
    splits: dict[str, list[str]] = {SPLIT_DEV: [], SPLIT_HELD: []}
    for bi, biz in enumerate(TAXONOMY):
        members = sorted(k for k in order if business[k] == biz)
        for pos, key in enumerate(members):
            dev = (pos + bi) % 2 == 0
            splits[SPLIT_DEV if dev else SPLIT_HELD].append(key)
    for v in splits.values():
        v.sort()

    # labels from the taxonomy
    def grade(a: str, b: str) -> int:
        ta, tb = TAXONOMY[business[a]], TAXONOMY[business[b]]
        if business[a] == business[b]:
            return 3
        if ta[:2] == tb[:2]:
            return 2
        if ta[0] == tb[0]:
            return 1
        return 0

    labels = {a: {b: grade(a, b) for b in sorted(order) if b != a} for a in sorted(order)}

    all_keys = [f"{r['country']}:{r['ticker']}" for r in records]
    assert len(set(all_keys)) == len(all_keys)
    fin = [(r["description"], r["total_debt"], r["cash"], r["revenue"], r["ebitda"], r["net_income"]) for r in records]
    assert len(set(fin)) == len(fin)

    label_doc = {
        "_about": (
            "Independent synthetic retrieval evaluation labels, written without reference to any ranker, to test "
            "whether peer retrieval is fooled by LOOK-ALIKE INVENTED COMPANY NAMES. Real data in this format has "
            "invented names such as 'Irovaiva Air Group' and 'Irovaor Fibre Inc', and each description starts with "
            "the company's own name; companies in unrelated businesses whose names share a prefix then look "
            "similar. Here 14 invented name stems are each shared by 5 companies in 5 different businesses and "
            "sectors (with slightly varied endings), while the true peers of every business carry names from "
            "different stems, so names never help find true peers. Each description opens with the company's full "
            "name and may repeat the short name once. All companies are invented and carry correct "
            "sector/industry/sub_industry fields (no mislabels). Graded labels are derived mechanically from the "
            "hand-written taxonomy: 3 same business, 2 same industry but different business, 1 same sector but "
            "different industry, 0 different sector. Tags: every company is 'lookalike_name'; 'cross_country' is "
            "computed (none of its same-business peers is in its own country). Splits alternate dev/held_out "
            "inside every business."
        ),
        "rubric": {
            "3": "same business",
            "2": "same industry, different business",
            "1": "same sector, different industry",
            "0": "different sector",
        },
        "relevant_threshold": 3,
        "business": {k: business[k] for k in sorted(order)},
        "tags": {k: tags[k] for k in sorted(order)},
        "splits": splits,
        "aliases": {},
        "labels": labels,
    }

    def dump(path: Path, obj: object, sort_keys: bool) -> None:
        path.write_text(json.dumps(obj, indent=2, sort_keys=sort_keys, ensure_ascii=False) + "\n", encoding="utf-8")

    dump(out / "companies.json", records, False)
    dump(out / "fx_rates.json", {"base": "USD", "rates": FX}, True)
    dump(out / "labels.json", label_doc, True)


if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
