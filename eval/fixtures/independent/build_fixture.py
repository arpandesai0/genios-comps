"""Independent synthetic retrieval universe for peer-retrieval evaluation.

Run `python build_fixture.py` to (re)write companies.json, fx_rates.json and
labels.json next to this file. Everything is held as Python literals below.
All companies are invented. Labels are derived mechanically from the TRUE
taxonomy (TAXONOMY below), never from the possibly-wrong record labels.
"""

from __future__ import annotations

import json
from pathlib import Path

# business id -> (sector, industry, sub_industry)
TAXONOMY: dict[str, tuple[str, str, str]] = {
    "hr_software": ("Information Technology", "Software", "Human Capital Management Software"),
    "cybersecurity": ("Information Technology", "Software", "Cybersecurity Software"),
    "oncology_biotech": ("Health Care", "Pharmaceuticals & Biotechnology", "Oncology Biotechnology"),
    "generic_pharma": ("Health Care", "Pharmaceuticals & Biotechnology", "Generic Pharmaceuticals"),
    "regional_banks": ("Financials", "Banks", "Regional Banks"),
    "pc_insurance": ("Financials", "Insurance", "Property & Casualty Insurance"),
    "offshore_drilling": ("Energy", "Oil & Gas", "Offshore Drilling"),
    "midstream_pipelines": ("Energy", "Oil & Gas", "Midstream Pipelines"),
    "regulated_electric": ("Utilities", "Electric Utilities", "Regulated Electric Utilities"),
    "renewable_generation": ("Utilities", "Electric Utilities", "Renewable Power Generation"),
    "ev_makers": ("Consumer Discretionary", "Automobiles", "Electric Vehicle Manufacturers"),
    "auto_parts": ("Consumer Discretionary", "Automobiles", "Auto Parts & Equipment"),
    "packaged_snacks": ("Consumer Staples", "Food & Beverage", "Packaged Snacks"),
    "craft_brewers": ("Consumer Staples", "Food & Beverage", "Brewers"),
    "airlines": ("Industrials", "Transportation", "Passenger Airlines"),
    "trucking_logistics": ("Industrials", "Transportation", "Trucking & Logistics"),
    "gold_miners": ("Materials", "Metals & Mining", "Gold Mining"),
    "specialty_chemicals": ("Materials", "Chemicals", "Specialty Chemicals"),
}

GEO = {
    "US": "Headquartered in the United States, the company serves customers throughout America and takes pride in its American roots.",
    "CA": "Headquartered in Toronto, Ontario, the company is proudly Canadian and serves customers across Canada.",
    "GB": "Headquartered in London, United Kingdom, the company is listed on the London Stock Exchange and serves customers across the UK.",
    "DE": "Headquartered in Germany, the company is a German Mittelstand firm with deep roots in the German economy and customers across Europe.",
    "JP": "Headquartered in Tokyo, Japan, the company operates mainly in the Japanese domestic market and serves customers across Japan.",
    "AU": "Headquartered in Sydney, the company is an Australian business serving customers across Australia and New Zealand.",
    "IN": "Headquartered in Mumbai, India, the company serves the Indian market with operations across India.",
}

BOILERPLATE = {
    "BP1": "Our mission is to deliver long-term value to our shareholders, customers and employees through a relentless focus on operational excellence, innovation and integrity. We are a leading provider of innovative solutions, and we believe that our people are our greatest asset.",
    "BP2": "The company is committed to sustainability and responsible corporate citizenship. It has set ambitious environmental, social and governance goals, reports annually against recognised ESG frameworks, and works to reduce its carbon footprint, promote diversity and inclusion, and support the communities in which it operates.",
    "BP3": "Founded on a heritage of trust, the group has grown steadily through disciplined investment and strategic acquisitions. Its experienced management team and strong corporate governance provide a platform for sustainable, profitable growth and the creation of enduring stakeholder value.",
    "BP4": "With a customer-first culture and a commitment to quality, the company strives to exceed expectations in everything it does. It invests in its workforce, upholds the highest ethical standards, and seeks to be recognised as an employer and partner of choice.",
    "BP5": "The company operates in a competitive and rapidly changing environment and is focused on driving growth, improving margins and generating strong cash flow. Its strategy rests on three pillars: operational discipline, customer intimacy and continuous innovation.",
}

# Records whose sector/industry/sub_industry fields are deliberately wrong.
MISLABEL: dict[str, tuple[str, str, str]] = {
    "US:NTCST": ("Industrials", "Commercial Services & Supplies", "Security & Alarm Services"),
    "GB:LKLCT": ("Industrials", "Building Products", "Building Products"),
    "US:VOLTR": ("Industrials", "Electrical Equipment", "Electrical Components & Equipment"),
    "AU:LYMPH": ("Health Care", "Life Sciences Tools & Services", "Laboratory Services"),
    "US:SLRSR": ("Information Technology", "Semiconductors", "Solar Equipment"),
    "IN:GAGAN": ("Consumer Discretionary", "Hotels, Restaurants & Leisure", "Travel Services"),
    "US:GLFCT": ("Industrials", "Transportation Infrastructure", "Marine Ports & Services"),
    "DE:RDRWK": ("Information Technology", "Electronic Equipment & Components", "Electronic Components"),
}

