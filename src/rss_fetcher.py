"""
RSS Feed Fetcher
Retrieves technical aviation articles, filters for BD-700 relevance,
and handles deduplication using a local history file.
"""

import feedparser
import logging
import json
import os
import time
from datetime import datetime
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
HISTORY_FILE = "sent_history.json"
# Strict cutoff: Only articles published on or after Feb 15, 2026
CUTOFF_DATE = datetime(2026, 2, 15)

# STRICT Technical Keywords (Legacy BD-700 only)
BD700_KEYWORDS = [
    "bd-700", "bd700",
    "global express", 
    "global 5000", 
    "global 6000",
    "xrs",
    "airworthiness", "directive", "ad",
    "service bulletin", "sb",
    "maintenance", "safety", "incident", "faa", "easa", "transport canada"
]

# Technical & Regulatory Feeds
RSS_FEEDS = [
    # Transport Canada - Civil Aviation Recent ADs (Primary Source)
    "https://wwwapps.tc.gc.ca/Saf-Sec-Sur/2/awd-cn/rss-feed-ech.aspx?lang=eng",
    # FAA Airworthiness Directives (filtered via Federal Register)
    "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bterm%5D=Bombardier+BD-700+Airworthiness",
    # EASA Airworthiness Directives
    "https://www.easa.europa.eu/en/rss/ad",
    # Aviation Herald (Incidents/Accidents)
    "https://avherald.com/h?opt=0&f=0"
]

def load_history() -> List[str]:
    """Loads the list of previously sent article IDs."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return []

def save_history(sent_ids: List[str]) -> None:
    """Saves the updated list of sent article IDs."""
    try:
        # Keep file size manageable (last 1000 IDs)
        trimmed_ids = sent_ids[-1000:] 
        with open(HISTORY_FILE, 'w') as f:
            json.dump(trimmed_ids, f)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")

def fetch_and_filter_articles() -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """
    Fetches articles, filters by date (>= Feb 15, 2026), 
    checks for duplicates, and filters by keywords.

    Returns:
        Tuple containing:
        1. List of relevant article dictionaries
        2. List of new IDs found in this run
        3. List of old history IDs (for appending later)
    """
    articles = []
    sent_ids = load_history()
    new_ids_found = []
    
    logger.info(f"Fetching articles... (Cutoff: {CUTOFF_DATE.strftime('%Y-%m-%d')})")

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # 1. IDENTIFY UNIQUE ID
                # Use GUID if available, otherwise Link, otherwise Title
                unique_id = entry.get('id', entry.get('link', entry.get('title')))
                
                # 2. DUPLICATE CHECK
                if unique_id in sent_ids:
                    continue 

                # 3. DATE CHECK
                # feedparser returns time.struct_time, convert to datetime
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if published_dt < CUTOFF_DATE:
                        continue # Skip old articles
                
                # 4. KEYWORD & CONTENT FILTERING
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '#')
                content_text = (title + " " + summary).lower()
                
                # Exclusion (No 7500/8000/Sales/Financials)
                if any(x in content_text for x in ["7500", "8000", "order", "delivery", "stock", "quarterly"]):
                    continue

                # Inclusion (Must match BD-700 keywords)
                if any(keyword in content_text for keyword in BD700_KEYWORDS):
                    
                    # Flag if this is from the State of Design (Canada)
                    is_primary = "tc.gc.ca" in feed_url or "CF-" in title
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'published': entry.get('published', str(datetime.now())),
                        'is_primary': is_primary,
                        'id': unique_id
                    })
                    
                    new_ids_found.append(unique_id)

        except Exception as e:
            logger.error(f"Error fetching {feed_url}: {e}")

    logger.info(f"Found {len(articles)} new relevant articles.")
    
    # Return the articles, the new IDs to save later, and the old history
    return articles, new_ids_found, sent_ids

if __name__ == "__main__":
    # Simple test to verify fetching works
    logging.basicConfig(level=logging.INFO)
    print("Testing RSS Fetcher...")
    arts, new_ids, _ = fetch_and_filter_articles()
    print(f"Retrieved {len(arts)} articles.")
    for a in arts:
        print(f"- {a['title']} ({'PRIMARY' if a['is_primary'] else 'Secondary'})")
