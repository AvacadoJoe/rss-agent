"""
RSS Feed Fetcher
Retrieves technical aviation articles, filters for BD-700/E-11A relevance,
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

# STRICT Technical Keywords for E-11A BACN and related entities
BD700_KEYWORDS = [
    # Platform & Payload
    "e-11", "e-11a", "e11a",
    "bacn", "battlefield airborne communications node",
    
    # Units & Bases
    "430th expeditionary", "430 eecs",
    "472 ecs", "472nd ecs",
    "319th reconnaissance", "319 rw", # Wing at Grand Forks
    "grand forks afb", "grand forks",
    "hanscom afb", # Program Office
    
    # Base Airframe & Technical
    "bd-700", "bd700",
    "global express", "global 6000",
    "airworthiness", "directive", "ad",
    "service bulletin", "sb",
    "maintenance", "safety", "incident", "faa", "easa", "transport canada",

    # Key Companies & Topics
    "northrop grumman",
    "cae inc",
    "flight training", "simulator"
]

# Technical & Regulatory Feeds
RSS_FEEDS = [
    # --- 1. OFFICIAL USAF & DOD FEEDS (NEW) ---
    
    # U.S. Department of Defense (Official News)
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=145",

    # U.S. Air Force (Official Top News)
    "https://www.af.mil/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=1",

    # Air Combat Command (ACC) - The MAJCOM for E-11A
    "https://www.acc.af.mil/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=2",

    # Grand Forks AFB - Home of the E-11A Mission
    "https://www.grandforks.af.mil/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=264",

    # Hanscom AFB - Home of the BACN Program Office (Contracts/Acquisition)
    "https://www.hanscom.af.mil/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=286",

    # --- 2. E-11A / BACN SPECIFIC FEEDS ---
    
    # Google News Custom Search: E-11A OR BACN
    "https://news.google.com/rss/search?q=E-11A+OR+%22Battlefield+Airborne+Communications+Node%22+OR+BACN&hl=en-US&gl=US&ceid=US:en",
    
    # DVIDS (Defense Visual Information Distribution Service) - Tag: E-11A
    "https://www.dvidshub.net/rss/news/tags/e-11a",

    # --- 3. DEFENSE & AVIATION NEWS ---

    # Air & Space Forces Magazine
    "https://www.airandspaceforces.com/feed/",
    
    # The Aviationist
    "https://theaviationist.com/feed/",
    
    # Defense News - Air Warfare
    "https://www.defensenews.com/arc/outboundfeeds/rss/category/air/",

    # Breaking Defense - Air Domain
    "https://breakingdefense.com/category/domain/air/feed/",

    # --- 4. INDUSTRY & TRAINING FEEDS ---

    # Northrop Grumman
    "https://news.northropgrumman.com/rss.xml",

    # CAE Inc.
    "https://www.cae.com/rss/press-releases/",

    # Defense News - Training & Simulation
    "https://www.defensenews.com/arc/outboundfeeds/rss/category/training-simulation/",

    # Halldale Group (Military Simulation & Training)
    "https://www.halldale.com/feed",

    # --- 5. REGULATORY & SAFETY FEEDS ---

    # Transport Canada - Civil Aviation Recent ADs
    "https://wwwapps.tc.gc.ca/Saf-Sec-Sur/2/awd-cn/rss-feed-ech.aspx?lang=eng",
    
    # FAA Airworthiness Directives
    "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bterm%5D=Bombardier+BD-700+Airworthiness",
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
                unique_id = entry.get('id', entry.get('link', entry.get('title')))
                
                # 2. DUPLICATE CHECK
                if unique_id in sent_ids:
                    continue 

                # 3. DATE CHECK
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if published_dt < CUTOFF_DATE:
                        continue 
                
                # 4. KEYWORD & CONTENT FILTERING
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '#')
                content_text = (title + " " + summary).lower()
                
                # Exclusion (No 7500/8000/Sales/Financials)
                if any(x in content_text for x in ["7500", "8000", "order", "delivery", "stock", "quarterly"]):
                    continue

                # Inclusion (Must match target keywords)
                if any(keyword in content_text for keyword in BD700_KEYWORDS):
                    
                    # Flag if this is from a Primary Military/Regulatory Source
                    is_primary = any(x in feed_url for x in ["tc.gc.ca", "dvidshub", "af.mil", "defense.gov"]) or "CF-" in title
                    
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
    
    return articles, new_ids_found, sent_ids

if __name__ == "__main__":
    # Simple test to verify fetching works
    logging.basicConfig(level=logging.INFO)
    print("Testing RSS Fetcher...")
    arts, new_ids, _ = fetch_and_filter_articles()
    print(f"Retrieved {len(arts)} articles.")
    for a in arts:
        print(f"- {a['title']} ({'PRIMARY' if a['is_primary'] else 'Secondary'})")
