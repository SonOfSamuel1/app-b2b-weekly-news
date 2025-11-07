"""Article filtering, deduplication, and canonicalization utilities."""
import re
import hashlib
from typing import Dict, List, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from difflib import SequenceMatcher
from datetime import datetime


class ArticleFilter:
    """Handles article filtering, deduplication, and URL canonicalization."""

    def __init__(
        self,
        allowed_domains: List[str],
        blocked_domains: List[str],
        similarity_threshold: float = 0.92
    ):
        """Initialize the article filter.

        Args:
            allowed_domains: List of allowed source domains
            blocked_domains: List of blocked source domains
            similarity_threshold: Threshold for considering titles duplicates (0-1)
        """
        self.allowed_domains = set(allowed_domains)
        self.blocked_domains = set(blocked_domains)
        self.similarity_threshold = similarity_threshold

    def filter_and_dedupe(
        self,
        articles: List[Dict],
        max_articles: int
    ) -> List[Dict]:
        """Filter and deduplicate a list of articles.

        Args:
            articles: List of article dictionaries
            max_articles: Maximum number of articles to return

        Returns:
            Filtered and deduplicated list of articles
        """
        # Step 1: Canonicalize URLs
        for article in articles:
            if 'link' in article:
                article['canonical_url'] = self.canonicalize_url(article['link'])
                article['url_hash'] = self._hash_url(article['canonical_url'])

        # Step 2: Filter by domain policy
        filtered = [a for a in articles if self._is_allowed_domain(a)]
        print(f"After domain filtering: {len(filtered)} articles")

        # Step 3: Remove URL duplicates
        seen_urls = set()
        url_unique = []
        for article in filtered:
            url_hash = article.get('url_hash', '')
            if url_hash and url_hash not in seen_urls:
                seen_urls.add(url_hash)
                url_unique.append(article)

        print(f"After URL deduplication: {len(url_unique)} articles")

        # Step 4: Remove near-duplicate titles
        title_unique = self._remove_duplicate_titles(url_unique)
        print(f"After title deduplication: {len(title_unique)} articles")

        # Step 5: Sort by publication date (newest first) and quality
        sorted_articles = self._sort_by_quality(title_unique)

        # Step 6: Cap to max articles
        return sorted_articles[:max_articles]

    def canonicalize_url(self, url: str) -> str:
        """Canonicalize a URL by removing tracking parameters.

        Args:
            url: Original URL

        Returns:
            Canonicalized URL
        """
        if not url:
            return url

        # Parse URL
        parsed = urlparse(url)

        # Remove common tracking parameters
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid',
            'ref', 'source', 'campaign',
            '_ga', '_gl', 'mc_cid', 'mc_eid'
        }

        # Parse query string
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Filter out tracking parameters
        filtered_params = {
            k: v for k, v in query_params.items()
            if k.lower() not in tracking_params
        }

        # Rebuild query string
        new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''

        # Rebuild URL
        canonical = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''  # Remove fragment
        ))

        return canonical

    def _hash_url(self, url: str) -> str:
        """Create a hash of a URL for deduplication.

        Args:
            url: URL to hash

        Returns:
            SHA256 hash of the URL
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def _is_allowed_domain(self, article: Dict) -> bool:
        """Check if an article's source domain is allowed.

        Args:
            article: Article dictionary

        Returns:
            True if domain is allowed, False otherwise
        """
        url = article.get('link', '')
        if not url:
            return False

        try:
            domain = urlparse(url).netloc.lower()

            # Remove www prefix for matching
            domain = domain.replace('www.', '')

            # Check blocklist first
            for blocked in self.blocked_domains:
                if blocked in domain:
                    return False

            # If allowlist is empty, allow all (except blocked)
            if not self.allowed_domains:
                return True

            # Check allowlist
            for allowed in self.allowed_domains:
                if allowed in domain:
                    return True

            # Also allow the source_url domain if present
            source_url = article.get('source_url', '')
            if source_url:
                source_domain = urlparse(source_url).netloc.lower().replace('www.', '')
                for allowed in self.allowed_domains:
                    if allowed in source_domain:
                        return True

            return False

        except Exception as e:
            print(f"Error parsing domain: {e}")
            return False

    def _remove_duplicate_titles(self, articles: List[Dict]) -> List[Dict]:
        """Remove articles with near-duplicate titles.

        Args:
            articles: List of article dictionaries

        Returns:
            List with duplicate titles removed
        """
        unique = []
        seen_titles = []

        for article in articles:
            title = article.get('title', '').lower().strip()
            if not title:
                continue

            # Check against all seen titles
            is_duplicate = False
            for seen_title in seen_titles:
                similarity = self._title_similarity(title, seen_title)
                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(article)
                seen_titles.append(title)

        return unique

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles.

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score between 0 and 1
        """
        # Normalize titles
        t1 = self._normalize_title(title1)
        t2 = self._normalize_title(title2)

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, t1, t2).ratio()

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison.

        Args:
            title: Original title

        Returns:
            Normalized title
        """
        # Convert to lowercase
        normalized = title.lower()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        # Remove common prefixes/suffixes
        patterns = [
            r'^breaking:\s*',
            r'^exclusive:\s*',
            r'^update:\s*',
            r'\s*-\s*[^-]*$',  # Remove source suffix
        ]
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

        return normalized.strip()

    def _sort_by_quality(self, articles: List[Dict]) -> List[Dict]:
        """Sort articles by quality and recency.

        Args:
            articles: List of article dictionaries

        Returns:
            Sorted list of articles
        """
        def quality_score(article: Dict) -> tuple:
            """Calculate quality score for sorting."""
            # Parse publication date
            pub_date_str = article.get('pubDate', '')
            try:
                if pub_date_str:
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                else:
                    pub_date = datetime.min
            except:
                pub_date = datetime.min

            # Prefer reputable sources
            source_priority = 0
            source_name = article.get('source_name', '').lower()
            reputable_sources = [
                'reuters', 'bloomberg', 'wall street journal', 'financial times',
                'business wire', 'pr newswire', 'globe newswire'
            ]
            for idx, rep_source in enumerate(reputable_sources):
                if rep_source in source_name:
                    source_priority = len(reputable_sources) - idx
                    break

            # Return tuple for sorting (higher values first, except date which is reversed)
            return (-pub_date.timestamp(), -source_priority)

        return sorted(articles, key=quality_score)
