"""Newsdata.io API client with advanced query strategies."""
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.constants import (
    DEFAULT_NEWS_API_TIMEOUT,
    DEFAULT_NEWS_API_MAX_RETRIES,
    DEFAULT_NEWS_MAX_PAGES,
    PRESS_WIRE_DOMAINS,
    BLOCKED_NEWS_SOURCES,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class NewsdataClient:
    """Client for interacting with Newsdata.io API."""

    BASE_URL = "https://newsdata.io/api/1/news"

    def __init__(
        self,
        api_key: str,
        timeout: int = DEFAULT_NEWS_API_TIMEOUT,
        max_retries: int = DEFAULT_NEWS_API_MAX_RETRIES
    ):
        """Initialize the Newsdata client.

        Args:
            api_key: Newsdata.io API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    def fetch_articles_for_account(
        self,
        company: str,
        website: str,
        keywords: List[str],
        newsroom: Optional[str],
        days_lookback: int,
        max_articles: int,
        timezone: str = 'America/New_York'
    ) -> List[Dict]:
        """Fetch articles for a specific account using three query strategies.

        Args:
            company: Company name
            website: Company website domain
            keywords: List of relevant keywords
            newsroom: Optional newsroom URL
            days_lookback: Number of days to look back
            max_articles: Maximum articles to fetch per account
            timezone: Timezone for date calculations

        Returns:
            List of article dictionaries
        """
        from_date, to_date = self._get_date_window(days_lookback, timezone)

        # Fix: Ensure at least 1 article per strategy
        articles_per_strategy = max(1, max_articles // 3)
        logger.info(f"[{company}] Fetching {articles_per_strategy} articles per strategy")

        # Parallel execution of all three strategies
        all_articles = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}

            # Strategy 1: Direct mentions in headlines
            future1 = executor.submit(
                self._fetch_direct_mentions,
                company, from_date, to_date, articles_per_strategy
            )
            futures[future1] = "direct_mentions"

            # Strategy 2: Official press (company domain and newsroom)
            if website or newsroom:
                future2 = executor.submit(
                    self._fetch_official_press,
                    company, website, newsroom, from_date, to_date, articles_per_strategy
                )
                futures[future2] = "official_press"

            # Strategy 3: Press wires and partner activity
            future3 = executor.submit(
                self._fetch_press_wires,
                company, keywords, from_date, to_date, articles_per_strategy
            )
            futures[future3] = "press_wires"

            # Collect results
            for future in as_completed(futures):
                strategy = futures[future]
                try:
                    articles = future.result()
                    all_articles.extend(articles)
                    logger.info(f"[{company}] {strategy}: {len(articles)} articles")
                except Exception as e:
                    logger.error(f"[{company}] Error in {strategy}: {e}")

        logger.info(f"[{company}] Total fetched: {len(all_articles)} articles")
        return all_articles

    def _fetch_direct_mentions(
        self,
        company: str,
        from_date: str,
        to_date: str,
        max_results: int
    ) -> List[Dict]:
        """Fetch articles with direct company mentions in title."""
        params = {
            'q': f'"{company}"',
            'language': 'en',
            'from_date': from_date,
            'to_date': to_date,
            'prioritydomain': 'top'
        }
        return self._paginated_fetch(params, max_results)

    def _fetch_official_press(
        self,
        company: str,
        website: str,
        newsroom: Optional[str],
        from_date: str,
        to_date: str,
        max_results: int
    ) -> List[Dict]:
        """Fetch articles from company's official domains."""
        domains = [website] if website else []

        if newsroom:
            # Fix: Properly extract domain using urlparse
            try:
                parsed = urlparse(newsroom)
                newsroom_domain = parsed.netloc or newsroom.split('/')[0]
                # Remove www prefix
                newsroom_domain = newsroom_domain.replace('www.', '')
                if newsroom_domain and newsroom_domain != website:
                    domains.append(newsroom_domain)
            except Exception as e:
                logger.warning(f"[{company}] Failed to parse newsroom URL {newsroom}: {e}")

        if not domains:
            logger.warning(f"[{company}] No domains for official press search")
            return []

        params = {
            'domainurl': ','.join(domains),
            'language': 'en',
            'from_date': from_date,
            'to_date': to_date
        }
        return self._paginated_fetch(params, max_results)

    def _fetch_press_wires(
        self,
        company: str,
        keywords: List[str],
        from_date: str,
        to_date: str,
        max_results: int
    ) -> List[Dict]:
        """Fetch articles from press wires with keyword matching."""
        # Build query with keywords and company name
        keyword_terms = ' OR '.join(keywords[:6])  # Limit to avoid overly long queries
        query = f'({keyword_terms}) AND "{company}"'

        params = {
            'q': query,
            'language': 'en',
            'from_date': from_date,
            'to_date': to_date,
            'domainurl': ','.join(PRESS_WIRE_DOMAINS),
            'excludedomain': ','.join(BLOCKED_NEWS_SOURCES)
        }
        return self._paginated_fetch(params, max_results)

    def _paginated_fetch(
        self,
        params: Dict,
        max_results: int
    ) -> List[Dict]:
        """Fetch articles with pagination support."""
        articles = []
        next_page = None
        page_count = 0

        while len(articles) < max_results and page_count < DEFAULT_NEWS_MAX_PAGES:
            try:
                # Add pagination token if available
                if next_page:
                    params['page'] = next_page

                response = self._make_request(params)

                if not response:
                    logger.warning("Empty response from API")
                    break

                # Fix: Validate response structure
                if not isinstance(response, dict):
                    logger.error(f"Invalid response type: {type(response)}")
                    break

                if response.get('status') == 'success':
                    results = response.get('results', [])
                    if not isinstance(results, list):
                        logger.error("Results is not a list")
                        break

                    articles.extend(results)

                    # Check for next page
                    next_page = response.get('nextPage')
                    if not next_page:
                        break

                    page_count += 1
                    # Only sleep when actually paginating
                elif response.get('status') == 'error':
                    error_msg = response.get('results', {}).get('message', 'Unknown error')
                    logger.error(f"API error: {error_msg}")
                    break
                else:
                    logger.warning(f"Unexpected response status: {response.get('status')}")
                    break

            except Exception as e:
                logger.error(f"Error during pagination: {e}")
                break

        return articles[:max_results]

    def _make_request(self, params: Dict) -> Optional[Dict]:
        """Make an API request with retry logic."""
        # Add API key to params
        request_params = params.copy()
        request_params['apikey'] = self.api_key

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=request_params,
                    timeout=self.timeout
                )

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Handle server errors
                if response.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {response.status_code}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except ValueError as e:
                # JSON decode error
                logger.error(f"Failed to parse response JSON: {e}")
                break

        logger.error("All retry attempts exhausted")
        return None

    def _get_date_window(
        self,
        days_lookback: int,
        timezone: str
    ) -> Tuple[str, str]:
        """Calculate the date window for queries.

        Args:
            days_lookback: Number of days to look back
            timezone: Timezone for calculations

        Returns:
            Tuple of (from_date, to_date) in ISO format
        """
        try:
            tz = pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {timezone}. Using UTC")
            tz = pytz.UTC

        now = datetime.now(tz)
        from_datetime = now - timedelta(days=days_lookback)

        # Convert to UTC for API
        from_date_utc = from_datetime.astimezone(pytz.UTC)
        to_date_utc = now.astimezone(pytz.UTC)

        # Format as ISO date strings
        from_date = from_date_utc.strftime('%Y-%m-%d')
        to_date = to_date_utc.strftime('%Y-%m-%d')

        return from_date, to_date
