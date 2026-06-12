#!/usr/bin/env python3
"""
LegiScan Social Media Bills Scraper
====================================
Scrapes federal and state legislature bills related to social media, TikTok, deepfakes, and online platform regulation using the LegiScan API.

Follows Bill Scraper Architecture:
  - Step 1: Load previous scrape data
  - Step 2: Extract data points function
  - Step 3: Search + change detection via change_hash
  - Step 4: Scrape with try/except, fallback to yesterday's data
  - Step 5: Write 3 output files (data, changelog, error log)

"""

######################## IMPORTS ########################

import os
import json
import hashlib
import datetime
import traceback
import requests
import time
from dotenv import load_dotenv


######################## CONFIGURATION ########################

load_dotenv()
API_KEY = os.getenv("LEGISCAN_API_KEY")

# Local cache directory for raw API responses
# LegiScan recommends caching to minimize query spend on replayability
CACHE_DIR = "data/api_cache"
API_BASE = "https://api.legiscan.com/"

DATA_FILE = "data/legiscan_bills.json"
TODAY_STR = datetime.date.today().isoformat()

# Search terms covering social media legislation topics
# Broader keyword universe per tutor's recommendation
SEARCH_QUERIES = [
    "TikTok",
    "ByteDance",
    '"social media"',
    '"social networking"',
    '"online platform"',
    '"recommendation system"',
    '"age verification"',
    '"parental consent"',
    '"children online safety"',
    '"youth online"',
    '"children online"',
    '"digital addiction"',
    '"screen time"',
    '"content moderation"',
    '"online safety"',
    '"online harms"',
    "deepfake",
    '"artificial intelligence" AND "social media"',
    '"influencer" AND "social media"',
    '"algorithm" AND "social media"',
]

# LegiScan status codes → human-readable labels
STATUS_MAP = {
    0: "N/A",
    1: "Introduced",
    2: "Engrossed",
    3: "Enrolled",
    4: "Passed",
    5: "Vetoed",
    6: "Failed",
}

# LegiScan party codes → labels
PARTY_MAP = {
    "D": "Democrat",
    "R": "Republican",
    "I": "Independent",
    "G": "Green",
    "L": "Libertarian",
    "N": "Nonpartisan",
}

# State abbreviation → full name
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "US": "US Congress",
}

# Keywords for auto-classifying bill topics
TOPIC_KEYWORDS = {
    "Youth safety": ["youth", "child", "children", "minor", "student", "kid", "teenager", "adolescent", "juvenile"],
    "Mental health": ["mental health", "addiction", "well-being", "wellbeing", "anxiety", "depression", "psychological"],
    "National security": ["national security", "foreign adversary", "foreign government", "espionage", "foreign-owned"],
    "Data privacy": ["privacy", "personal data", "data protection", "data collection", "user data", "biometric"],
    "Algorithm transparency": ["algorithm", "recommendation", "transparency", "algorithmic", "feed", "curation"],
    "Content moderation": ["content moderation", "harmful content", "remove content", "illegal content", "terms of service"],
    "Deepfakes/AI": ["deepfake", "deep fake", "artificial intelligence", "ai-generated", "synthetic media", "generative"],
    "School restrictions": ["school", "classroom", "education", "campus", "instruction", "k-12"],
}

# Relevance filter: bill title/description must contain at least one of these
# to avoid false positives (e.g. sports wagering bills matching "age verification")
RELEVANCE_TERMS = [
    # Platforms
    "social media", "social network", "online platform", "covered platform",
    "tiktok", "bytedance", "wechat", "facebook", "instagram", "snapchat",
    "youtube", "twitter", "app store",
    # Content / safety
    "deepfake", "deep fake", "content moderation", "online safety",
    "online harms", "internet safety", "digital safety", "digital wellness",
    "cyberbullying", "cyber bullying", "cyber-bullying",
    # Youth / age
    "age verification", "parental consent", "children online", "youth online",
    "screen time", "digital addiction", "screen-based",
    "access by minors", "minors online", "protect minors",
    # Tech regulation
    "algorithm", "recommendation system", "artificial intelligence",
    "influencer", "chatbot", "software application",
    # Privacy
    "data privacy", "consumer privacy", "personal data", "personal information",
    "biometric", "data protection", "data collection",
    # Internet / digital
    "internet website", "online service", "online marketplace",
    "electronic device", "wireless device", "digital device", "mobile device",
    "pornograph",
]


def is_relevant(title, description):
    """Check if a bill is actually about tech/social media regulation."""
    text = (title + " " + description).lower()
    return any(term in text for term in RELEVANCE_TERMS)


