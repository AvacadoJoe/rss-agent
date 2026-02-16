import os
import time
import logging
from typing import List, Dict

# NEW SDK IMPORT
from google import genai
from google.genai import types

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
    Generates a digest from a list of articles using Gemini 2.0 Flash (New SDK).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return "Error: Missing API Key"

    if not articles:
        logger.warning("No articles provided for digest generation")
        return "No articles to process."

    # Initialize Client (New SDK Style)
    client = genai.Client(api_key=api_key)

    # Format Input
    articles_text = ""
    for i, a in enumerate(articles, 1):
        priority_tag = "[PRIMARY AUTHORITY - TRANSPORT CANADA]" if a.get('is_primary') else ""
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

    # Retry Logic
    max_retries = 3
    retry_delay = 10

    for attempt in range(1, max_retries + 1):
        try:
            # New SDK Call
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.1 # Low temperature for factual reporting
                ),
                contents=[prompt]
            )
            
            logger.info("Successfully generated digest")
            return response.text

        except Exception as e:
            # The new SDK handles errors differently, but generic Exception catching 
            # is safe for the top-level loop.
            logger.warning(f"Gemini API Error (Attempt {attempt}/{max_retries}): {e}")
            if "429" in str(e) or "ResourceExhausted" in str(e):
                logger.info(f"Rate limit hit. Sleeping {retry_delay}s...")
                time.sleep(retry_delay)
            elif attempt < max_retries:
                time.sleep(retry_delay)
            else:
                return f"Error generating digest: {e}"

    return "Error: Rate limit exceeded after retries."
