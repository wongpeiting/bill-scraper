# Social Media Bill Scraper

A database of federal and state legislation related to social media regulation across US state legislatures, DC and the US Congress. Sourced from the [LegiScan API](https://legiscan.com/) and updated weekly via GitHub Actions.

**903 bills | 49 states | 59 fields per bill | 867 with full text extracted**

## What it tracks

Bills matching 20 keyword searches: TikTok, ByteDance, social media, social networking, online platform, age verification, parental consent, children online safety, screen time, digital addiction, content moderation, online safety, online harms, deepfake, artificial intelligence, influencer, algorithm, and more.

Each bill record includes: sponsor with party and district, co-sponsors, status, committee, full action history, vote tallies, bill text (extracted from PDF via NaturalPDF or HTML via BeautifulSoup), amendments, subjects, and auto-classified topic categories.

## Current dataset (as of June 15, 2026)

| Topic | Bills |
|---|---|
| Youth safety | 372 |
| General | 251 |
| School restrictions | 160 |
| Deepfakes/AI | 149 |
| Data privacy | 108 |
| Algorithm transparency | 70 |
| Mental health | 45 |
| Content moderation | 13 |
| National security | 7 |

| Status | Bills |
|---|---|
| Introduced | 617 |
| Passed | 106 |
| Engrossed | 85 |
| Failed | 80 |
| Enrolled | 9 |
| Vetoed | 6 |

| Primary sponsor party | Bills |
|---|---|
| Democrat | 445 |
| Republican | 397 |
| Nonpartisan | 10 |
| Independent | 1 |

## Methodology

**Scope:** The scraper collects bills from all 50 state legislatures, DC and the US Congress via the LegiScan API, covering every chamber (house and senate) across active sessions. The current dataset spans the 2024-2026 sessions. It runs weekly via GitHub Actions, building a longitudinal record of social media legislation.

**Technique:** The scraper queries LegiScan's pull API (`getSearchRaw`) with 20 keyword searches covering social media, TikTok, deepfakes, age verification, content moderation and related terms. The free-tier API allows 30,000 requests/month, so the scraper is built around minimising calls at every step: it uses `getSearchRaw` (which returns 2,000 results per page instead of 50 with `getSearch`), compares LegiScan's `change_hash` values against stored data so that unchanged bills are never re-fetched, and caches all API responses locally so the same request is never made twice. Bill text is extracted from PDFs via [NaturalPDF](https://jsoma.github.io/natural-pdf/) and from HTML via BeautifulSoup; when the API quota is exhausted, the scraper falls back to downloading bill text directly from state legislature websites, bypassing the API entirely. A typical weekly update uses approximately 25 API calls — 21 for searches and a handful of `getBill` calls for bills that actually changed — leaving the vast majority of the monthly quota untouched. 

**Data integrity:** Each bill contains 59 fields: identifiers, sponsors with party, committee, full action history, votes, amendments, bill text and subjects. Missing fields default to empty values to preserve a consistent schema. Duplicates are detected via LegiScan's unique `bill_id`; changes are detected via `change_hash` comparison, with field-by-field diffs logged to `data/changelogs/`. On error, the scraper falls back to the previous scrape's data so no records are lost. A relevance filter checks titles and descriptions against core terms to exclude false positives (e.g. sports wagering bills matching "age verification").

**Analysis:** Bills are classified into eight topic categories (youth safety, data privacy, deepfakes/AI, algorithm transparency, mental health, national security, content moderation, school restrictions) using keyword matching against each bill's title and description — for example, a bill containing "child," "minor" or "youth" is tagged as youth safety; one containing "deepfake" or "artificial intelligence" is tagged as deepfakes/AI. A bill can belong to multiple categories. Platform-specific tags (TikTok, Meta, Snapchat, YouTube, etc.) are assigned the same way when a company name appears in the title or description. Over time, the database will allow analysis of how topic priorities shift by state and year, whether passage rates differ by party and topic, how introduction spikes correlate with news events such as congressional hearings or court rulings, and whether states are copying each other's bill language.

## Output files

| File | Description |
|---|---|
| `data/legiscan_bills.json` | Full dataset with all bills and extracted text |
| `data/changelogs/YYYY-MM-DD.json` | What changed each scrape (additions, modifications) |
| `data/error_logs/YYYY-MM-DD.json` | Errors with tracebacks (only written if errors occur) |

## Setup

```bash
pip install -r requirements.txt
# Create .env with your LegiScan API key (free at https://legiscan.com/legiscan)
echo "LEGISCAN_API_KEY=your_key_here" > .env
python scraper.py
```

## Data attribution

Data provided by [LegiScan](https://legiscan.com/), licensed under [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