######################## API FUNCTIONS ########################

def _cache_key(operation, params):
    """Generate a cache filename from the API operation and params."""
    # Exclude the API key from the cache key
    cache_params = {k: v for k, v in sorted(params.items()) if k != "key"}
    raw = f"{operation}:{json.dumps(cache_params, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()


def api_request(operation, use_cache=False, **params):
    """Make a LegiScan API request with local JSON caching. 
    
    LegiScan recommends: 'local caching of JSON response to minimize spend on replayability.' Cached responses are stored in data/api_cache/ and replayed instead of burning a query when use_cache=True.
    """
    if not API_KEY:
        raise ValueError("LEGISCAN_API_KEY not set. Copy .env.example to .env and add your key.")

    # Check local cache first (for getBill responses that haven't changed)
    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{_cache_key(operation, params)}.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                return json.load(f)

    params["key"] = API_KEY
    params["op"] = operation
    response = requests.get(API_BASE, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "ERROR":
        msg = data.get("alert", {}).get("message", "Unknown API error")
        raise Exception(f"LegiScan API error: {msg}")

    # Cache the response locally
    if use_cache:
        with open(cache_file, "w") as f:
            json.dump(data, f)

    return data


def search_bills(query, year=2, page=1):
    """Search for bills matching a query using getSearchRaw.

    Uses getSearchRaw (2000 results/page) instead of getSearch (50/page) to minimize API calls. Returns bill_id, change_hash, title, state, relevance — everything needed for change detection.

    year: 1=current, 2=recent (last 2 years), 3=prior, 4=all
    """
    return api_request("getSearchRaw", query=query, year=year, page=page)


def get_bill(bill_id, use_cache=False):
    """Get full bill details by LegiScan bill_id.

    use_cache=True replays a cached response if available, avoiding a query spend for data we already downloaded.
    """
    return api_request("getBill", use_cache=use_cache, id=bill_id)


######################## CLASSIFICATION FUNCTIONS ########################

def classify_topics(title, description):
    """Auto-classify bill into topic categories based on keywords."""
    text = (title + " " + description).lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)
    return topics if topics else ["General"]


def detect_platform(title, description):
    """Detect if bill targets a specific platform."""
    text = (title + " " + description).lower()
    platforms = []
    if "tiktok" in text:
        platforms.append("TikTok")
    if "bytedance" in text:
        platforms.append("ByteDance")
    if "facebook" in text or "instagram" in text or "meta platforms" in text:
        platforms.append("Meta")
    if "snapchat" in text:
        platforms.append("Snapchat")
    if "youtube" in text:
        platforms.append("YouTube")
    if "twitter" in text or "x.com" in text:
        platforms.append("X/Twitter")
    if "wechat" in text:
        platforms.append("WeChat")
    if "reddit" in text:
        platforms.append("Reddit")
    if "telegram" in text:
        platforms.append("Telegram")
    if "discord" in text:
        platforms.append("Discord")
    if "whatsapp" in text:
        platforms.append("WhatsApp")
    return ", ".join(platforms) if platforms else "General"


######################## DATA EXTRACTION ########################

