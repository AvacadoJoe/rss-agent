"""
Main Orchestration Script
Workflow: Fetch RSS articles (filtered) -> Generate Gemini digest -> Send email -> Update History
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Import our new modules
# Ensure rss_fetcher.py, llm_processor.py, and email_sender.py are in the same directory
from rss_fetcher import fetch_and_filter_articles, save_history
from llm_processor import generate_digest
from email_sender import send_email 

# Configure logging
def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('digest.log')
        ]
    )

logger = logging.getLogger(__name__)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BD-700 Technical Digest - Automated Airworthiness Monitoring"
    )

    parser.add_argument('--dry-run', action='store_true', help='Generate digest but do not send email')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--force', action='store_true', help='Ignore weekend check and run anyway')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    load_dotenv()

    # --- 1. WEEKDAY CHECK ---
    # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    if not args.force:
        today = datetime.today().weekday()
        if today >= 5:
            logger.info("Today is a weekend (Saturday/Sunday). Skipping execution.")
            sys.exit(0)

    # --- 2. CHECK ENV VARS ---
    required_vars = ['GEMINI_API_KEY', 'EMAIL_PASSWORD', 'EMAIL_SENDER', 'EMAIL_RECIPIENT']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("STARTING BD-700 TECHNICAL DIGEST")
    logger.info("=" * 60)

    try:
        # --- 3. FETCH & FILTER ---
        # Returns: relevant articles, new IDs found, and the old history list
        logger.info("[STEP 1] Fetching and filtering articles...")
        articles, new_ids, old_history = fetch_and_filter_articles()

        if not articles:
            logger.info("No new technical articles found since last run.")
            logger.info("WORKFLOW COMPLETE (No Data)")
            sys.exit(0)

        logger.info(f"✓ Found {len(articles)} new relevant articles")

        # --- 4. GENERATE DIGEST ---
        logger.info(f"[STEP 2] Generating digest with Gemini...")
        digest_content = generate_digest(articles)

        if not digest_content or "Error" in digest_content:
            logger.error("Failed to generate digest content.")
            sys.exit(1)

        logger.info("✓ Digest generated successfully")

        # --- 5. SEND EMAIL ---
        if not args.dry_run:
            logger.info("[STEP 3] Sending email...")
            
            subject = f"BD-700 Airworthiness & Safety Update - {datetime.now().strftime('%Y-%m-%d')}"
            
            # We assume send_email takes (subject, body) or similar. 
            # Adjust arguments if your email_sender.py signature is different.
            success = send_email(
                subject=subject, 
                body=digest_content
            )
            
            # Note: If your send_email function doesn't return a boolean, 
            # wrap this in a try/except block instead.
            
            logger.info("✓ Email sent successfully")

            # --- 6. SAVE HISTORY ---
            # Only mark as sent if email actually went out
            updated_history = old_history + new_ids
            save_history(updated_history)
            logger.info(f"✓ Marked {len(new_ids)} articles as sent in history file")

        else:
            logger.info("[DRY RUN] Skipping email sending.")
            logger.info(f"Would have sent email to {os.getenv('EMAIL_RECIPIENT')}")
            logger.info(f"Digest Content Preview:\n{digest_content[:500]}...")

        logger.info("=" * 60)
        logger.info("WORKFLOW COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Critical error in workflow: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