# (business, country, ticker, name, description, manual tags)
# Placeholders {GEO_xx} and {BPn} are expanded below and add the geo_trap /
# boilerplate tags automatically. "cross_country" is computed from the data.
RAW: list[tuple[str, str, str, str, str, list[str]]] = [
    # ---- hr_software
    (
        "hr_software",
        "US",
        "WRKZ",
        "Workaline Systems Inc.",
        "Workaline Systems provides cloud-based human capital management software that handles payroll, benefits administration, time tracking and talent acquisition for mid-sized employers. Customers subscribe annually on a per-employee basis, and most run the platform alongside their existing accounting software.",
        [],
    ),
    (
        "hr_software",
        "CA",
        "PAYLM",
        "Payloom Technologies Ltd.",
        "Payloom sells subscription payroll and workforce management software to small and medium-sized businesses. Its platform automates pay runs, tax filings and employee onboarding, and plugs into the main accounting packages.",
        [],
    ),
    (
        "hr_software",
        "DE",
        "PRSWK",
        "Personalwerk Software AG",
        "{GEO_DE} Personalwerk Software AG develops human resources software covering payroll, time recording, recruiting and employee self-service. The solutions are delivered as a hosted service to companies with 200 to 5,000 employees.",
        [],
    ),
    (
        "hr_software",
        "IN",
        "KAARY",
        "Kaarya Cloud Technologies Ltd.",
        "Kaarya helps employers look after their people from the first interview to the last day of work, all on a single web portal: hiring, joining formalities, salary disbursement, attendance, leave and appraisals. Clients pay a monthly fee per head, and the product has been built around the statutory filings required of Indian employers.",
        ["paraphrase"],
    ),
    (
        "hr_software",
        "US",
        "ROTAB",
        "Rotabase Inc.",
        "Rotabase supplies shift scheduling, holiday booking and wage calculation tools to employers with large hourly-paid workforces, mainly in hospitality, care homes and retail. {BP1}",
        ["paraphrase"],
    ),
    # ---- cybersecurity
    (
        "cybersecurity",
        "US",
        "SNTRX",
        "Sentrix Security Corp.",
        "Sentrix Security offers an endpoint detection and response (EDR) and extended detection and response (XDR) platform that uses behavioural analytics to spot ransomware, credential theft and lateral movement. It sells annual subscriptions through channel partners and managed security service providers (MSSPs).",
        ["jargon"],
    ),
    (
        "cybersecurity",
        "US",
        "VLTGD",
        "Voltguard Networks Inc.",
        "Voltguard Networks sells zero-trust network access and secure web gateway products, together with a cloud SIEM that correlates logs from firewalls, identity providers and SaaS applications. Large enterprises and public sector agencies account for most of its recurring revenue.",
        ["jargon"],
    ),
    (
        "cybersecurity",
        "AU",
        "KRYPT",
        "Kryptara Cyber Ltd",
        "Kryptara protects organisations from hackers, viruses and data theft. It keeps watch over staff laptops, servers and mobile phones around the clock, and its analysts step in when something suspicious turns up. Customers include banks, hospitals and government departments.",
        ["paraphrase"],
    ),
    (
        "cybersecurity",
        "JP",
        "SHLDL",
        "Shieldline Co., Ltd.",
        "Shieldline provides information security products for corporations, including email filtering, vulnerability scanning and endpoint protection software, and runs a security operations centre in Tokyo. {GEO_JP}",
        [],
    ),
    (
        "cybersecurity",
        "US",
        "NTCST",
        "Netcastle Group Inc.",
        "Netcastle Group develops identity and access management (IAM) and privileged access management (PAM) software that controls who can reach sensitive systems and records what they do there. {BP2}",
        ["jargon", "mislabelled"],
    ),
    # ---- oncology_biotech
    (
        "oncology_biotech",
        "US",
        "ONCRX",
        "Oncorex Therapeutics, Inc.",
        "Oncorex is a clinical-stage biopharmaceutical company developing antibody-drug conjugates (ADCs) for solid tumours. Its lead candidate is in a Phase 2 trial in platinum-resistant ovarian cancer, and two further programmes are in IND-enabling studies. The company has no approved products and has not generated product revenue.",
        ["jargon"],
    ),
    (
        "oncology_biotech",
        "US",
        "TMRVX",
        "Tumorvex Biosciences Inc.",
        "Tumorvex is developing targeted small-molecule kinase inhibitors for patients with lung and colorectal cancers that carry specific genetic mutations. A pivotal trial of its lead drug is under way, and a marketing application is planned for next year.",
        [],
    ),
    (
        "oncology_biotech",
        "AU",
        "LYMPH",
        "Lymphara Pty Ltd",
        "Lymphara works on living treatments for blood cancers. It takes a patient's own immune cells, re-programmes them to hunt down leukaemia and lymphoma, and gives them back by infusion. Early-stage studies are enrolling at hospitals in Melbourne and Boston.",
        ["paraphrase", "mislabelled"],
    ),
    (
        "oncology_biotech",
        "DE",
        "HNNGO",
        "Hennig Onkologie AG",
        "{GEO_DE} Hennig Onkologie researches cancer immunotherapies, including checkpoint inhibitor combinations and personalised mRNA vaccines. Several candidates are being tested in Phase 1 and Phase 2 trials in Europe.",
        [],
    ),
    (
        "oncology_biotech",
        "US",
        "GNSEI",
        "Gensei Oncology Inc.",
        "Gensei Oncology discovers anticancer agents, with a PD-1 combination programme for gastric cancer in Phase 2 and a licensed antibody-drug conjugate from a US partner in Phase 1. {BP3}",
        ["jargon"],
    ),
    # ---- generic_pharma
    (
        "generic_pharma",
        "IN",
        "MDGNX",
        "Medigenix Laboratories Ltd.",
        "Medigenix manufactures and sells generic medicines, including cardiovascular, anti-diabetic and antibiotic tablets and capsules, from regulator-inspected plants in Gujarat. About half of its sales come from exports to the United States and Europe.",
        [],
    ),
    (
        "generic_pharma",
        "IN",
        "ANDRP",
        "Andara Pharmaceuticals Ltd.",
        "Andara develops, manufactures and markets generic prescription drugs. It holds more than 120 approved ANDAs, has several Paragraph IV filings pending, and is focusing on complex generics such as inhalers and injectables.",
        ["jargon"],
    ),
    (
        "generic_pharma",
        "GB",
        "CURFD",
        "Curaford Healthcare plc",
        "Curaford supplies off-patent medicines to hospitals and pharmacies in Britain and Ireland at low prices. It buys active ingredients in bulk, produces tablets and sterile injections in its own factories, and also distributes products made by other manufacturers.",
        ["paraphrase"],
    ),
    (
        "generic_pharma",
        "IN",
        "SRYRM",
        "Surya Remedies Ltd.",
        "Surya Remedies is a Hyderabad-based maker of active pharmaceutical ingredients and finished-dose generic formulations. {GEO_IN}",
        [],
    ),
    (
        "generic_pharma",
        "CA",
        "PHBRG",
        "Pharmabridge Canada Inc.",
        "Pharmabridge develops lower-cost versions of brand-name drugs, including biosimilars, once their patents expire, and sells them to provincial drug plans and pharmacy chains. {BP4}",
        [],
    ),
    # ---- regional_banks
    (
        "regional_banks",
        "US",
        "HRBNC",
        "Heartland Ridge Bancorp",
        "{GEO_US} Heartland Ridge Bancorp is the holding company for a community bank with 84 branches in the Midwest. It takes deposits and makes commercial real estate, agricultural and small business loans, and earns most of its income from net interest margin.",
        [],
    ),
    (
        "regional_banks",
        "CA",
        "CMBPF",
        "Cambrian Prairie Financial Corp.",
        "Cambrian Prairie Financial is a regional lender serving households and farms through branches and credit union partnerships. Its loan book is dominated by residential mortgages and farm operating loans funded by retail deposits. {GEO_CA}",
        [],
    ),
    (
        "regional_banks",
        "AU",
        "WSTLY",
        "Westerly Mutual Bank Ltd",
        "Westerly offers savings accounts, home loans and business lending to customers in the western half of the country. It funds its mortgage book mostly with local deposits and is the largest locally headquartered bank in its home state.",
        ["paraphrase"],
    ),
    (
        "regional_banks",
        "DE",
        "RHKRD",
        "Rheinland Kreditbank AG",
        "Rheinland Kreditbank AG is a regional commercial bank for medium-sized companies and private clients. Lending consists mainly of mortgages and working-capital credit to family-owned manufacturers. {GEO_DE}",
        [],
    ),
    (
        "regional_banks",
        "JP",
        "SHKCH",
        "Shikoku Chuo Bank, Ltd.",
        "Shikoku Chuo Bank provides ordinary deposits, loans and remittance services to individuals and small enterprises on the island of Shikoku, and manages a portfolio of local government bonds.",
        ["paraphrase"],
    ),
    # ---- pc_insurance
    (
        "pc_insurance",
        "US",
        "AEGRN",
        "Aegerton Insurance Group",
        "Aegerton writes commercial property, general liability and workers' compensation insurance through independent agents. It reported a combined ratio of 94.1% last year and manages catastrophe exposure through an extensive reinsurance programme.",
        ["jargon"],
    ),
    (
        "pc_insurance",
        "GB",
        "SAFHB",
        "Safeharbour Underwriting plc",
        "Safeharbour is a specialty insurer operating in the Lloyd's market, underwriting marine, aviation and political-risk policies. Its results are sensitive to large loss events and to the pricing of excess-of-loss reinsurance treaties.",
        ["jargon"],
    ),
    (
        "pc_insurance",
        "AU",
        "CSSWR",
        "Cassowary Insurance Holdings Ltd",
        "{GEO_AU} Cassowary sells home, motor and small-business cover directly to households and through brokers. When storms, floods or bushfires strike, it pays out for damage to people's houses and cars.",
        ["paraphrase"],
    ),
    (
        "pc_insurance",
        "JP",
        "HKTFM",
        "Hokuto Fire & Marine Insurance Co., Ltd.",
        "Hokuto Fire & Marine writes fire, marine, automobile and personal accident insurance, and has been expanding into liability products for corporate clients overseas. {BP5}",
        [],
    ),
    (
        "pc_insurance",
        "DE",
        "NRDHF",
        "Nordhafen Versicherung AG",
        "Nordhafen Versicherung insures vehicles, homes and small companies in the north and also takes on reinsurance business from smaller regional insurers.",
        [],
    ),
    # ---- offshore_drilling
    (
        "offshore_drilling",
        "GB",
        "ABYSL",
        "Abyssal Drilling plc",
        "Abyssal Drilling owns and operates a fleet of ultra-deepwater drillships and harsh-environment semisubmersibles contracted to oil majors in the Gulf of Mexico, West Africa and Brazil. Revenue depends on contract dayrates and rig utilisation, and the company reports a contract backlog of roughly $3 billion.",
        ["jargon"],
    ),
    (
        "offshore_drilling",
        "GB",
        "NRTHR",
        "Northsea Rigs plc",
        "Northsea Rigs provides jackup drilling rigs and well services in the North Sea and Middle East. Fleet utilisation has recovered to 92%, and two rigs have recently secured multi-year contract extensions at higher dayrates.",
        ["jargon"],
    ),
    (
        "offshore_drilling",
        "AU",
        "TMRDR",
        "Timor Offshore Drilling Ltd",
        "Timor Offshore Drilling hires out floating platforms that bore wells into the seabed for energy companies working in Asia-Pacific waters. Contracts typically run for one to three years and include the crew and maintenance.",
        ["paraphrase"],
    ),
    (
        "offshore_drilling",
        "JP",
        "KAIYO",
        "Kaiyo Drilling Co., Ltd.",
        "Kaiyo Drilling owns six jack-up rigs working off the coasts of Southeast Asia and India under term contracts with national oil companies. {BP2}",
        [],
    ),
    (
        "offshore_drilling",
        "IN",
        "MHNDR",
        "Mahanadi Offshore Services Ltd.",
        "Mahanadi Offshore Services operates drilling rigs and offshore support vessels for oil and gas explorers. {GEO_IN}",
        [],
    ),
    # ---- midstream_pipelines
    (
        "midstream_pipelines",
        "US",
        "TRNSP",
        "Transprairie Pipelines Inc.",
        "Transprairie owns natural gas gathering and processing plants and long-haul pipelines moving gas and natural gas liquids (NGLs) from the Montney basin to market hubs and export terminals. About 90% of its EBITDA is derived from fee-based, take-or-pay contracts.",
        ["jargon"],
    ),
    (
        "midstream_pipelines",
        "US",
        "PRMDN",
        "Permian Midstream Partners LP",
        "Permian Midstream Partners is a master limited partnership that gathers, compresses and transports crude oil and produced water in West Texas and New Mexico. Distributions to unitholders are supported by minimum volume commitments.",
        ["jargon"],
    ),
    (
        "midstream_pipelines",
        "US",
        "GLFCT",
        "Gulf Coast Terminals Inc.",
        "Gulf Coast Terminals runs storage tanks, marine docks and short pipelines that move refined fuels and chemicals around Houston and Louisiana. It earns rental fees for tank capacity rather than taking ownership of the product.",
        ["paraphrase", "mislabelled"],
    ),
    (
        "midstream_pipelines",
        "AU",
        "PLBGT",
        "Pilbara Gas Transmission Ltd",
        "{GEO_AU} Pilbara Gas Transmission owns and operates high-pressure gas transmission pipelines linking gasfields to mines, power stations and LNG plants under long-term capacity contracts.",
        [],
    ),
    (
        "midstream_pipelines",
        "DE",
        "NRDLT",
        "Nordleitung Pipeline GmbH",
        "Nordleitung operates crude oil and gas pipelines and underground gas storage caverns, transporting energy on behalf of traders and utilities. {BP3}",
        [],
    ),
    # ---- regulated_electric
    (
        "regulated_electric",
        "US",
        "CNSLV",
        "Consolidated Valley Power Co.",
        "Consolidated Valley Power is a vertically integrated electric utility serving 2.1 million customers across three states. Earnings are driven by growth in rate base, authorised returns on equity set by state commissions, and recovery of capital spending through rate cases.",
        ["jargon"],
    ),
    (
        "regulated_electric",
        "GB",
        "WSSXG",
        "Wessex Grid Holdings plc",
        "{GEO_GB} Wessex Grid Holdings owns and operates the electricity distribution network across the south under a licence regulated by Ofgem, delivering power to 3.4 million homes and businesses. Revenue is set by the regulator through a price control formula.",
        ["jargon"],
    ),
    (
        "regulated_electric",
        "JP",
        "TOSAN",
        "Tosan Electric Power Co., Inc.",
        "Tosan Electric Power generates, transmits and sells electricity to residential and industrial customers in its franchise area on Honshu. It operates thermal, hydro and nuclear plants and is subject to tariff regulation. {GEO_JP}",
        [],
    ),
    (
        "regulated_electric",
        "CA",
        "NTHLT",
        "Northern Lights Electric Corp.",
        "Northern Lights Electric sends power along its lines to farms, homes and businesses across a large rural province, and charges rates that a government board approves. Most of the electricity it delivers comes from its own dams.",
        ["paraphrase"],
    ),
    (
        "regulated_electric",
        "AU",
        "SXPDL",
        "Southern Cross Power Distribution Ltd",
        "Southern Cross Power Distribution owns the poles, wires and substations that carry electricity to 1.6 million customers in regional areas. It does not sell energy itself; retailers pay it network charges set by the regulator. {BP4}",
        [],
    ),
    # ---- renewable_generation
    (
        "renewable_generation",
        "US",
        "SLRSR",
        "Solaris Ridge Energy Inc.",
        "Solaris Ridge develops, owns and operates utility-scale solar farms and battery storage projects, selling power under long-term power purchase agreements (PPAs) to utilities and corporate buyers. It has 4.5 GW of contracted capacity and a pipeline of 11 GW.",
        ["jargon", "mislabelled"],
    ),
    (
        "renewable_generation",
        "DE",
        "WNDKR",
        "Windkraft Nord AG",
        "{GEO_DE} Windkraft Nord builds and operates onshore and offshore wind parks. Revenue comes from feed-in tariffs and market-priced electricity sales.",
        [],
    ),
    (
        "renewable_generation",
        "IN",
        "SRYVN",
        "Suryavan Renewables Ltd.",
        "Suryavan Renewables is one of the country's largest independent producers of green electricity, with solar parks and wind farms selling output to state distribution companies under 25-year contracts.",
        [],
    ),
    (
        "renewable_generation",
        "AU",
        "TSMHW",
        "Tasman Hydro and Wind Ltd",
        "Tasman harnesses water, wind and sunshine to make clean power. It owns dams and turbines on the island state and wind turbines on the mainland, and sells what it generates to the national grid market and to large industrial buyers.",
        ["paraphrase"],
    ),
    (
        "renewable_generation",
        "US",
        "BORRN",
        "Boreal Renewables Corp.",
        "Boreal Renewables owns run-of-river hydroelectric stations and wind farms with a combined capacity of 1.9 GW. {BP1}",
        [],
    ),
    # ---- ev_makers
    (
        "ev_makers",
        "US",
        "VOLTR",
        "Voltera Motors Inc.",
        "Voltera Motors designs and builds battery-electric sedans and SUVs at its factory in Nevada, selling directly to consumers online. Deliveries reached 310,000 vehicles last year, and the company is building its own network of fast chargers.",
        ["mislabelled"],
    ),
    (
        "ev_makers",
        "JP",
        "ZNKMT",
        "Zenko Motor Co., Ltd.",
        "Zenko Motor makes compact electric cars and battery packs for domestic and Southeast Asian customers, and is developing a solid-state battery for launch later this decade.",
        [],
    ),
    (
        "ev_makers",
        "GB",
        "MRLWE",
        "Marlowe Electric Vehicles plc",
        "Marlowe builds zero-emission luxury saloons and sports cars by hand at its factory in the English Midlands. Each car carries a battery pack rated for 450 miles of range, and order books are full for two years.",
        ["paraphrase"],
    ),
    (
        "ev_makers",
        "IN",
        "TRNGM",
        "Tarang Mobility Ltd.",
        "Tarang Mobility produces electric three-wheelers, scooters and small passenger cars for crowded cities and operates battery-swapping stations. {GEO_IN}",
        [],
    ),
    (
        "ev_makers",
        "DE",
        "STRMW",
        "Stromwerk Automobile AG",
        "Stromwerk Automobile assembles premium battery-electric vehicles and develops its own 800-volt platform with fast-charging capability. {BP5}",
        [],
    ),
    # ---- auto_parts
    (
        "auto_parts",
        "US",
        "DRVTC",
        "Drivetrain Components Corp.",
        "Drivetrain Components is a Tier 1 supplier of transmissions, axles and driveline modules to global OEMs for light trucks and SUVs. About 60% of sales come from three customers, and contracts are awarded on platform life cycles of five to seven years.",
        ["jargon"],
    ),
    (
        "auto_parts",
        "DE",
        "RDRWK",
        "Radarwerk Automotive GmbH",
        "Radarwerk develops radar, camera and ultrasonic sensors and the control software behind ADAS functions such as adaptive cruise control and automatic emergency braking. Series production is ramping on several OEM platforms.",
        ["jargon", "mislabelled"],
    ),
    (
        "auto_parts",
        "CA",
        "STPWL",
        "Stopwell Brake Systems Inc.",
        "Stopwell manufactures brake pads, rotors and calipers for new vehicles and the aftermarket from plants in Ontario and Michigan. The aftermarket business is sold through distributors and retail chains.",
        [],
    ),
    (
        "auto_parts",
        "JP",
        "NGYPP",
        "Nagoya Precision Parts Co., Ltd.",
        "Nagoya Precision Parts manufactures engine valves, fuel injection components and bearings for domestic automakers, with overseas plants in Thailand and Mexico. {GEO_JP}",
        [],
    ),
    (
        "auto_parts",
        "IN",
        "RTHAI",
        "Rathi Auto Interiors Ltd.",
        "Rathi Auto Interiors makes the things inside a car that passengers touch: seats, dashboards, door panels and carpets. It supplies vehicle assemblers. {BP2}",
        ["paraphrase"],
    ),
    # ---- packaged_snacks
    (
        "packaged_snacks",
        "US",
        "CRNCH",
        "Crunchwell Foods, Inc.",
        "Crunchwell Foods makes potato chips, tortilla chips, pretzels and popcorn that are sold through grocery stores, convenience stores and vending operators across the United States. The company also runs a direct-store-delivery network that restocks shelves several times a week.",
        [],
    ),
    (
        "packaged_snacks",
        "GB",
        "BSCTR",
        "Biscuitry & Co. plc",
        "Biscuitry & Co. bakes biscuits, crackers and savoury snack bars sold under household brands in supermarkets. Own-label contracts with the large grocers account for roughly a quarter of its sales.",
        [],
    ),
    (
        "packaged_snacks",
        "IN",
        "RSNMK",
        "Rasoi Namkeen Foods Ltd.",
        "Rasoi Namkeen sells spicy fried and roasted nibbles such as bhujia, chivda and masala peanuts, packed in pouches and sold through small neighbourhood shops and modern trade outlets.",
        ["paraphrase"],
    ),
    (
        "packaged_snacks",
        "JP",
        "KSHYM",
        "Kashiyama Foods Co., Ltd.",
        "Kashiyama Foods produces rice crackers, seaweed snacks and small confectionery for the domestic market, selling mostly through convenience stores. {GEO_JP}",
        [],
    ),
    (
        "packaged_snacks",
        "GB",
        "OUTCR",
        "Outback Crisps Ltd",
        "Outback Crisps produces kettle-cooked chips, nut mixes and jerky for supermarkets and petrol stations. {BP3}",
        [],
    ),
    # ---- craft_brewers
    (
        "craft_brewers",
        "US",
        "HOPSM",
        "Hopsmith Brewing Co.",
        "{GEO_US} Hopsmith Brewing Company produces craft beer, including IPAs, lagers and seasonal ales. It operates brewery taprooms in Colorado and distributes its cans and kegs to bars and stores in 38 states.",
        [],
    ),
    (
        "craft_brewers",
        "DE",
        "BRHFK",
        "Brauhaus Falkenstein AG",
        "Brauhaus Falkenstein brews Pils, wheat beer and Märzen according to the purity law at its family-owned brewery, and sells in kegs and bottles to restaurants, beer gardens and retailers.",
        [],
    ),
    (
        "craft_brewers",
        "AU",
        "CRKTB",
        "Cricket Bay Brewing Ltd",
        "Cricket Bay ferments malt and hops into small-batch ales and lagers in Queensland, sold in its own pubs and bottle shops and through independent venues.",
        ["paraphrase"],
    ),
    (
        "craft_brewers",
        "GB",
        "HGHLD",
        "Highland Ales plc",
        "{GEO_GB} Highland Ales brews cask ales and bottled beers at three breweries and operates a chain of 120 pubs.",
        [],
    ),
    (
        "craft_brewers",
        "CA",
        "MPLCR",
        "Maplecrest Brewing Corp.",
        "Maplecrest Brewing operates microbreweries and a taproom chain in Ontario and Quebec, producing craft lagers, sours and fruit beers. {BP4}",
        [],
    ),
    # ---- airlines
    (
        "airlines",
        "US",
        "SKYWD",
        "Skyward Airlines, Inc.",
        "Skyward Airlines operates a hub-and-spoke network of 640 daily departures across North America and the Caribbean. Management guides to a CASM-ex fuel decline and a RASM increase of 3% as capacity, measured in available seat miles (ASMs), grows.",
        ["jargon"],
    ),
    (
        "airlines",
        "IN",
        "GAGAN",
        "Gagan Airways Ltd.",
        "Gagan Airways is a low-cost carrier flying domestic routes and short international flights with a single-type narrowbody fleet. Revenue comes from ticket sales and ancillary fees such as baggage and seat selection.",
        ["mislabelled"],
    ),
    (
        "airlines",
        "AU",
        "SWNGS",
        "Southern Wings Australia Ltd",
        "Southern Wings flies people between cities and remote towns, carrying holidaymakers, business travellers and mine workers on jets and propeller planes. Seats are sold online and through travel agents.",
        ["paraphrase"],
    ),
    (
        "airlines",
        "JP",
        "ASHAL",
        "Asahi Air Lines Co., Ltd.",
        "Asahi Air Lines offers scheduled passenger flights between major cities and several Asian destinations, and operates a cargo subsidiary. {BP5}",
        [],
    ),
    (
        "airlines",
        "GB",
        "PNNAW",
        "Pennine Airways plc",
        "{GEO_GB} Pennine Airways is a regional airline serving UK regional airports and the Scottish islands with turboprop aircraft.",
        [],
    ),
    # ---- trucking_logistics
    (
        "trucking_logistics",
        "US",
        "HLMRK",
        "Haulmark Freight Systems Inc.",
        "{GEO_US} Haulmark Freight Systems operates a fleet of 14,000 tractors and 45,000 trailers delivering full-truckload and less-than-truckload shipments. It also offers freight brokerage and dedicated contract carriage.",
        [],
    ),
    (
        "trucking_logistics",
        "CA",
        "NRDRL",
        "Northroad Logistics Inc.",
        "{GEO_CA} Northroad Logistics moves freight by truck and rail-linked intermodal services, and operates cross-dock terminals and a cold-chain network.",
        [],
    ),
    (
        "trucking_logistics",
        "DE",
        "KHNLG",
        "Kuhnert Logistik AG",
        "Kuhnert Logistik transports goods by road across Europe, and also runs contract warehousing and customs clearance for industrial customers. Its fleet of 3,200 lorries is mostly fitted with telematics.",
        [],
    ),
    (
        "trucking_logistics",
        "GB",
        "LRYWR",
        "Lorryworth Group plc",
        "Lorryworth carries pallets and parcels over Britain's roads for manufacturers and retailers, with overnight network hubs and a fleet of vans and heavy goods vehicles.",
        ["paraphrase"],
    ),
    (
        "trucking_logistics",
        "JP",
        "TKAIT",
        "Tokai Transport Co., Ltd.",
        "Tokai Transport provides parcel delivery, temperature-controlled trucking and 3PL warehousing services, with a growing e-commerce fulfilment business for online retailers.",
        ["jargon"],
    ),
    # ---- gold_miners
    (
        "gold_miners",
        "AU",
        "AURDG",
        "Aurum Ridge Mining Ltd",
        "Aurum Ridge produces gold from open-pit and underground operations, with a JORC-compliant reserve of 6.8 million ounces. All-in sustaining costs (AISC) were US$1,420 per ounce last year, and mill throughput is expanding to 5 Mtpa.",
        ["jargon"],
    ),
    (
        "gold_miners",
        "CA",
        "NGLKG",
        "Nugget Lake Gold Corp.",
        "Nugget Lake Gold is an Abitibi-based producer and explorer, with an NI 43-101 compliant resource of 3.1 million ounces grading 5.2 g/t. The company is advancing a decline at its flagship underground mine.",
        ["jargon"],
    ),
    (
        "gold_miners",
        "CA",
        "SRDOR",
        "Sierra Dorada Mining Inc.",
        "Sierra Dorada digs up and refines gold and silver at heap-leach mines. Metal is sold as dore bars to refiners, and the company is exploring neighbouring claims.",
        ["paraphrase"],
    ),
    (
        "gold_miners",
        "GB",
        "KLHRG",
        "Kalahari Gold plc",
        "Kalahari Gold is a London-listed producer with mines in Ghana and Tanzania, producing roughly 400,000 ounces a year, and has built two processing plants.",
        [],
    ),
    (
        "gold_miners",
        "JP",
        "KNZNM",
        "Kinzan Mining Co., Ltd.",
        "Kinzan Mining operates a small gold mine in Kyushu and holds equity interests in overseas gold projects. {BP1}",
        [],
    ),
    # ---- specialty_chemicals
    (
        "specialty_chemicals",
        "US",
        "PLMRQ",
        "Polymarq Specialty Chemicals Inc.",
        "Polymarq makes specialty additives, coating resins and adhesives for the automotive, construction and packaging industries. Its products are tailored to customer specifications and sold in lots from drums to railcars.",
        [],
    ),
    (
        "specialty_chemicals",
        "DE",
        "ALTMN",
        "Altmann Chemie AG",
        "Altmann produces catalysts, pigments and performance polymers, with all products registered under REACH. R&D spending is 4% of sales and about a third of revenue comes from products launched in the past five years.",
        ["jargon"],
    ),
    (
        "specialty_chemicals",
        "JP",
        "SEIWK",
        "Seiwa Kagaku Co., Ltd.",
        "Seiwa Kagaku produces electronic chemicals, including photoresists, cleaning solvents and polishing slurries, for semiconductor and display manufacturers.",
        [],
    ),
    (
        "specialty_chemicals",
        "IN",
        "AARFC",
        "Aarna Fine Chemicals Ltd.",
        "Aarna makes the building-block molecules that other companies turn into medicines and crop-protection products. It runs multi-purpose reactors at three sites and works under long-term supply agreements.",
        ["paraphrase"],
    ),
    (
        "specialty_chemicals",
        "GB",
        "LKLCT",
        "Lakeland Coatings plc",
        "Lakeland makes paints and protective finishes for ships, bridges, pipelines and factories. Its marine range lasts longer in saltwater and its coatings are applied in more than 40 countries.",
        ["paraphrase", "mislabelled"],
    ),
]