def extract_data_points(bill_data, search_terms_matched):
    """Extract and flatten bill data from the getBill API response.

    This is the equivalent of the tutor's extract_data_points() function, but working with structured API JSON instead of HTML/BeautifulSoup.
    """
    bill = bill_data["bill"]
    fields = {}

    # Change detection hash (provided by LegiScan API)
    fields["content_hash"] = bill["change_hash"]

    # Core identifiers
    fields["legiscan_bill_id"] = bill["bill_id"]
    fields["bill_number"] = bill["bill_number"]
    fields["state"] = bill["state"]
    fields["state_name"] = STATE_NAMES.get(bill["state"], bill["state"])
    fields["bill_id"] = f"{bill['state']} {bill['bill_number']}"
    fields["bill_type"] = bill.get("bill_type", "")
    fields["body"] = bill.get("body", "")

    # Description
    fields["title"] = bill["title"]
    fields["description"] = bill["description"]

    # Status
    fields["status"] = STATUS_MAP.get(bill.get("status", 0), str(bill.get("status", "")))
    fields["status_code"] = bill.get("status", 0)
    fields["status_date"] = bill.get("status_date", "")
    fields["completed"] = bill.get("completed", 0)

    # URLs
    fields["url"] = bill.get("url", "")
    fields["state_link"] = bill.get("state_link", "")

    # Session info (API returns {} or dict, never seen as [])
    session = bill.get("session", {})
    if isinstance(session, dict):
        fields["session_id"] = bill.get("session_id", "")
        fields["session_title"] = session.get("session_title", "")
        fields["session_years"] = f"{session.get('year_start', '')}-{session.get('year_end', '')}"
    else:
        fields["session_id"] = bill.get("session_id", "")
        fields["session_title"] = ""
        fields["session_years"] = ""

    # Sponsors
    sponsors = bill.get("sponsors", [])
    fields["num_sponsors"] = len(sponsors)
    if sponsors:
        prime = next((s for s in sponsors if s.get("sponsor_order", 0) == 1), sponsors[0])
        fields["prime_sponsor"] = prime.get("name", "").strip()
        fields["prime_sponsor_party"] = PARTY_MAP.get(prime.get("party", ""), prime.get("party", ""))
        fields["prime_sponsor_party_code"] = prime.get("party", "")
        fields["prime_sponsor_role"] = prime.get("role", "")
        fields["prime_sponsor_district"] = prime.get("district", "")
        fields["prime_sponsor_people_id"] = prime.get("people_id", "")
    else:
        fields["prime_sponsor"] = ""
        fields["prime_sponsor_party"] = ""
        fields["prime_sponsor_party_code"] = ""
        fields["prime_sponsor_role"] = ""
        fields["prime_sponsor_district"] = ""
        fields["prime_sponsor_people_id"] = ""

    fields["sponsors"] = [
        {
            "name": s.get("name", "").strip(),
            "party": PARTY_MAP.get(s.get("party", ""), s.get("party", "")),
            "party_code": s.get("party", ""),
            "role": s.get("role", ""),
            "district": s.get("district", ""),
            "sponsor_type": "Primary" if s.get("sponsor_order", 0) == 1 else "Co-Sponsor",
        }
        for s in sponsors
    ]

    # Committee (API returns {} when present, [] when empty)
    committee = bill.get("committee", {})
    if isinstance(committee, dict):
        fields["committee"] = committee.get("name", "")
        fields["committee_chamber"] = committee.get("chamber", "")
    else:
        fields["committee"] = ""
        fields["committee_chamber"] = ""

    # History / actions
    history = bill.get("history", [])
    fields["history"] = history
    fields["num_actions"] = len(history)
    if history:
        fields["date_introduced"] = history[0].get("date", "")
        fields["last_action"] = history[-1].get("action", "")
        fields["last_action_date"] = history[-1].get("date", "")
    else:
        fields["date_introduced"] = ""
        fields["last_action"] = ""
        fields["last_action_date"] = ""

    # Progress timeline
    fields["progress"] = bill.get("progress", [])

    # Subjects (some old bills have False instead of string for subject_name)
    subjects = bill.get("subjects", [])
    fields["subjects"] = [str(s.get("subject_name", "")) for s in subjects]
    fields["subjects_str"] = "; ".join(fields["subjects"])

    # Bill texts (URLs to actual text documents)
    texts = bill.get("texts", [])
    fields["texts"] = texts
    fields["num_text_versions"] = len(texts)
    if texts:
        latest = texts[-1]
        fields["latest_text_url"] = latest.get("url", "")
        fields["latest_text_state_link"] = latest.get("state_link", "")
        fields["latest_text_date"] = latest.get("date", "")
        fields["latest_text_type"] = latest.get("type", "")
    else:
        fields["latest_text_url"] = ""
        fields["latest_text_state_link"] = ""
        fields["latest_text_date"] = ""
        fields["latest_text_type"] = ""

    # Votes
    votes = bill.get("votes", [])
    fields["votes"] = votes
    fields["num_votes"] = len(votes)
    if votes:
        latest_vote = votes[-1]
        fields["latest_vote_date"] = latest_vote.get("date", "")
        fields["latest_vote_desc"] = latest_vote.get("desc", "")
        fields["latest_vote_yea"] = latest_vote.get("yea", 0)
        fields["latest_vote_nay"] = latest_vote.get("nay", 0)
        fields["latest_vote_passed"] = latest_vote.get("passed", 0)
    else:
        fields["latest_vote_date"] = ""
        fields["latest_vote_desc"] = ""
        fields["latest_vote_yea"] = ""
        fields["latest_vote_nay"] = ""
        fields["latest_vote_passed"] = ""

    # Amendments
    amendments = bill.get("amendments", [])
    fields["amendments"] = amendments
    fields["num_amendments"] = len(amendments)

    # Related bills (SAST)
    sasts = bill.get("sasts", [])
    fields["related_bills"] = [
        {"type": s.get("type", ""), "bill_number": s.get("sast_bill_number", "")}
        for s in sasts
    ]

    # Calendar / hearings
    calendar = bill.get("calendar", [])
    fields["calendar"] = calendar
    fields["num_hearings"] = len(calendar)

    # Classification (auto-generated)
    fields["topic_categories"] = classify_topics(bill["title"], bill["description"])
    fields["platform_specific"] = detect_platform(bill["title"], bill["description"])
    fields["search_terms_matched"] = search_terms_matched

    # Metadata
    fields["scraped_date"] = TODAY_STR

    return fields


