"""Newsdata.io API client with advanced query strategies."""
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
import pytz


class NewsdataClient:
    """Client for interacting with Newsdata.io API."""

    BASE_URL = "https://newsdata.io/api/1/news"

    def __init__(self, api_key: str, timeout: int = 10, max_retries: int = 3):
        """Initialize the Newsdata client.

        Args:
            api_key: Newsdata.io API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
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

        all_articles = []
        articles_per_strategy = max_articles // 3 + 1

        # Strategy 1: Direct mentions in headlines
        print(f"[{company}] Fetching direct mentions...")
        direct_articles = self._fetch_direct_mentions(
            company, from_date, to_date, articles_per_strategy
        )
        all_articles.extend(direct_articles)
        print(f"[{company}] Found {len(direct_articles)} direct mentions")

        # Strategy 2: Official press (company domain and newsroom)
        if website or newsroom:
            print(f"[{company}] Fetching official press...")
            press_articles = self._fetch_official_press(
                company, website, newsroom, from_date, to_date, articles_per_strategy
            )
            all_articles.extend(press_articles)
            print(f"[{company}] Found {len(press_articles)} official press articles")

        # Strategy 3: Press wires and partner activity
        print(f"[{company}] Fetching press wires...")
        wire_articles = self._fetch_press_wires(
            company, keywords, from_date, to_date, articles_per_strategy
        )
        all_articles.extend(wire_articles)
        print(f"[{company}] Found {len(wire_articles)} press wire articles")

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
        domains = [website]
        if newsroom:
            # Extract domain from newsroom URL if it's different
            newsroom_domain = newsroom.replace('https://', '').replace('http://', '').split('/')[0]
            if newsroom_domain != website:
                domains.append(newsroom_domain)

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

        # Allowed press wire domains
        allowed_domains = [
            'businesswire.com',
            'prnewswire.com',
            'globenewswire.com',
            'reuters.com',
            'bloomberg.com'
        ]

        # Domains to exclude
        excluded_domains = [
            'seekingalpha.com',
            'fool.com',
            'benzinga.com',
            'stocktwits.com',
            'finance.yahoo.com'
        ]

        params = {
            'q': query,
            'language': 'en',
            'from_date': from_date,
            'to_date': to_date,
            'domainurl': ','.join(allowed_domains),
            'excludedomain': ','.join(excluded_domains)
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
        max_pages = 5  # Safety limit

        while len(articles) < max_results and page_count < max_pages:
            try:
                # Add pagination token if available
                if next_page:
                    params['page'] = next_page

                response = self._make_request(params)

                if response and response.get('status') == 'success':
                    results = response.get('results', [])
                    articles.extend(results)

                    # Check for next page
                    next_page = response.get('nextPage')
                    if not next_page:
                        break

                    page_count += 1
                    time.sleep(0.2)  # Small delay between pages
                else:
                    break

            except Exception as e:
                print(f"Error during pagination: {e}")
                break

        return articles[:max_results]

    def _make_request(self, params: Dict) -> Optional[Dict]:
        """Make an API request with retry logic."""
        params['apikey'] = self.api_key

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.timeout
                )

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    print(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Handle server errors
                if response.status_code >= 500:
                    wait_time = 2 ** attempt
                    print(f"Server error {response.status_code}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                print(f"Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

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
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        from_datetime = now - timedelta(days=days_lookback)

        # Convert to UTC for API
        from_date_utc = from_datetime.astimezone(pytz.UTC)
        to_date_utc = now.astimezone(pytz.UTC)

        # Format as ISO date strings
        from_date = from_date_utc.strftime('%Y-%m-%d')
        to_date = to_date_utc.strftime('%Y-%m-%d')

        return from_date, to_date