# Duplicate listings: (alias key, original key, new country, ticker, name, description or None)
# description None means "derive by case/whitespace/punctuation change from the original".
ALIAS_SPECS = [
    ("CA", "VLTGC", "US:VLTGD", "Voltguard Networks Inc. (CDR)", None),
    (
        "AU",
        "CRNCW",
        "US:CRNCH",
        "Crunchwell Foods Limited",
        "Crunchwell's product line is made up of potato and tortilla chips, pretzels and popcorn, which reach shoppers via supermarkets, corner stores and vending machines throughout America. It operates its own route-delivery fleet to keep retail shelves topped up every few days.",
    ),
]

FISCAL_YE = {"US": "12-31", "CA": "12-31", "GB": "03-31", "DE": "12-31", "JP": "03-31", "AU": "06-30", "IN": "03-31"}
SPLIT_DEV, SPLIT_HELD = "dev", "held_out"


def _expand(desc: str) -> tuple[str, list[str]]:
    tags: list[str] = []
    for cc, text in GEO.items():
        token = "{GEO_" + cc + "}"
        if token in desc:
            desc = desc.replace(token, text)
            tags.append("geo_trap")
    for name, text in BOILERPLATE.items():
        token = "{" + name + "}"
        if token in desc:
            desc = desc.replace(token, text)
            tags.append("boilerplate")
    assert "{" not in desc, desc
    return desc, tags


