"""Claude AI client for article summarization."""
import anthropic
from typing import Dict, List


class ClaudeClient:
    """Client for summarizing articles using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        """Initialize the Claude client.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def summarize_articles(
        self,
        company: str,
        articles: List[Dict]
    ) -> Dict[str, any]:
        """Summarize a list of articles for a company.

        Args:
            company: Company name
            articles: List of article dictionaries

        Returns:
            Dictionary with summary sections and metadata
        """
        if not articles:
            return {
                'company': company,
                'summary': self._generate_empty_summary(),
                'article_count': 0,
                'links': []
            }

        # Build the prompt
        prompt = self._build_prompt(company, articles)

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=900,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract the summary text
            summary_text = message.content[0].text

            # Format links
            links = self._format_links(articles)

            return {
                'company': company,
                'summary': summary_text,
                'article_count': len(articles),
                'links': links,
                'tokens_used': message.usage.input_tokens + message.usage.output_tokens
            }

        except Exception as e:
            print(f"Error summarizing articles for {company}: {e}")
            return {
                'company': company,
                'summary': f"Error generating summary: {str(e)}",
                'article_count': len(articles),
                'links': self._format_links(articles),
                'error': str(e)
            }

    def _build_prompt(self, company: str, articles: List[Dict]) -> str:
        """Build the prompt for Claude.

        Args:
            company: Company name
            articles: List of article dictionaries

        Returns:
            Formatted prompt string
        """
        # Build article list
        article_list = []
        for idx, article in enumerate(articles, 1):
            title = article.get('title', 'No title')
            source = article.get('source_name', 'Unknown source')
            pub_date = article.get('pubDate', '')
            url = article.get('link', '')

            # Format publication date
            if pub_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    pub_date_fmt = dt.strftime('%b %d, %Y')
                except:
                    pub_date_fmt = pub_date
            else:
                pub_date_fmt = 'Date unknown'

            article_list.append(
                f"{idx}. **{title}**\n"
                f"   Source: {source} | {pub_date_fmt}\n"
                f"   URL: {url}"
            )

            # Add description if available
            description = article.get('description', '')
            if description:
                # Truncate long descriptions
                if len(description) > 200:
                    description = description[:197] + '...'
                article_list.append(f"   Summary: {description}")

            article_list.append("")  # Blank line

        articles_text = "\n".join(article_list)

        # Build the prompt
        prompt = f"""You are generating a weekly sales intelligence brief for account executives. You will summarize recent news about {company} based on the articles below.

**Instructions:**
1. Group the information into these exact sections (only include sections that have content):
   - **Products/Launches**: New products, features, or services
   - **Customers/Partners**: New customers, partnerships, integrations, or case studies
   - **Exec & Hiring**: Leadership changes, key hires, organizational announcements
   - **Funding/M&A**: Funding rounds, acquisitions, or financial milestones
   - **Risks/Controversies**: Lawsuits, security incidents, outages, or negative press
   - **Regulatory**: Compliance updates, policy changes, or regulatory filings

2. For each section:
   - Write 1-3 concise bullets
   - Keep each bullet under 25 words
   - Include concrete numbers, dates, and names when available
   - Focus on what matters to an AE preparing for a call

3. End with a section called **Talk track:** containing 2 bullets that suggest conversation starters or angles for an AE

4. If there's no material news in a category, skip that section entirely

**Articles about {company}:**

{articles_text}

**Now generate the brief:**"""

        return prompt

    def _format_links(self, articles: List[Dict]) -> List[Dict]:
        """Format articles as link references.

        Args:
            articles: List of article dictionaries

        Returns:
            List of formatted link dictionaries
        """
        links = []
        for article in articles:
            title = article.get('title', 'No title')
            source = article.get('source_name', 'Unknown source')
            url = article.get('link', '')

            if url:
                links.append({
                    'title': title,
                    'source': source,
                    'url': url
                })

        return links

    def _generate_empty_summary(self) -> str:
        """Generate a summary for when there are no articles.

        Returns:
            Empty summary message
        """
        return "**No material items this week.**\n\nNo significant news coverage found for this account in the past 7 days."
