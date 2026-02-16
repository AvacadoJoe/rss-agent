"""
LLM Processor Module
Handles digest generation directly from raw articles using Google Gemini API.
"""

import os
import time
import logging
from typing import List, Dict, Optional

import google.generativeai as genai
from google.api_core import exceptions

logger = logging.getLogger(__name__)

# System Prompt tailored for Technical/Maintenance focus
SYSTEM_INSTRUCTION = """
You are a Technical Aviation Safety Specialist.

Your Task:
Review the provided regulatory documents and incident reports to generate a "BD-700 Airworthiness & Safety Digest."

Scope:
- Aircraft: Bombardier BD-700-1A10 and BD-700-1A11 (Global Express, XRS, 5000, 6000).
- EXCLUDE: Global 7500, Global 8000.
- EXCLUDE: Sales, marketing, orders, deliveries, stock prices.

Prioritization:
1. **CRITICAL:** Transport Canada (TCCA) Airworthiness Directives (ADs). These usually start with "CF-". Since Bombardier is Canadian, these are the primary source documents.
2. **Secondary:** FAA or EASA ADs.
3. **Tertiary:** Operational incidents.

Format:
- **Transport Canada Directives** (If any exist, list these FIRST).
- **FAA/EASA Updates**
- **Operational Incidents**

If a document is an AD, explicitly state the AD number (e.g., CF-2024-XX) and effective date.
If no technical issues are found, state: "No new airworthiness directives or safety incidents reported."
"""

def generate_digest(articles: List[Dict]) -> str:
    """
    Generates a digest from a list of articles using Gemini 2.0 Flash.
    """
    # 1. Configure API
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return "Error: Missing API Key"
    
    genai.configure(api_key=api_key)

    if not articles:
        logger.warning("No articles provided for digest generation")
        return "No articles to process."

    # 2. Initialize Model
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_INSTRUCTION
    )

    # 3. Format Input
    # We highlight if an article is from the Primary Authority (Transport Canada)
    articles_text = ""
    for i, a in enumerate(articles, 1):
        priority_tag = "[PRIMARY AUTHORITY - TRANSPORT CANADA]" if a.get('is_primary') else ""
        
        # Handle various key names depending on where the article came from
        title = a.get('title', 'No Title')
        link = a.get('link', a.get('url', '#'))
        summary = a.get('summary', a.get('rss_summary', 'No summary'))
        
        articles_text += (
            f"Article {i} {priority_tag}\n"
            f"Title: {title}\n"
            f"Source: {link}\n"
            f"Summary: {summary}\n"
            f"---\n"
        )

    prompt = f"Analyze these reports for BD-700 airworthiness issues:\n\n{articles_text}"

    logger.info(f"Generating digest for {len(articles)} articles using Gemini 2.0 Flash")

    # 4. Generate with Retry Logic
    max_retries = 3
    retry_delay = 10

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            logger.info("Successfully generated digest")
            return response.text

        except exceptions.ResourceExhausted as e:
            # This catches 429 / Quota Exceeded errors
            logger.warning(f"Rate limit hit (Attempt {attempt}/{max_retries}). Sleeping {retry_delay}s...")
            time.sleep(retry_delay)
            
        except Exception as e:
            # Catch generic errors (like 500s or connection issues)
            logger.error(f"Gemini API Error (Attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                return f"Error generating digest: {e}"

    return "Error: Rate limit exceeded after retries."

# --- Test Function ---
if __name__ == "__main__":
    # Simple test to verify the module works standalone
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()

    test_articles = [
        {
            "title": "Transport Canada AD CF-2026-05",
            "link": "https://tc.gc.ca/example",
            "summary": "Inspection of flap actuators required for BD-700-1A10.",
            "is_primary": True
        },
        {
            "title": "Bombardier Quarterly Results",
            "link": "https://example.com",
            "summary": "Profits are up 5%.",
            "is_primary": False
        }
    ]

    print("Testing Gemini Processor...")
    result = generate_digest(test_articles)
    print("\n--- Result ---\n")
    print(result)