def _numbers(i: int) -> dict:
    # every field differs per record index (so no two listings share financials)
    revenue = 400.0 + i
    return {
        "price": round(10.0 + i * 0.25, 2),
        "shares_outstanding": 50.0 + i,
        "total_debt": 100.0 + i,
        "cash": 20.0 + i,
        "revenue": revenue,
        "ebitda": round(revenue * 0.15, 1),
        "net_income": round(revenue * 0.05, 1),
    }


def _record(i: int, country: str, ticker: str, name: str, desc: str, labels: tuple[str, str, str]) -> dict:
    return {
        "id": f"in{i:03d}",
        "ticker": ticker,
        "name": name,
        "description": desc,
        "sector": labels[0],
        "industry": labels[1],
        "sub_industry": labels[2],
        "country": country,
        "price_currency": "USD",
        "reporting_currency": "USD",
        "units": "millions",
        "fiscal_year_end": FISCAL_YE[country],
        "price_date": "2026-10-01",
        **_numbers(i),
    }


def _alias_a_text(orig: str) -> str:
    # case, whitespace and one punctuation-level change only
    return orig.lower().replace(". ", ".  ").replace("zero-trust", "zero trust")


def build(out: Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    business: dict[str, str] = {}
    tags: dict[str, list[str]] = {}
    desc_of: dict[str, str] = {}
    country_of: dict[str, str] = {}
    order: list[str] = []

    for i, (biz, country, ticker, name, raw_desc, manual) in enumerate(RAW):
        assert 3 <= len(ticker) <= 5 and ticker.isupper() and ticker.isalpha(), ticker
        key = f"{country}:{ticker}"
        assert key not in business, f"duplicate key {key}"
        desc, derived = _expand(raw_desc)
        labels = MISLABEL.get(key, TAXONOMY[biz])
        if key in MISLABEL:
            assert "mislabelled" in manual, key
        records.append(_record(i, country, ticker, name, desc, labels))
        business[key] = biz
        tags[key] = sorted(set(manual) | set(derived))
        desc_of[key] = desc
        country_of[key] = country
        order.append(key)

    # cross_country: none of the same-business peers sits in the company's own country
    for key in order:
        peers = [k for k in order if k != key and business[k] == business[key]]
        if all(country_of[k] != country_of[key] for k in peers):
            tags[key] = sorted(set(tags[key]) | {"cross_country"})

    aliases: dict[str, str] = {}
    n = len(records)
    for j, (cc, tick, orig, name, desc) in enumerate(ALIAS_SPECS):
        key = f"{cc}:{tick}"
        assert key not in business and key not in aliases
        text = desc if desc is not None else _alias_a_text(desc_of[orig])
        base = TAXONOMY[business[orig]]
        records.append(_record(n + j, cc, tick, name, text, base))
        aliases[key] = orig

    # splits: alternate dev/held_out within each business (tag-heavy first, so tags spread)
    splits: dict[str, list[str]] = {SPLIT_DEV: [], SPLIT_HELD: []}
    seen_mis = 0
    for bi, biz in enumerate(TAXONOMY):
        members = sorted(
            (k for k in order if business[k] == biz),
            key=lambda k: ("mislabelled" not in tags[k], -len(tags[k]), k),
        )
        if any("mislabelled" in tags[k] for k in members):
            parity = seen_mis  # alternate where the rare mislabelled company lands
            seen_mis += 1
        else:
            parity = 0 if len(splits[SPLIT_DEV]) <= 2.5 * bi else 1  # keep dev/held_out at 50/50
        for pos, key in enumerate(members):
            dev = (pos + parity) % 2 == 0
            splits[SPLIT_DEV if dev else SPLIT_HELD].append(key)
    for v in splits.values():
        v.sort()

    # labels from the TRUE taxonomy
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

    label_doc = {
        "_about": (
            "Independent synthetic retrieval evaluation labels, written without reference to any ranker. "
            "All companies are invented. Each company belongs to one TRUE business in a hand-written "
            "sector > industry > business taxonomy; the record's own sector/industry/sub_industry fields "
            "may be deliberately wrong (tag 'mislabelled'). Graded labels are derived mechanically from the "
            "true taxonomy: 3 same business, 2 same industry but different business, 1 same sector but "
            "different industry, 0 different sector. Aliases are duplicate listings of an existing company "
            "(different ticker, reworded or re-cased description); they are not targets and have no label rows. "
            "Tags: paraphrase, boilerplate, geo_trap, jargon, mislabelled are hand-assigned (boilerplate and "
            "geo_trap follow the shared text); cross_country is computed (none of its same-business peers "
            "is in its own country). Splits alternate dev/held_out inside every business."
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
        "aliases": dict(sorted(aliases.items())),
        "labels": labels,
    }

    def dump(path: Path, obj: object, sort_keys: bool) -> None:
        path.write_text(json.dumps(obj, indent=2, sort_keys=sort_keys, ensure_ascii=False) + "\n", encoding="utf-8")

    dump(out / "companies.json", records, False)
    dump(out / "fx_rates.json", {"base": "USD", "rates": {"USD": 1.0}}, True)
    dump(out / "labels.json", label_doc, True)


if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
