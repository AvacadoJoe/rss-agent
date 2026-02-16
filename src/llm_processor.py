"""
LLM Processor Module
Handles digest generation directly from raw articles using OpenAI-compatible APIs.
"""

import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

from openai import OpenAI
from openai import RateLimitError, APIError, APIConnectionError

logger = logging.getLogger(__name__)


class LLMProcessor:
    """Processes articles using LLM via OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        import os

        if model is None:
            model = os.getenv("LLM_MODEL")

        if base_url:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers={
                    "HTTP-Referer": "https://github.com/your-username/rss-digest",
                    "X-Title": "BD700 Actionability Filter",
                },
            )
            logger.info(
                f"LLM Processor initialized with model: {model}, base_url: {base_url}"
            )
        else:
            self.client = OpenAI(api_key=api_key)
            logger.info(f"LLM Processor initialized with model: {model}")

        self.model = model
        self.total_tokens_used = 0

    def generate_digest_from_articles(
        self,
        articles: List[Dict],
        prompt_template: str,
        date_range: str,
    ) -> Optional[str]:
        if not articles:
            logger.warning("No articles provided for digest generation")
            return None

        article_list = self._format_raw_articles_for_prompt(articles)

        prompt = prompt_template.format(
            article_count=len(articles),
            article_list=article_list,
            date_range=date_range,
        )

        logger.info(f"Generating digest for {len(articles)} articles")

        MAX_RETRIES = 3
        RETRY_DELAY_SECONDS = 3

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"LLM request attempt {attempt}/{MAX_RETRIES}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an operational intelligence filter. "
                                "Only produce content that is directly actionable. "
                                "Ignore commentary, opinion, or non-operational analysis."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=0.0,
                    max_tokens=2500,
                )

                if hasattr(response, "usage") and response.usage:
                    tokens = response.usage.total_tokens
                    self.total_tokens_used += tokens
                    logger.info(f"Tokens used: {tokens}")

                digest_html = response.choices[0].message.content.strip()
                logger.info("Successfully generated digest")
                return digest_html

            except (APIConnectionError, RateLimitError) as e:
                logger.warning(
                    f"LLM attempt {attempt} failed due to transient error: {e}"
                )
                if attempt < MAX_RETRIES:
                    logger.info(
                        f"Sleeping {RETRY_DELAY_SECONDS}s before retry"
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error("All LLM retry attempts exhausted")
                    return None

            except APIError as e:
                logger.error(f"Fatal API error: {e}")
                return None

            except Exception as e:
                logger.error(f"Unexpected error during digest generation: {e}")
                return None

        return None

    def _format_raw_articles_for_prompt(self, articles: List[Dict]) -> str:
        formatted = []

        for i, article in enumerate(articles, 1):
            pub_date = article.get("published_date")
            if isinstance(pub_date, datetime):
                pub_date_str = pub_date.strftime("%Y-%m-%d")
            else:
                pub_date_str = str(pub_date) if pub_date else "Unknown"

            article_text = f"""
Article {i}:
Title: {article.get('title', 'Unknown')}
URL: {article.get('url', 'Unknown')}
Feed: {article.get('feed_category', 'Unknown')}
Published: {pub_date_str}
Summary: {article.get('rss_summary', 'No summary available')}
"""
            formatted.append(article_text.strip())

        return "\n\n---\n\n".join(formatted)

    def get_token_usage_summary(self) -> Dict:
        return {"total_tokens": self.total_tokens_used}


def test_llm(api_key: str, base_url: Optional[str] = None) -> None:
    processor = LLMProcessor(api_key, base_url=base_url)

    print("\n=== LLM Processor Test ===")
    print(f"Using model: {processor.model}")

    test_articles = [
        {
            "title": "Europe's economy faces headwinds from energy crisis",
            "rss_summary": (
                "Rising energy costs and supply chain disruptions continue "
                "to challenge European economies."
            ),
            "feed_category": "Europe",
            "published_date": datetime(2025, 1, 20),
            "url": "https://example.com/article1",
        }
    ]

    from config.feeds import DIGEST_GENERATION_PROMPT

    result = processor.generate_digest_from_articles(
        test_articles,
        DIGEST_GENERATION_PROMPT,
        "Jan 15–21, 2025",
    )

    if result:
        print("\nDigest Generated Successfully!")
        print(f"Length: {len(result)} characters")
    else:
        print("\nDigest generation failed")

    print("\nToken Usage:", processor.get_token_usage_summary())


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    assert api_key, "OPENROUTER_API_KEY not set"

    test_llm(api_key, base_url)
