"""Main Lambda handler for weekly account news automation."""
import json
import os
from datetime import datetime
from typing import Dict, List

from src.config import Config
from src.clients.newsdata_client import NewsdataClient
from src.clients.claude_client import ClaudeClient
from src.clients.slack_client import SlackClient
from src.utils.article_filter import ArticleFilter
from src.utils.persistence import DynamoDBPersistence, S3Archiver


def lambda_handler(event: Dict, context) -> Dict:
    """Main Lambda handler function.

    Args:
        event: Lambda event dictionary
        context: Lambda context object

    Returns:
        Response dictionary
    """
    print("=== Weekly Account News Automation Starting ===")
    print(f"Event: {json.dumps(event)}")

    # Load configuration
    config = Config()

    # Check for dry run mode
    dry_run = event.get('dry_run', False)
    if dry_run:
        print("*** DRY RUN MODE - Will not post to Slack ***")

    # Calculate run key for idempotency
    run_key = get_iso_week()
    print(f"Run key (ISO week): {run_key}")

    # Initialize clients
    newsdata_client = NewsdataClient(
        api_key=config.secrets['NEWS_DATA_API_KEY']
    )

    claude_client = ClaudeClient(
        api_key=config.secrets['ANTHROPIC_API_KEY'],
        model=config.anthropic_model
    )

    slack_client = SlackClient(
        bot_token=config.secrets['SLACK_BOT_TOKEN']
    )

    # Initialize article filter
    article_filter = ArticleFilter(
        allowed_domains=config.allowed_domains,
        blocked_domains=config.blocked_domains
    )

    # Initialize persistence (optional)
    persistence = None
    if config.use_dynamodb:
        persistence = DynamoDBPersistence(config.dynamodb_table)
        print(f"Using DynamoDB persistence: {config.dynamodb_table}")

    # Initialize archiver (optional)
    archiver = None
    archive_bucket = os.environ.get('ARCHIVE_S3_BUCKET', '')
    if archive_bucket:
        archiver = S3Archiver(archive_bucket)
        print(f"Using S3 archiving: {archive_bucket}")

    # Load account configurations
    try:
        accounts = config.load_accounts()
        print(f"Loaded {len(accounts)} accounts")
    except Exception as e:
        print(f"Error loading accounts: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to load accounts: {str(e)}'})
        }

    # Process each account
    all_summaries = []
    stats = {
        'accounts_processed': 0,
        'total_articles_fetched': 0,
        'total_articles_kept': 0,
        'total_tokens_used': 0,
        'errors': []
    }

    for account in accounts:
        try:
            print(f"\n{'='*60}")
            print(f"Processing: {account.company}")
            print(f"{'='*60}")

            summary = process_account(
                account=account,
                newsdata_client=newsdata_client,
                claude_client=claude_client,
                article_filter=article_filter,
                persistence=persistence,
                config=config
            )

            if summary:
                all_summaries.append(summary)
                stats['accounts_processed'] += 1
                stats['total_articles_fetched'] += summary.get('articles_fetched', 0)
                stats['total_articles_kept'] += summary.get('article_count', 0)
                stats['total_tokens_used'] += summary.get('tokens_used', 0)

        except Exception as e:
            error_msg = f"Error processing {account.company}: {str(e)}"
            print(error_msg)
            stats['errors'].append(error_msg)

    # Post to Slack
    print(f"\n{'='*60}")
    print("Posting to Slack...")
    print(f"{'='*60}")

    slack_result = slack_client.post_weekly_brief(
        channel_id=config.slack_channel_id,
        summaries=all_summaries,
        dry_run=dry_run
    )

    # Archive the brief (optional)
    if archiver and not dry_run and slack_result.get('success'):
        archive_content = json.dumps({
            'run_key': run_key,
            'timestamp': datetime.utcnow().isoformat(),
            'summaries': all_summaries,
            'stats': stats
        }, indent=2)
        archiver.archive_brief(run_key, archive_content)

    # Build response
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Accounts processed: {stats['accounts_processed']}/{len(accounts)}")
    print(f"Total articles fetched: {stats['total_articles_fetched']}")
    print(f"Total articles kept: {stats['total_articles_kept']}")
    print(f"Total tokens used: {stats['total_tokens_used']}")
    print(f"Slack post success: {slack_result.get('success', False)}")
    if stats['errors']:
        print(f"Errors: {len(stats['errors'])}")
        for error in stats['errors']:
            print(f"  - {error}")

    return {
        'statusCode': 200 if slack_result.get('success') else 500,
        'body': json.dumps({
            'run_key': run_key,
            'dry_run': dry_run,
            'stats': stats,
            'slack_result': slack_result
        })
    }


def process_account(
    account,
    newsdata_client: NewsdataClient,
    claude_client: ClaudeClient,
    article_filter: ArticleFilter,
    persistence,
    config: Config
) -> Dict:
    """Process a single account.

    Args:
        account: AccountConfig object
        newsdata_client: Newsdata.io client
        claude_client: Claude client
        article_filter: Article filter
        persistence: Optional persistence layer
        config: Configuration object

    Returns:
        Summary dictionary
    """
    # Fetch articles
    articles = newsdata_client.fetch_articles_for_account(
        company=account.company,
        website=account.website,
        keywords=account.keywords,
        newsroom=account.newsroom,
        days_lookback=config.days_lookback,
        max_articles=config.articles_per_account * 3,  # Fetch more, filter down
        timezone=config.timezone
    )

    articles_fetched = len(articles)
    print(f"Fetched {articles_fetched} raw articles")

    if not articles:
        print("No articles found, generating empty summary")
        return claude_client.summarize_articles(account.company, [])

    # Filter unseen articles if persistence is enabled
    if persistence:
        unseen_articles = persistence.filter_unseen(account.company, articles)
        print(f"After filtering seen URLs: {len(unseen_articles)} unseen articles")
        articles = unseen_articles

    # Filter and deduplicate
    filtered_articles = article_filter.filter_and_dedupe(
        articles=articles,
        max_articles=config.articles_per_account
    )

    print(f"After filtering and deduplication: {len(filtered_articles)} articles")

    # Summarize with Claude
    summary = claude_client.summarize_articles(
        company=account.company,
        articles=filtered_articles
    )

    # Mark articles as seen if persistence is enabled
    if persistence and filtered_articles:
        url_hashes = [a.get('url_hash', '') for a in filtered_articles if a.get('url_hash')]
        pub_dates = [a.get('pubDate', '') for a in filtered_articles if a.get('url_hash')]
        persistence.mark_as_seen(account.company, url_hashes, pub_dates)

    # Add metadata
    summary['articles_fetched'] = articles_fetched

    return summary


def get_iso_week() -> str:
    """Get current ISO week identifier.

    Returns:
        ISO week string (e.g., "2024-W12")
    """
    now = datetime.utcnow()
    iso_calendar = now.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"