######################## SCRAPING LOGIC ########################


def run_scraper():
    """Main scraping logic following the DD_Day4/Day5 architecture."""

    if not API_KEY:
        print("ERROR: No API key found.")
        print("1. Get a free key at https://legiscan.com/legiscan")
        print("2. Copy .env.example to .env")
        print("3. Add your key to the .env file")
        return

    ######### STEP ONE #########
    # Check for data history

    os.makedirs("data/changelogs", exist_ok=True)
    os.makedirs("data/error_logs", exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    if os.path.exists(DATA_FILE):
        print("Found existing dataset. Loading history...")
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
        # Handle both wrapped format {"bills": [...]} and flat list [...]
        yesterdays_list = raw.get("bills", raw) if isinstance(raw, dict) else raw
        # Map by LegiScan bill_id for instant lookup
        old_data_map = {item["legiscan_bill_id"]: item for item in yesterdays_list}
        print(f"  Loaded {len(old_data_map)} bills from previous scrape.")
    else:
        print("No existing dataset found. Running baseline scrape...")
        old_data_map = {}

    ######### STEP TWO #########
    # Set up change log and error log

    changelog = {
        "date": TODAY_STR,
        "additions": [],
        "deletions": [],
        "modifications": [],
    }
    error_log = {
        "date": TODAY_STR,
        "errors": [],
    }

    ######### STEP THREE #########
    # Search LegiScan for bills matching our keywords
    # Collect all unique bill_ids with their change_hashes
    #
    # API budget strategy:
    #   - Uses getSearchRaw (2000 results/page) instead of getSearch (50/page)
    #   - Initial run (no data file): year=2 (recent sessions) for baseline
    #   - Daily updates (data file exists): year=1 (current year only)
    #   - Change_hash comparison skips unchanged bills (no getBill needed)
    #   - Budget: ~25 search + ~50 getBill = ~75 calls/day = ~2,250/month

    # Always use year=2 (recent sessions). year=1 ("current session") actually
    # returns MORE results than year=2 for many states since sessions span 2 years.
    search_year = 2
    print(f"\n--- Searching for social media bills (year={search_year}) ---")
    all_found_bills = {}  # legiscan_bill_id -> {change_hash, search_terms, title, state}
    api_calls = 0

    for query in SEARCH_QUERIES:
        page = 1
        while True:
            try:
                time.sleep(0.5)  # polite rate limiting
                results = search_bills(query, year=search_year, page=page)
                api_calls += 1
                search_data = results.get("searchresult", {})
                summary = search_data.get("summary", {})

                # getSearchRaw returns {"results": [{bill_id, change_hash, relevance}, ...]}
                bill_list = search_data.get("results", [])
                result_count = len(bill_list)

                for bill in bill_list:
                    bid = bill["bill_id"]
                    if bid not in all_found_bills:
                        all_found_bills[bid] = {
                            "change_hash": bill.get("change_hash", ""),
                            "search_terms": [query],
                            "relevance": bill.get("relevance", 0),
                        }
                    else:
                        if query not in all_found_bills[bid]["search_terms"]:
                            all_found_bills[bid]["search_terms"].append(query)

                page_total = summary.get("page_total", 1)
                count = summary.get("count", 0)
                print(f"  '{query}' — page {page}/{page_total} — {result_count} results (total: {count})")

                if page >= page_total:
                    break
                page += 1

            except Exception as e:
                print(f"  Search error for '{query}' page {page}: {e}")
                error_log["errors"].append({
                    "bill_id": f"SEARCH:{query}",
                    "url": "",
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc().splitlines()[-3:],
                })
                break

    print(f"\nFound {len(all_found_bills)} unique bills across all search terms.")
    print(f"Search phase used {api_calls} API calls.")

    ######### STEP FOUR #########
    # Process each bill — check for changes, scrape if new/modified
    # Saves incrementally every 50 bills so data is available while running

    SAVE_EVERY = 50  # write to disk every N bills

    def save_progress(bills_so_far):
        """Incremental save — write current data to disk so nothing is lost."""
        output = {
            "attribution": "Data provided by LegiScan (legiscan.com), licensed under Creative Commons Attribution 4.0 (CC BY 4.0)",
            "scraped_date": TODAY_STR,
            "bill_count": len(bills_so_far),
            "bills": sorted(bills_so_far, key=lambda x: x["bill_id"]),
        }
        with open(DATA_FILE, "w") as f:
            json.dump(output, f, indent=2)

    print("\n--- Processing bills ---")
    todays_bills = []
    new_count = 0
    changed_count = 0
    unchanged_count = 0
    error_count = 0
    processed_count = 0

    for i, (bill_id, info) in enumerate(all_found_bills.items()):
        yesterdays_item = old_data_map.get(bill_id)

        try:
            if bill_id not in old_data_map:
                # NEW BILL — fetch full details
                time.sleep(0.5)
                bill_data = get_bill(bill_id)
                api_calls += 1
                bill_dict = extract_data_points(bill_data, info["search_terms"])
                # Relevance filter: skip false positives
                if not is_relevant(bill_dict["title"], bill_dict["description"]):
                    continue
                todays_bills.append(bill_dict)
                changelog["additions"].append({
                    "bill_id": bill_dict["bill_id"],
                    "state": bill_dict["state"],
                    "title": bill_dict["title"],
                    "status": bill_dict["status"],
                })
                new_count += 1
            else:
                # EXISTING BILL — check change_hash
                if yesterdays_item["content_hash"] == info["change_hash"]:
                    # No change — keep yesterday's data
                    todays_bills.append(yesterdays_item)
                    unchanged_count += 1
                else:
                    # CHANGED — re-fetch full details
                    time.sleep(0.5)
                    bill_data = get_bill(bill_id)
                    api_calls += 1
                    bill_dict = extract_data_points(bill_data, info["search_terms"])
                    todays_bills.append(bill_dict)

                    # Log meaningful changes (field-by-field diff)
                    meaningful_changes = {}
                    for key, value in bill_dict.items():
                        if yesterdays_item.get(key) != value:
                            meaningful_changes[key] = {
                                "from": yesterdays_item.get(key),
                                "to": value,
                            }
                    if meaningful_changes:
                        changelog["modifications"].append({
                            "bill_id": bill_dict["bill_id"],
                            "changes": meaningful_changes,
                        })
                    changed_count += 1

        except Exception as e:
            print(f"  Error on bill {bill_id}: {e}")
            # Fallback to yesterday's data if available
            if yesterdays_item:
                todays_bills.append(yesterdays_item)
            error_log["errors"].append({
                "bill_id": str(bill_id),
                "error_type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc().splitlines()[-3:],
            })
            error_count += 1

        # Incremental save every SAVE_EVERY bills
        processed_count += 1
        if processed_count % SAVE_EVERY == 0:
            save_progress(todays_bills)
            print(f"  Progress: {i+1}/{len(all_found_bills)} bills — {new_count} new, {changed_count} changed, {unchanged_count} unchanged — saved to disk")

    # Check for bills in old data that are no longer in search results
    # (Bills don't get "deleted" from legislatures, but they may fall
    # out of our search results. Keep them in the dataset.)
    current_ids = set(all_found_bills.keys())
    for old_id, old_item in old_data_map.items():
        if old_id not in current_ids:
            todays_bills.append(old_item)

    print(f"\n--- Results ---")
    print(f"  New bills:       {new_count}")
    print(f"  Changed bills:   {changed_count}")
    print(f"  Unchanged bills: {unchanged_count}")
    print(f"  Errors:          {error_count}")
    print(f"  Total in dataset: {len(todays_bills)}")
    print(f"  Total API calls: {api_calls}")

    ######### STEP FIVE #########
    # Final write of all output files

    # 1. Main data file (final save — also saved incrementally during Step 4)
    save_progress(todays_bills)
    print(f"\nWrote {len(todays_bills)} bills to {DATA_FILE}")

    # 2. Change log (only if changes exist)
    if changelog["additions"] or changelog["deletions"] or changelog["modifications"]:
        changelog_file = f"data/changelogs/{TODAY_STR}.json"
        with open(changelog_file, "w") as f:
            json.dump(changelog, f, indent=2)
        print(f"Wrote changelog to {changelog_file}")
        print(f"  {len(changelog['additions'])} additions, {len(changelog['modifications'])} modifications")

    # 3. Error log (only if errors occurred)
    if error_log["errors"]:
        error_file = f"data/error_logs/{TODAY_STR}.json"
        with open(error_file, "w") as f:
            json.dump(error_log, f, indent=2)
        print(f"Wrote {len(error_log['errors'])} errors to {error_file}")

    print("\nScrape done!")


if __name__ == "__main__":
    run_scraper()
