"""Constants and configuration defaults for the weekly news automation."""

# API Configuration
DEFAULT_NEWS_API_TIMEOUT = 10  # seconds
DEFAULT_NEWS_API_MAX_RETRIES = 3
DEFAULT_NEWS_MAX_PAGES = 5

# Article Processing
DEFAULT_DAYS_LOOKBACK = 7
DEFAULT_ARTICLES_PER_ACCOUNT = 12
DEFAULT_ARTICLES_FETCH_MULTIPLIER = 2  # Fetch 2x articles before filtering
TITLE_SIMILARITY_THRESHOLD = 0.92  # 92% similarity for deduplication
MAX_TITLE_LENGTH = 200  # chars
MAX_DESCRIPTION_LENGTH = 200  # chars

# Claude API
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_MAX_TOKENS = 900
CLAUDE_TEMPERATURE = 0.3
CLAUDE_REQUEST_TIMEOUT = 60  # seconds

# Slack API
SLACK_MESSAGE_SIZE_LIMIT = 30000  # bytes (stay under 40KB limit)
SLACK_MAX_LINKS_PER_ACCOUNT = 12
SLACK_REQUEST_TIMEOUT = 30  # seconds

# Persistence
DYNAMODB_TTL_DAYS = 90  # Days to keep seen URLs
S3_ARCHIVE_PREFIX = "briefs"

# Timeouts
HTTP_REQUEST_TIMEOUT = 30  # seconds for generic HTTP requests
LAMBDA_EXECUTION_BUFFER = 60  # seconds to reserve before timeout

# Allowed News Domains
REPUTABLE_NEWS_SOURCES = [
    'businesswire.com',
    'prnewswire.com',
    'globenewswire.com',
    'reuters.com',
    'bloomberg.com',
    'wsj.com',
    'techcrunch.com',
    'theverge.com',
    'zdnet.com',
    'venturebeat.com',
    'axios.com',
    'forbes.com',
    'ft.com',
    'cnbc.com',
    'marketwatch.com'
]

# Blocked News Domains (stock tickers, spam)
BLOCKED_NEWS_SOURCES = [
    'seekingalpha.com',
    'fool.com',
    'benzinga.com',
    'stocktwits.com',
    'finance.yahoo.com',
    'investing.com',
    'marketbeat.com',
    'gurufocus.com',
    'tipranks.com'
]

# Press Wire Services for Keyword Search
PRESS_WIRE_DOMAINS = [
    'businesswire.com',
    'prnewswire.com',
    'globenewswire.com',
    'reuters.com',
    'bloomberg.com'
]

# Source Priority for Sorting (higher = better)
SOURCE_PRIORITY_MAP = {
    'reuters': 7,
    'bloomberg': 7,
    'wall street journal': 6,
    'financial times': 6,
    'business wire': 5,
    'pr newswire': 5,
    'globe newswire': 5,
    'wsj': 6,
    'ft': 6
}

# Environment Variable Names
ENV_SLACK_CHANNEL_ID = 'SLACK_CHANNEL_ID'
ENV_TIMEZONE = 'TIMEZONE'
ENV_DAYS_LOOKBACK = 'DAYS_LOOKBACK'
ENV_ARTICLES_PER_ACCOUNT = 'ARTICLES_PER_ACCOUNT'
ENV_ANTHROPIC_MODEL = 'ANTHROPIC_MODEL'
ENV_CONFIG_S3_BUCKET = 'CONFIG_S3_BUCKET'
ENV_CONFIG_S3_KEY = 'CONFIG_S3_KEY'
ENV_USE_DYNAMODB = 'USE_DYNAMODB'
ENV_DYNAMODB_TABLE = 'DYNAMODB_TABLE'
ENV_ARCHIVE_S3_BUCKET = 'ARCHIVE_S3_BUCKET'

# Secret Names
SECRET_NEWS_DATA_API_KEY = 'NEWS_DATA_API_KEY'
SECRET_ANTHROPIC_API_KEY = 'ANTHROPIC_API_KEY'
SECRET_SLACK_BOT_TOKEN = 'SLACK_BOT_TOKEN'

# Default Timezone
DEFAULT_TIMEZONE = 'America/New_York'
