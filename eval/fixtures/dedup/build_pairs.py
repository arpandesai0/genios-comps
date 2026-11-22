"""Synthetic description pairs for evaluating near-duplicate detection.

Run `python build_pairs.py` to (re)write pairs.json next to this file.
"duplicate" means both texts describe the SAME company (one business listed
twice). Texts are hand-written; a few duplicate kinds apply a mechanical
transform to a hand-written base (case/whitespace, sentence reorder,
truncation, appended boilerplate), because that is exactly what those kinds
are. All companies are invented.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# ---------------------------------------------------------------- duplicates

CASE_BASES = [
    "Brightwell Dental makes digital dental scanners, clear aligners and related software, which it sells to orthodontists in North America and Europe. Its aligners are produced in a highly automated plant in Costa Rica.",
    "Fernhollow Farms grows, packs and ships organic apples and pears from orchards in the Pacific Northwest. Most of its fruit is sold to supermarket chains under long-term supply agreements.",
    "Tidewater Marine Services operates a fleet of tugboats and barges that move bulk cargo and assist ships in four East Coast ports. The company has been family-controlled since 1952.",
    "Lumina Cinemas owns and runs 210 multiplex theatres across the Midwest. Ticket sales, concessions and screen advertising make up its revenue.",
    "Granite Peak Brands makes outdoor equipment, including tents, backpacks and sleeping bags, and sells them through specialty retailers and its own website. About a fifth of its sales are outside the United States.",
    "Orchid Pay processes card payments for online merchants in Southeast Asia. It earns a small fee on every transaction and offers fraud screening as an add-on.",
    "Kestrel Aerospace Fasteners supplies titanium bolts, rivets and clips used in commercial aircraft. Production is certified to aerospace quality standards, with long qualification cycles.",
    "Marigold Senior Living operates assisted-living and memory-care communities in the Sun Belt. Residents pay monthly fees that cover accommodation, meals and care services.",
    "Stonebridge Cement produces cement and ready-mix concrete for construction projects in the south-east of England. Its two kilns run on a growing share of alternative fuels.",
    "Vantor Analytics provides satellite imagery and geospatial analysis to insurers, farmers and government agencies. Customers buy data subscriptions and custom monitoring reports.",
]

CASE_TRANSFORMS = [
    lambda s: s.lower().replace(". ", ".  "),
    lambda s: s.upper(),
    lambda s: "  ".join(s.replace(",", "").split(" ")),
    lambda s: " ".join(w.capitalize() for w in s.split()),
    lambda s: "  " + s.rstrip(".").replace("-", " ").replace(", ", " , ") + " ",
]

REORDER_BASES = [
    "Crestline Pet Foods produces dry and wet food for dogs and cats. Its recipes use named meats and no artificial colours. The products are sold through pet specialty stores and online. A subscription programme accounts for a growing share of orders.",
    "Halcyon Power Tools designs cordless drills, saws and sanders for professional tradespeople. All of its tools share one battery platform. The company sells mainly through hardware wholesalers. Warranty claims have been below 2% of units.",
    "Meridian Freight Brokers matches shippers with independent truckers using an online marketplace. It does not own trucks. Revenue is the spread between what shippers pay and what carriers receive. The marketplace handles roughly 90,000 loads a month.",
    "Solstice Hotels owns 40 upscale beach resorts in the Caribbean and Mexico. Guests come mostly from North America. Occupancy peaks in winter, and the company manages the resorts itself. Renovations are planned for eight of the properties.",
    "Quarry Hill Software builds scheduling tools for hospitals. Nurses can swap shifts from a phone app. The product is licensed per bed. Sales are made through direct teams to hospital groups.",
    "Ardent Steel Works operates two electric arc furnaces that melt scrap into reinforcing bar and wire rod. The mills sit near a major river port. Customers are construction firms and fabricators. Output has increased every year since the plant was modernised.",
    "Pelham Veterinary Group owns 150 animal hospitals and clinics. The clinics treat dogs, cats and small exotic pets. Revenue comes from examinations, surgeries, vaccines and pharmacy sales. The group buys independent practices and keeps their local brands.",
    "Lanternfish Games develops mobile puzzle and strategy games. The games are free to download. Money comes from in-app purchases and advertising. A new title is released about every nine months.",
    "Coppervale Water Utility supplies drinking water and wastewater services to 900,000 people. Its prices are approved by a state regulator. The utility is replacing ageing pipes under a ten-year plan. Capital spending is funded by debt and retained earnings.",
    "Zephyr Textile Mills spins cotton yarn and weaves denim fabric for jeans makers. Its mills are in Gujarat. About 40% of sales are exports. The company installed solar panels to power its largest plant.",
]
REORDER_PERMS = [(3, 2, 1, 0), (1, 3, 0, 2), (2, 0, 3, 1), (1, 2, 3, 0), (3, 0, 1, 2)]

TRUNC_BASES = [
    "Alderwood Lumber manages timberlands and operates sawmills producing framing lumber. It owns 1.2 million acres of forest in the Pacific Northwest. Most of its output goes to home builders. A smaller division makes wood pellets for heating.",
    "Beacon Radiology runs 85 outpatient imaging centres offering MRI, CT and ultrasound scans. Referrals come from physician groups and hospitals. Contracts with health insurers set the prices. The company has been adding mobile scanning units in rural areas.",
    "Cobalt Bay Seafood farms Atlantic salmon in sea pens and processes it into fillets. It sells fresh and frozen product to supermarkets in Europe and Asia. Feed represents its largest cost. The company recently opened a land-based hatchery.",
    "Delphine Cosmetics creates skincare and makeup products sold in department stores and online. Its brand targets consumers aged 25 to 45. Product development focuses on natural ingredients. A third of revenue comes from the Asian market.",
    "Eastgate Student Housing owns purpose-built residences near large universities. Beds are leased on academic-year contracts. Occupancy exceeded 97% last year. The company is developing two new properties near city campuses.",
    "Falconer Defence Systems manufactures radar and electronic warfare equipment for navies and air forces. Contracts are awarded by governments over multi-year periods. Export sales need licences. Research and development consumes about 12% of revenue.",
    "Glenmore Distillers produces single-malt whisky and gin at three distilleries. The spirits are aged in oak casks and exported to more than 60 countries. A visitor centre welcomes tourists. Inventory of maturing whisky is its largest asset.",
    "Harbour Light Insurance Brokers places commercial insurance for mid-sized companies. It earns commissions from insurers and fees from clients. The firm has grown through acquiring small agencies. Offices are located in 12 cities.",
    "Ironbark Mining Equipment makes underground loaders, haul trucks and drill rigs. Mining companies are its customers. Spare parts and servicing bring in about half of sales. The company operates service centres near major mines.",
    "Juniper Learning provides online courses and certificates in data science and project management. Learners pay monthly subscriptions. Universities license its content for their own students. The platform has 6 million registered users.",
]

EXTRA_BASES = [
    "Kingfisher Biotech Supply sells laboratory reagents, cell culture media and consumables to universities and drug developers. Orders are placed through its online catalogue and shipped within 24 hours.",
    "Lakeview Mortgage Servicing collects payments from home loan borrowers and passes them to investors. It earns fees as a percentage of the balance it services.",
    "Mountainside Ski Resorts operates five ski areas in the Rockies. Season passes and lift tickets account for most of its revenue.",
    "Norwood Paper Packaging makes corrugated boxes and cartons for food and e-commerce companies. It runs eleven plants close to its customers.",
    "Oakmont Retirement Funds manage pension assets for corporations and public employers. Fees are charged as a percentage of assets under management.",
    "Pinecrest Auto Dealerships sells new and used cars and runs service departments across the Southeast. Parts and service provide the bulk of the profit.",
    "Quillon Data Centres leases racks and power capacity to cloud providers and large enterprises. Its facilities sit close to major metropolitan fibre routes.",
    "Ridgeway Truck Rental leases tractors and trailers to carriers on short and long terms. Its fleet is serviced in more than 60 company-owned shops.",
    "Sapphire Shipping owns product tankers carrying refined fuels between Asia and Europe. Vessels are chartered out on spot and time-charter contracts.",
    "Tamarind Spices blends and packs spices, sauces and ready meals for retail and restaurant customers. Its plants are certified to food safety standards.",
]

BOILERPLATE = [
    "We are a leading provider of innovative solutions, guided by a mission to deliver long-term value to our shareholders, customers and employees. Integrity, teamwork and operational excellence are at the heart of everything we do.",
    "The company is committed to sustainability and responsible corporate citizenship. It reports annually against recognised ESG frameworks and works to cut its carbon footprint, promote diversity and inclusion, and support the communities where it operates.",
    "With a heritage built on trust, the group has grown steadily through disciplined investment and strategic acquisitions. Strong corporate governance and an experienced management team provide a platform for profitable, sustainable growth.",
    "Customer focus and a commitment to quality drive the organisation. It invests in its people, upholds the highest ethical standards and aims to be an employer and partner of choice in every market it serves.",
    "Operating in a competitive and fast-changing environment, the business concentrates on growth, margin improvement and cash generation. Its strategy rests on three pillars: operational discipline, customer intimacy and continuous innovation.",
    "Our vision is to be the most trusted name in our industry. We combine deep expertise, a collaborative culture and modern technology to create value for all of our stakeholders.",
]

REWORDED = [
    (
        "Pioneer Glassworks manufactures glass bottles and jars for beverage and food producers, operating nine furnaces across Europe.",
        "The company, Pioneer Glassworks, produces glass containers for drinks and food brands from nine furnaces located throughout the continent.",
    ),
    (
        "Nimbus Air Charter provides private jet charter and fractional ownership to business travellers and wealthy individuals.",
        "Wealthy individuals and corporate travellers can hire private aircraft, or buy a share of one, through Nimbus Air Charter.",
    ),
    (
        "Coralline Cosmetics sells skincare products through department stores and online retailers, with an emphasis on sun protection.",
        "Skin-care items, particularly those that shield against the sun, are Coralline Cosmetics' speciality, offered via department stores and e-tailers.",
    ),
    (
        "Redstone Capital is an investment bank advising companies on mergers and raising funds in debt and equity markets.",
        "Redstone Capital, an investment bank, helps corporate clients with takeovers and mergers and arranges their bond and share offerings.",
    ),
    (
        "Oakley Dairy collects milk from 600 farms and turns it into cheese, butter and yoghurt for supermarkets.",
        "Cheese, butter and yoghurt are produced by Oakley Dairy from the milk of 600 farms and delivered to grocery chains.",
    ),
    (
        "Halifax Rail Services maintains and overhauls locomotives and freight wagons for railway operators.",
        "Railway operators hire Halifax Rail Services to service and refurbish their freight cars and locomotives.",
    ),
    (
        "Starfield Observatory Technologies builds telescopes and imaging sensors for research institutions.",
        "Research institutes buy telescopes and image sensors manufactured by Starfield Observatory Technologies.",
    ),
    (
        "Ambrosia Bakeries makes bread, rolls and pastries in 14 plants and delivers them to supermarkets and restaurants.",
        "Fourteen factories of Ambrosia Bakeries turn out loaves, buns and pastries that go to grocers and eateries.",
    ),
    (
        "Bluepoint Staffing places temporary and permanent workers with clients in healthcare, logistics and finance.",
        "Clients in medicine, warehousing and banking use Bluepoint Staffing to find short-term and full-time employees.",
    ),
    (
        "Tundra Energy Services provides hydraulic fracturing and well completion services to shale oil producers.",
        "Shale oil producers hire Tundra Energy Services to fracture rock and complete their wells.",
    ),
    (
        "Vertex Engineering designs bridges, tunnels and highways for governments and contractors.",
        "Governments and building contractors commission Vertex Engineering to plan roads, bridges and tunnels.",
    ),
    (
        "Everbright Lighting manufactures LED bulbs and fixtures for homes and commercial buildings.",
        "LED lamps and light fittings for houses and offices are what Everbright Lighting makes.",
    ),
]

UPDATED = [
    (
        "Rivergate Bank offers checking, savings and mortgage products through 60 branches in Ohio.",
        "Rivergate Bank offers checking, savings and mortgage products through 60 branches in Ohio and Pennsylvania, and recently launched a wealth management arm.",
    ),
    (
        "Sunbeam Solar installs rooftop solar systems for homeowners in California.",
        "Sunbeam Solar installs rooftop solar systems and home batteries for homeowners in California and Arizona.",
    ),
    (
        "Pacific Rim Logistics provides ocean freight forwarding between Asia and the US West Coast.",
        "Pacific Rim Logistics provides ocean freight forwarding between Asia and North America and has added air cargo services.",
    ),
    (
        "Tenzing Software sells accounting software to freelancers.",
        "Tenzing Software sells accounting and invoicing software to freelancers and small agencies, and has added a payments feature.",
    ),
    (
        "Orion Foods produces frozen pizzas for grocery stores.",
        "Orion Foods produces frozen pizzas and plant-based meals for grocery stores and has opened a second factory in Texas.",
    ),
    (
        "Westmark Clinics operates 30 urgent care centres in Florida.",
        "Westmark Clinics operates 45 urgent care centres in Florida and Georgia and offers telehealth visits.",
    ),
    (
        "Cascade Drilling Tools makes drill bits for oil and gas wells.",
        "Cascade Drilling Tools makes drill bits for oil and gas wells and geothermal projects.",
    ),
    (
        "Maple Leaf Telecom supplies mobile service to 2 million customers in Ontario.",
        "Maple Leaf Telecom supplies mobile and home internet service to 2.4 million customers in Ontario and Quebec.",
    ),
    (
        "Ironclad Security guards office buildings and retail centres.",
        "Ironclad Security guards office buildings and retail centres and has started to supply remote video monitoring.",
    ),
    (
        "Bayside Boats builds fishing boats and pontoons.",
        "Bayside Boats builds fishing boats, pontoons and, since its acquisition last year of an electric outboard maker, electric propulsion systems.",
    ),
    (
        "Quantum Leap Education runs tutoring centres for secondary school students in India.",
        "Quantum Leap Education runs tutoring centres and an online platform for secondary school students in India and the Middle East.",
    ),
    (
        "Harvest Moon Brewing produces lagers and sells them in bars.",
        "Harvest Moon Brewing produces lagers and non-alcoholic beers and sells them in bars, supermarkets and online.",
    ),
]

# ------------------------------------------------------------- non-duplicates

# Clusters of three different companies in the same narrow business, similar wording.
PEER_CLUSTERS = [
    [
        "Harvest Basket operates 310 supermarkets offering fresh produce, bakery, meat and household goods. The chain also sells a private-label range and runs a home delivery service.",
        "Greenfield Markets runs 275 supermarkets selling fresh produce, meat, bakery items and household products. Its own-brand range and online delivery service complement the stores.",
        "Valley Fresh Grocers operates 340 supermarkets with fresh produce, bakery, deli and household goods, plus a growing own-label line and click-and-collect service.",
    ],
    [
        "Granitex produces cement, aggregates and ready-mixed concrete from plants in the Midwest. Infrastructure and housing projects are its main end markets.",
        "Rockbridge Materials makes cement, crushed stone and ready-mix concrete for infrastructure and residential construction across the Midwest.",
        "Midland Cementworks manufactures cement and ready-mixed concrete and quarries aggregates, selling mainly to road, bridge and housing projects in the Midwest.",
    ],
    [
        "Wanderly is an online travel agency where customers book flights, hotels and rental cars. It earns commissions from suppliers and booking fees from travellers.",
        "Journeyhub operates a website and app for booking flights, hotels and car rentals, earning commissions from travel suppliers and fees from customers.",
        "TripNest runs an online marketplace for airline tickets, hotel rooms and rental cars, taking commissions from suppliers and service fees from travellers.",
    ],
    [
        "Patty Barn franchises 1,900 quick-service restaurants serving hamburgers, fries and milkshakes. Roughly 95% of restaurants are owned by franchisees who pay royalties.",
        "Grillhouse Burgers is a quick-service restaurant chain of 2,200 locations selling hamburgers, fries and shakes, with franchisees operating nearly all outlets and paying royalties.",
        "Big Bun Restaurants franchises 1,400 fast-food outlets serving burgers, fries and shakes; franchisees pay royalties and run almost every restaurant.",
    ],
    [
        "Pipeline Cloud sells subscription customer relationship management software that helps sales teams track leads, forecast revenue and automate follow-ups.",
        "Clientloop provides cloud CRM software on a subscription basis, letting sales teams manage leads, forecast deals and automate outreach.",
        "Salesflow offers a subscription-based CRM platform used by sales teams to track leads, predict revenue and automate follow-up emails.",
    ],
    [
        "Meridian Lines operates 210 container ships on trade lanes between Asia, Europe and North America. Freight rates and vessel utilisation drive earnings.",
        "Oceanic Box Carriers runs 190 container vessels on Asia-Europe and trans-Pacific routes, with earnings driven by freight rates and utilisation.",
        "BlueTide Container Shipping owns and charters 240 box ships serving Asia, Europe and the Americas. Its results follow freight rates and fleet utilisation.",
    ],
    [
        "Sunforge manufactures crystalline silicon solar panels and sells them to installers and utility-scale developers. Its factories have a combined capacity of 8 GW.",
        "Helio Modules produces monocrystalline solar modules for rooftop installers and large solar farms, with 6 GW of annual manufacturing capacity.",
        "PanelWorks makes silicon photovoltaic modules for installers and utility-scale solar projects from factories with 7 GW of capacity.",
    ],
    [
        "Stayline Hospitality Trust owns 85 upscale and select-service hotels leased to or managed by major brands. Rental income varies with room revenue.",
        "Capstone Lodging REIT owns 70 select-service and upscale hotels operated by leading brands, earning rent linked to hotel revenues.",
        "Harbor Inns Trust is a REIT with 92 upscale and select-service hotels run by national brands, receiving revenue-based rents.",
    ],
    [
        "Evergreen Life writes term and whole life insurance and annuities sold through agents. Profits depend on mortality experience and investment spreads.",
        "Longview Assurance sells term life, whole life and annuity products through agents, with earnings driven by mortality results and investment spreads.",
        "Perpetua Life Insurance offers term and permanent life policies and annuities via career agents; mortality and investment margins drive profit.",
    ],
    [
        "Meridian Care Hospitals operates 24 private hospitals providing surgery, maternity and emergency care, funded by insurers and patients.",
        "Lifespring Health runs 28 private hospitals offering surgical, maternity and emergency services, paid for by insurers and self-pay patients.",
        "Carewell Hospital Group owns 21 private hospitals with surgery, maternity and emergency departments, receiving payments from insurers and patients.",
    ],
    [
        "Stridewell designs running shoes and athletic apparel sold through specialty stores and its own e-commerce site; it sponsors marathon events.",
        "Velocity Athletics makes running footwear and performance clothing sold in sporting goods stores and online, and sponsors road races.",
        "Pacebreaker produces running shoes and sportswear for specialty retailers and a direct-to-consumer website, sponsoring local races.",
    ],
    [
        "Andesite Copper operates two open-pit copper mines and a concentrator, producing 300,000 tonnes of copper in concentrate a year.",
        "Cordillera Metals mines copper at two open pits, processing ore at a concentrator to produce 280,000 tonnes of copper in concentrate annually.",
        "Red Mesa Copper runs open-pit copper mines with a concentrator, yielding about 320,000 tonnes of copper concentrate per year.",
    ],
    [
        "Brightpath Dental Group owns 220 dental clinics offering check-ups, orthodontics and cosmetic dentistry, and pays dentists a share of fees collected.",
        "Smilecare Partners runs 190 dental practices providing check-ups, braces and cosmetic treatments, sharing collected fees with its dentists.",
        "Toothwise Clinics operates 250 dental surgeries with routine care, orthodontics and cosmetic work, and compensates dentists with a percentage of fees.",
    ],
]

# Short single-business sentences for the shared-boilerplate pairs (different businesses each).
SB_SENTENCES = [s.split(". ")[0].rstrip(".") + "." for s in CASE_BASES + REORDER_BASES]
SB_PAIR_GAP = 11

# Templates: same sentence frame, different companies in different businesses.
TEMPLATES = [
    (
        "{name} is a {kind} headquartered in {place} that {does}. The company has approximately {n} employees and sells to customers in {m} countries.",
        [
            (
                "Arbor Dynamics",
                "manufacturer of industrial robots",
                "Ohio",
                "builds robotic arms for automotive assembly lines",
                "2,400",
                "31",
            ),
            (
                "Bluefin Capital",
                "investment management firm",
                "Singapore",
                "manages equity and bond portfolios for pension funds",
                "650",
                "12",
            ),
            (
                "Candlewick Foods",
                "packaged-food company",
                "Manchester",
                "produces frozen pies and ready meals for supermarkets",
                "3,800",
                "9",
            ),
            (
                "Dunmore Biologics",
                "biotechnology company",
                "Dublin",
                "develops antibody therapies for autoimmune disease",
                "310",
                "6",
            ),
        ],
    ),
    (
        "Founded in {year}, {name} {does}. It operates {n} {units} in {place} and reported revenue of ${rev} million last year.",
        [
            (
                "Eastport Hardware",
                "1946",
                "sells tools and building supplies to contractors",
                "120",
                "stores",
                "the Southeast",
                "880",
            ),
            (
                "Fenwick Telecom",
                "1998",
                "provides broadband internet and television service",
                "45",
                "regional offices",
                "western Canada",
                "1,240",
            ),
            (
                "Greenacre Landscaping",
                "1987",
                "designs and maintains commercial landscapes",
                "60",
                "branches",
                "Texas",
                "310",
            ),
            (
                "Hollis Pharma Services",
                "2005",
                "conducts clinical trials for drug developers",
                "14",
                "research sites",
                "Central Europe",
                "190",
            ),
        ],
    ),
    (
        "{name} is a leading {kind} in {place}. It offers {prod}, and its customers include {cust}.",
        [
            (
                "Ivywood Systems",
                "software provider",
                "the Nordic region",
                "payroll and scheduling tools",
                "retailers and hospitals",
            ),
            (
                "Jasper Foundry",
                "metal casting company",
                "Brazil",
                "iron and aluminium castings",
                "truck makers and pump manufacturers",
            ),
            (
                "Kinsley Media",
                "publisher",
                "Australia",
                "regional newspapers and local news websites",
                "advertisers and subscribers",
            ),
            (
                "Linden Pharma",
                "drug distributor",
                "Turkey",
                "prescription medicines and hospital supplies",
                "pharmacies and public hospitals",
            ),
        ],
    ),
    (
        "{name} designs, manufactures and sells {prod} to {cust}. Based in {place}, the company operates {n} facilities worldwide.",
        [
            (
                "Marlow Instruments",
                "scientific measuring equipment",
                "university and industrial laboratories",
                "Massachusetts",
                "six",
            ),
            ("Northgate Furniture", "office desks and chairs", "corporate facility managers", "North Carolina", "four"),
            ("Oriel Optics", "camera lenses and optical sensors", "phone and drone makers", "Taiwan", "nine"),
            ("Pembroke Marine", "outboard engines and boat trailers", "boat dealers and shipyards", "Florida", "three"),
        ],
    ),
    (
        "At {name}, we {does}. Our strategy is to {strategy}, and our customers include {cust}.",
        [
            (
                "Quayside Energy",
                "produce and sell natural gas",
                "grow through low-cost drilling in proven basins",
                "utilities and industrial users",
            ),
            (
                "Rosewell Bank",
                "provide deposit, loan and card services",
                "expand in fast-growing suburban markets",
                "households and small firms",
            ),
            (
                "Sable Software",
                "build tools for managing digital advertising",
                "add features through frequent small releases",
                "agencies and e-commerce brands",
            ),
            (
                "Thistle Foods",
                "bake and distribute fresh bread",
                "win more shelf space in discount supermarkets",
                "grocery chains and cafes",
            ),
        ],
    ),
    (
        "{name} owns and operates {n} {assets} in {place}. Revenue is generated from {rev}.",
        [
            ("Underhill Parking", "340", "car parks", "the Northeast", "hourly and monthly parking fees"),
            ("Vireo Storage", "180", "self-storage facilities", "the Sun Belt", "monthly unit rentals"),
            (
                "Willowmere Hospitals",
                "12",
                "private hospitals",
                "southern England",
                "payments from insurers and patients",
            ),
            ("Xander Wind", "27", "onshore wind farms", "Scandinavia", "electricity sales under long-term contracts"),
        ],
    ),
    (
        "{name} is a holding company whose subsidiaries {does}. The group has {n} employees and is headquartered in {place}.",
        [
            ("Yarrow Holdings", "produce cement and ready-mix concrete", "5,600", "Johannesburg"),
            ("Zenith Group", "provide life insurance and pension products", "9,100", "Amsterdam"),
            ("Ashdown Holdings", "operate regional airlines and ground handling", "7,400", "Vancouver"),
            ("Birchfield Group", "make animal feed and process poultry", "12,300", "Sao Paulo"),
        ],
    ),
    (
        "Since {year}, {name} has {does}. Today the company serves {cust} from its base in {place}.",
        [
            (
                "Carrow Pumps",
                "1962",
                "manufactured industrial pumps and valves",
                "oil refiners and water utilities",
                "Leeds",
            ),
            (
                "Dovecote Travel",
                "1989",
                "organised guided walking holidays",
                "holidaymakers across Europe",
                "Edinburgh",
            ),
            ("Elmhurst Seeds", "1934", "bred and sold vegetable and grain seeds", "farmers and garden centres", "Iowa"),
            (
                "Fairlight Security",
                "2001",
                "installed and monitored alarm systems",
                "homeowners and small businesses",
                "Ottawa",
            ),
        ],
    ),
    (
        "The Company {does}. Its principal products are {prod}, which are sold to {cust}.",
        [
            ("Greystone Brewing", "brews and bottles beer", "lagers and pale ales", "pubs and supermarkets"),
            ("Halden Plastics", "moulds plastic parts", "bottle caps and storage crates", "food packers and retailers"),
            (
                "Inverness Tweed",
                "weaves woollen cloth and makes garments",
                "jackets and scarves",
                "department stores and tourists",
            ),
            (
                "Juno Medical",
                "develops respiratory devices",
                "ventilators and oxygen concentrators",
                "hospitals and home-care providers",
            ),
        ],
    ),
    (
        "{name} Plc is a {kind} that {does}. It was admitted to the {exch} in {year}.",
        [
            (
                "Kestrel Retail",
                "clothing retailer",
                "sells fashion through 400 high-street stores",
                "London Stock Exchange",
                "2004",
            ),
            (
                "Larkspur Water",
                "water utility",
                "supplies drinking water to two million customers",
                "London Stock Exchange",
                "1989",
            ),
            (
                "Meadowbank Biotech",
                "drug developer",
                "researches treatments for rare genetic diseases",
                "AIM market",
                "2016",
            ),
            (
                "Nettlebed Logistics",
                "freight forwarder",
                "arranges sea and air shipments for manufacturers",
                "AIM market",
                "2010",
            ),
        ],
    ),
    (
        "{name} provides {prod} through its {n} operating segments. The company is listed on the {exch} and paid a dividend of {div} per share last year.",
        [
            ("Oakhurst Industries", "engineering services", "three", "New York Stock Exchange", "$0.80"),
            ("Pennant Resorts", "holiday and leisure services", "four", "New York Stock Exchange", "$0.45"),
            ("Quincy Health", "diagnostic and care services", "two", "Nasdaq", "$1.10"),
            ("Rutland Utilities", "gas and electricity distribution", "three", "Nasdaq", "$1.65"),
        ],
    ),
]

# Related but distinct units of one corporate group.
GROUP_PAIRS = [
    (
        "Marlton Motors designs, builds and sells passenger cars and light trucks through a network of franchised dealers, and reports results by region.",
        "Marlton Motor Credit provides retail loans and leases to customers buying Marlton vehicles, and floor-plan financing to the dealers that sell them.",
    ),
    (
        "Calder Health operates 38 acute-care hospitals and 200 outpatient centres, treating patients referred by physicians across the region.",
        "Calder Health Plans sells Medicare Advantage and employer-sponsored insurance to members, paying claims to hospitals including those of its parent.",
    ),
    (
        "Pacifica Airways flies 180 aircraft on domestic and international routes, carrying business and leisure passengers.",
        "Pacifica Rewards runs the airline's frequent-flyer programme, selling miles to credit card issuers and retail partners.",
    ),
    (
        "Harrowgate Stores operates 600 department stores selling clothing, home goods and cosmetics.",
        "Harrowgate Bank issues the retailer's store credit cards and earns interest and late fees on cardholder balances.",
    ),
    (
        "Brightwater Power owns the poles, wires and substations that deliver electricity to 2 million customers under regulated tariffs.",
        "Brightwater Energy Retail sells electricity and gas to households under competitive contracts, buying power on the wholesale market.",
    ),
    (
        "Cedar Hollow Homes builds and sells single-family homes and townhouses in 40 communities.",
        "Cedar Hollow Mortgage originates home loans for Cedar Hollow's buyers and sells the loans to investors.",
    ),
    (
        "Tallgrass Petroleum explores for and produces crude oil and natural gas from fields in Oklahoma and Texas.",
        "Tallgrass Refining processes crude oil into gasoline and diesel and sells them through branded service stations.",
    ),
    (
        "Nimbus Software licenses enterprise resource planning software to manufacturers and distributors.",
        "Nimbus Consulting implements and customises ERP systems for clients, using staff certified on the parent's software.",
    ),
    (
        "Whitcombe Pharma develops and manufactures prescription medicines sold to wholesalers and hospitals.",
        "Whitcombe Pharmacies is a chain of 900 retail drugstores filling prescriptions and selling health and beauty products.",
    ),
    (
        "Skylink Telecom provides mobile and broadband services to 30 million subscribers.",
        "Skylink Towers owns 12,000 cell towers and leases space to wireless carriers, with Skylink Telecom as its anchor tenant.",
    ),
    (
        "Oceanway Shipping operates 60 container ships connecting Asia and Europe.",
        "Oceanway Terminals runs container ports and rail yards that load and unload ships, including those of Oceanway Shipping.",
    ),
    (
        "Prairie Harvest Machinery builds tractors, combines and sprayers sold through independent farm equipment dealers.",
        "Prairie Harvest Financial offers loans and leases to farmers buying the machinery and finances dealer inventories.",
    ),
    (
        "Starlight Entertainment produces feature films and television series and licenses them to cinemas and streaming services.",
        "Starlight Parks operates theme parks and resorts based on the studio's characters, earning admission fees and merchandise sales.",
    ),
    (
        "Fairmount Bank offers checking accounts, mortgages and business loans through 300 branches.",
        "Fairmount Asset Management runs mutual funds and manages portfolios for institutions and wealthy individuals, earning fees on assets.",
    ),
]


# ----------------------------------------------------------------- assembly


def _pair(a: str, b: str, duplicate: bool, kind: str) -> dict:
    return {"a": a, "b": b, "duplicate": duplicate, "kind": kind}


def _sentences(text: str) -> list[str]:
    return [s.strip() + "." for s in text.rstrip(".").split(". ")]


def _fill(template: str, names: tuple[str, ...], fields: list[str]) -> str:
    return template.format(**dict(zip(fields, names, strict=False)))


def _template_pairs() -> list[dict]:
    field_lists = [
        ["name", "kind", "place", "does", "n", "m"],
        ["name", "year", "does", "n", "units", "place", "rev"],
        ["name", "kind", "place", "prod", "cust"],
        ["name", "prod", "cust", "place", "n"],
        ["name", "does", "strategy", "cust"],
        ["name", "n", "assets", "place", "rev"],
        ["name", "does", "n", "place"],
        ["name", "year", "does", "cust", "place"],
        ["name", "does", "prod", "cust"],
        ["name", "kind", "does", "exch", "year"],
        ["name", "prod", "n", "exch", "div"],
    ]
    out = []
    for (tpl, fills), fields in zip(TEMPLATES, field_lists, strict=False):
        texts = [_fill(tpl, f, fields) for f in fills]
        out.append(_pair(texts[0], texts[1], False, "same_template"))
        out.append(_pair(texts[2], texts[3], False, "same_template"))
    return out


def build(out: Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[dict]] = {}

    groups["case_whitespace"] = [
        _pair(t, CASE_TRANSFORMS[i % len(CASE_TRANSFORMS)](t), True, "case_whitespace")
        for i, t in enumerate(CASE_BASES)
    ]
    groups["reworded"] = [_pair(a, b, True, "reworded") for a, b in REWORDED]
    reordered = []
    for i, t in enumerate(REORDER_BASES):
        s = _sentences(t)
        perm = REORDER_PERMS[i % len(REORDER_PERMS)]
        reordered.append(_pair(t, " ".join(s[j] for j in perm), True, "reordered"))
    groups["reordered"] = reordered
    truncated = []
    for i, t in enumerate(TRUNC_BASES):
        s = _sentences(t)
        truncated.append(_pair(t, " ".join(s[: 1 + i % 2]), True, "truncated"))
    groups["truncated"] = truncated
    extra = []
    for i, t in enumerate(EXTRA_BASES):
        bp = BOILERPLATE[i % len(BOILERPLATE)]
        extra.append(_pair(t, (bp + " " + t) if i % 2 else (t + " " + bp), True, "extra_boilerplate"))
    groups["extra_boilerplate"] = extra
    groups["updated"] = [_pair(a, b, True, "updated") for a, b in UPDATED]

    peers = []
    for cl in PEER_CLUSTERS:
        peers += [
            _pair(cl[0], cl[1], False, "same_business_peer"),
            _pair(cl[1], cl[2], False, "same_business_peer"),
            _pair(cl[0], cl[2], False, "same_business_peer"),
        ]
    groups["same_business_peer"] = peers[:38]

    shared = []
    n = len(SB_SENTENCES)
    for i in range(22):
        x, y = SB_SENTENCES[i % n], SB_SENTENCES[(i + SB_PAIR_GAP) % n]
        bp = BOILERPLATE[i % len(BOILERPLATE)]
        if i % 2:
            shared.append(_pair(x + " " + bp, y + " " + bp, False, "shared_boilerplate"))
        else:
            shared.append(_pair(bp + " " + x, bp + " " + y, False, "shared_boilerplate"))
    groups["shared_boilerplate"] = shared
    groups["same_template"] = _template_pairs()
    groups["same_group_different_unit"] = [_pair(a, b, False, "same_group_different_unit") for a, b in GROUP_PAIRS]

    # splits alternate within each kind (cluster-wise for same_business_peer, so that
    # no company description appears in both splits)
    for kind, items in groups.items():
        for i, p in enumerate(items):
            unit = i // 3 if kind == "same_business_peer" and i < 36 else i
            p["split"] = "dev" if unit % 2 == 0 else "held_out"
        if kind == "same_business_peer":
            items[36]["split"], items[37]["split"] = "dev", "held_out"
        # swap a/b on alternate pairs so position carries no signal
        for i, p in enumerate(items):
            if i % 2:
                p["a"], p["b"] = p["b"], p["a"]

    allp = [p for items in groups.values() for p in items]
    random.Random(7).shuffle(allp)
    for i, p in enumerate(allp):
        p["id"] = f"p{i:03d}"
    pairs = [{k: p[k] for k in ("id", "a", "b", "duplicate", "kind", "split")} for p in allp]

    doc = {
        "_about": (
            "Independent synthetic pairs for evaluating near-duplicate detection between company "
            "descriptions. 'duplicate' is true when both texts describe the SAME company (one business "
            "listed twice), false otherwise. Duplicate kinds: case_whitespace, reworded, reordered, "
            "truncated, extra_boilerplate, updated. Non-duplicate kinds: same_business_peer, "
            "shared_boilerplate, same_template, same_group_different_unit. Texts are hand-written and all "
            "companies are invented; case_whitespace, reordered, truncated and extra_boilerplate apply a "
            "mechanical transform to a hand-written base. Splits alternate within each kind; "
            "same_business_peer alternates by cluster so a description never appears in both splits. "
            "Written without reference to any similarity code."
        ),
        "pairs": pairs,
    }
    (out / "pairs.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
