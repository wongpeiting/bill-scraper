# Social Media Bill Scraper

Tracks federal and state legislation related to social media regulation across all 50 US states using the [LegiScan API](https://legiscan.com/).

**3,406 bills** | **49 states** | **59 fields per bill** | Updates every 3 days via GitHub Actions

## What it tracks

Bills matching 20 keyword queries: TikTok, ByteDance, social media, online platform, age verification, parental consent, screen time, content moderation, deepfake, algorithm, and more.

Each bill includes: sponsor, party, status, committee, full action history, vote tallies, bill text URLs, amendments, and auto-classified topic categories.

## Topic categories

| Topic | Bills |
|---|---|
| Youth safety | 827 |
| School restrictions | 611 |
| Deepfakes/AI | 157 |
| Algorithm transparency | 126 |
| Data privacy | 123 |
| Mental health | 103 |
| Content moderation | 14 |
| National security | 13 |

## How it works

1. Searches LegiScan API with 20 keyword queries (`getSearchRaw`, 2000 results/page)
2. Compares `change_hash` against previous scrape — only fetches bills that actually changed
3. Writes three output files following the [DD_Day4 scraper architecture](https://github.com/jthirkield/dd_bill_scraper_example):
   - `data/legiscan_bills.json` — full dataset
   - `data/changelogs/` — what changed each run
   - `data/error_logs/` — any errors

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your LegiScan API key to .env (free at https://legiscan.com/legiscan)
python scraper.py
```

## Data attribution

Data provided by [LegiScan](https://legiscan.com/), licensed under [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
