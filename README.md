# Social Media Bill Scraper

Tracks federal and state legislation related to social media regulation across all 50 US states using the [LegiScan API](https://legiscan.com/). This repo makes an API call for the scope (with 59 fields per bill) every three days via GitHub Actions. 

## What it tracks

Bills matching 20 keyword queries: TikTok, ByteDance, social media, online platform, age verification, parental consent, screen time, content moderation, deepfake, algorithm, and more.

Each bill includes: sponsor, party, status, committee, full action history, vote tallies, bill text URLs, amendments, and auto-classified topic categories.

## Topic categories

| Topic (as of June 11) | Bills |
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
3. Writes three output files following Jon Thirkield's scraper architecture - [DD_Day4 scraper architecture](https://github.com/jthirkield/dd_bill_scraper_example):
   - `data/legiscan_bills.json` — full dataset
   - `data/changelogs/` — what changed each run
   - `data/error_logs/` — any errors

## Setup

```bash
pip install -r requirements.txt
cp .env
python scraper.py
```

## Data attribution

Data provided by [LegiScan](https://legiscan.com/), licensed under [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).