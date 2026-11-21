# genios-comps

An offline **comparable-companies (comps table) service**.

An analyst names the company they want to research. The service picks that company's peers from a universe of about 500 public companies and returns a comps table:

- each peer's market cap, enterprise value, EV/Revenue, EV/EBITDA and P/E, all in USD;
- **why each peer was chosen**, so the analyst can trust or adjust the list;
- summary statistics (mean, median, high, low) across the peers.

The service reads its data from a folder it is given at start-up. It runs fully offline and starts with a single command.

This project is under active development. Setup instructions, design notes and evaluation results will be added as each part lands.
