"""Slack client for posting weekly news briefs."""
import json
import requests
from typing import Dict, List, Optional


class SlackClient:
    """Client for posting messages to Slack."""

    def __init__(self, bot_token: str):
        """Initialize the Slack client.

        Args:
            bot_token: Slack bot token
        """
        self.bot_token = bot_token
        self.base_url = "https://slack.com/api"

    def post_weekly_brief(
        self,
        channel_id: str,
        summaries: List[Dict],
        dry_run: bool = False
    ) -> Dict:
        """Post the weekly brief to Slack.

        Args:
            channel_id: Slack channel ID
            summaries: List of account summaries
            dry_run: If True, don't actually post to Slack

        Returns:
            Dictionary with posting results
        """
        if not summaries:
            print("No summaries to post")
            return {'success': False, 'error': 'No summaries provided'}

        # Build the main message
        message_blocks = self._build_message_blocks(summaries)

        # Check message size
        message_json = json.dumps(message_blocks)
        message_size = len(message_json)
        print(f"Message size: {message_size} bytes")

        if dry_run:
            print("\n=== DRY RUN - Would post to Slack ===")
            print(f"Channel: {channel_id}")
            print(f"Number of accounts: {len(summaries)}")
            print(f"Message preview:")
            self._print_preview(summaries)
            return {
                'success': True,
                'dry_run': True,
                'message_size': message_size,
                'account_count': len(summaries)
            }

        # Post to Slack
        try:
            # Check if message needs threading due to size
            if message_size > 30000:  # Slack's limit is ~40KB, be safe
                return self._post_threaded(channel_id, summaries)
            else:
                return self._post_single(channel_id, message_blocks)

        except Exception as e:
            print(f"Error posting to Slack: {e}")
            return {'success': False, 'error': str(e)}

    def _build_message_blocks(self, summaries: List[Dict]) -> List[Dict]:
        """Build Slack message blocks for the brief.

        Args:
            summaries: List of account summaries

        Returns:
            List of Slack block dictionaries
        """
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📰 Top Accounts — Weekly Brief"
            }
        })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Updates from {len(summaries)} accounts"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Each account
        for idx, summary in enumerate(summaries):
            company = summary.get('company', 'Unknown Company')
            summary_text = summary.get('summary', '')
            links = summary.get('links', [])
            article_count = summary.get('article_count', 0)

            # Company header
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{company}*\n_{article_count} articles this week_"
                }
            })

            # Summary content
            if summary_text:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": summary_text
                    }
                })

            # Links section
            if links:
                links_text = self._format_links_for_slack(links)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Links:*\n{links_text}"
                    }
                })

            # Divider between accounts (except after last)
            if idx < len(summaries) - 1:
                blocks.append({"type": "divider"})

        return blocks

    def _format_links_for_slack(self, links: List[Dict]) -> str:
        """Format links for Slack markdown.

        Args:
            links: List of link dictionaries

        Returns:
            Formatted links string
        """
        formatted = []
        for link in links[:12]:  # Limit to 12 links
            title = link.get('title', 'Article')
            source = link.get('source', '')
            url = link.get('url', '')

            if url:
                formatted.append(f"• <{url}|{title}> — _{source}_")

        return "\n".join(formatted)

    def _post_single(self, channel_id: str, blocks: List[Dict]) -> Dict:
        """Post a single message to Slack.

        Args:
            channel_id: Slack channel ID
            blocks: Message blocks

        Returns:
            Response dictionary
        """
        url = f"{self.base_url}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": channel_id,
            "blocks": blocks
        }

        response = requests.post(url, headers=headers, json=payload)
        result = response.json()

        if result.get('ok'):
            print(f"Successfully posted to Slack (message ts: {result.get('ts')})")
            return {
                'success': True,
                'ts': result.get('ts'),
                'channel': channel_id
            }
        else:
            error = result.get('error', 'Unknown error')
            print(f"Slack API error: {error}")
            return {
                'success': False,
                'error': error
            }

    def _post_threaded(self, channel_id: str, summaries: List[Dict]) -> Dict:
        """Post as threaded messages when content is too large.

        Args:
            channel_id: Slack channel ID
            summaries: List of account summaries

        Returns:
            Response dictionary
        """
        # Post first account as main message
        first_summary = [summaries[0]]
        first_blocks = self._build_message_blocks(first_summary)

        main_result = self._post_single(channel_id, first_blocks)
        if not main_result.get('success'):
            return main_result

        thread_ts = main_result.get('ts')

        # Post remaining accounts as thread replies
        for summary in summaries[1:]:
            thread_blocks = self._build_message_blocks([summary])
            self._post_reply(channel_id, thread_ts, thread_blocks)

        return {
            'success': True,
            'threaded': True,
            'ts': thread_ts,
            'channel': channel_id,
            'account_count': len(summaries)
        }

    def _post_reply(self, channel_id: str, thread_ts: str, blocks: List[Dict]) -> Dict:
        """Post a reply in a thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Parent message timestamp
            blocks: Message blocks

        Returns:
            Response dictionary
        """
        url = f"{self.base_url}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": channel_id,
            "thread_ts": thread_ts,
            "blocks": blocks
        }

        response = requests.post(url, headers=headers, json=payload)
        return response.json()

    def _print_preview(self, summaries: List[Dict]) -> None:
        """Print a preview of the message.

        Args:
            summaries: List of account summaries
        """
        for summary in summaries[:3]:  # Show first 3
            company = summary.get('company', 'Unknown')
            article_count = summary.get('article_count', 0)
            summary_text = summary.get('summary', '')

            print(f"\n--- {company} ({article_count} articles) ---")
            if summary_text:
                # Print first 200 chars of summary
                preview = summary_text[:200]
                if len(summary_text) > 200:
                    preview += "..."
                print(preview)

        if len(summaries) > 3:
            print(f"\n... and {len(summaries) - 3} more accounts")
