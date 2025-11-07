"""Configuration management for the weekly news automation."""
import os
import json
import yaml
import boto3
from typing import Dict, List, Optional
from dataclasses import dataclass

from src.constants import (
    DEFAULT_DAYS_LOOKBACK,
    DEFAULT_ARTICLES_PER_ACCOUNT,
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_TIMEZONE,
    REPUTABLE_NEWS_SOURCES,
    BLOCKED_NEWS_SOURCES,
    ENV_SLACK_CHANNEL_ID,
    ENV_TIMEZONE,
    ENV_DAYS_LOOKBACK,
    ENV_ARTICLES_PER_ACCOUNT,
    ENV_ANTHROPIC_MODEL,
    ENV_CONFIG_S3_BUCKET,
    ENV_CONFIG_S3_KEY,
    ENV_USE_DYNAMODB,
    ENV_DYNAMODB_TABLE,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


@dataclass
class AccountConfig:
    """Configuration for a single account."""
    company: str
    website: str
    keywords: List[str]
    newsroom: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'AccountConfig':
        """Create an AccountConfig from a dictionary.

        Args:
            data: Dictionary with account configuration

        Returns:
            AccountConfig instance

        Raises:
            ConfigError: If required fields are missing
        """
        required_fields = ['company', 'website', 'keywords']
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ConfigError(f"Missing required account fields: {', '.join(missing)}")

        if not isinstance(data['keywords'], list) or not data['keywords']:
            raise ConfigError(f"Account {data.get('company', 'unknown')} must have at least one keyword")

        return cls(
            company=data['company'],
            website=data['website'],
            keywords=data['keywords'],
            newsroom=data.get('newsroom')
        )


class Config:
    """Main configuration class."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Environment variables with validation
        self.slack_channel_id = os.environ.get(ENV_SLACK_CHANNEL_ID, '')
        self.timezone = os.environ.get(ENV_TIMEZONE, DEFAULT_TIMEZONE)

        # Parse integers with validation
        try:
            self.days_lookback = int(os.environ.get(ENV_DAYS_LOOKBACK, str(DEFAULT_DAYS_LOOKBACK)))
            if self.days_lookback < 1 or self.days_lookback > 30:
                raise ValueError("days_lookback must be between 1 and 30")
        except ValueError as e:
            logger.warning(f"Invalid DAYS_LOOKBACK: {e}. Using default: {DEFAULT_DAYS_LOOKBACK}")
            self.days_lookback = DEFAULT_DAYS_LOOKBACK

        try:
            self.articles_per_account = int(os.environ.get(ENV_ARTICLES_PER_ACCOUNT, str(DEFAULT_ARTICLES_PER_ACCOUNT)))
            if self.articles_per_account < 1 or self.articles_per_account > 50:
                raise ValueError("articles_per_account must be between 1 and 50")
        except ValueError as e:
            logger.warning(f"Invalid ARTICLES_PER_ACCOUNT: {e}. Using default: {DEFAULT_ARTICLES_PER_ACCOUNT}")
            self.articles_per_account = DEFAULT_ARTICLES_PER_ACCOUNT

        self.anthropic_model = os.environ.get(ENV_ANTHROPIC_MODEL, DEFAULT_CLAUDE_MODEL)
        self.config_s3_bucket = os.environ.get(ENV_CONFIG_S3_BUCKET, '')
        self.config_s3_key = os.environ.get(ENV_CONFIG_S3_KEY, '')
        self.use_dynamodb = os.environ.get(ENV_USE_DYNAMODB, 'false').lower() == 'true'
        self.dynamodb_table = os.environ.get(ENV_DYNAMODB_TABLE, 'weekly-news-seen-urls')

        # Secrets (lazy-loaded)
        self._secrets_cache: Optional[Dict[str, str]] = None

        # Domain filtering
        self.allowed_domains = REPUTABLE_NEWS_SOURCES.copy()
        self.blocked_domains = BLOCKED_NEWS_SOURCES.copy()

    @property
    def secrets(self) -> Dict[str, str]:
        """Lazy-load secrets from AWS Secrets Manager.

        Returns:
            Dictionary of secrets

        Raises:
            ConfigError: If critical secrets are missing
        """
        if self._secrets_cache is None:
            self._secrets_cache = self._load_secrets()
            self._validate_secrets(self._secrets_cache)
        return self._secrets_cache

    def _load_secrets(self) -> Dict[str, str]:
        """Load all secrets from AWS Secrets Manager.

        Returns:
            Dictionary of secrets
        """
        secrets_client = boto3.client('secretsmanager')
        secrets = {}

        secret_names = {
            'NEWS_DATA_API_KEY': os.environ.get('NEWS_DATA_SECRET_NAME', 'NEWS_DATA_API_KEY'),
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_SECRET_NAME', 'ANTHROPIC_API_KEY'),
            'SLACK_BOT_TOKEN': os.environ.get('SLACK_SECRET_NAME', 'SLACK_BOT_TOKEN')
        }

        for key, secret_name in secret_names.items():
            try:
                response = secrets_client.get_secret_value(SecretId=secret_name)
                secret_value = response['SecretString']

                # Handle both plain string and JSON secrets
                try:
                    secret_dict = json.loads(secret_value)
                    secrets[key] = secret_dict.get(key, secret_value)
                except json.JSONDecodeError:
                    secrets[key] = secret_value

                logger.info(f"Successfully loaded secret: {secret_name}")

            except Exception as e:
                logger.error(f"Failed to load secret {secret_name}: {e}")
                # For local testing, allow fallback to environment variables
                env_value = os.environ.get(key, '')
                if env_value:
                    logger.warning(f"Using environment variable fallback for {key}")
                    secrets[key] = env_value
                else:
                    secrets[key] = ''

        return secrets

    def _validate_secrets(self, secrets: Dict[str, str]) -> None:
        """Validate that all required secrets are present and non-empty.

        Args:
            secrets: Dictionary of loaded secrets

        Raises:
            ConfigError: If any required secret is missing or empty
        """
        required_secrets = ['NEWS_DATA_API_KEY', 'ANTHROPIC_API_KEY', 'SLACK_BOT_TOKEN']
        missing = []
        empty = []

        for key in required_secrets:
            if key not in secrets:
                missing.append(key)
            elif not secrets[key] or secrets[key].strip() == '':
                empty.append(key)

        if missing:
            raise ConfigError(f"Missing required secrets: {', '.join(missing)}")

        if empty:
            raise ConfigError(f"Empty secrets detected: {', '.join(empty)}")

        logger.info("All required secrets validated successfully")

    def load_accounts(self, config_path: Optional[str] = None) -> List[AccountConfig]:
        """Load account configurations from file or S3.

        Args:
            config_path: Optional path to config file

        Returns:
            List of AccountConfig objects

        Raises:
            ConfigError: If accounts cannot be loaded or are invalid
        """
        try:
            if self.config_s3_bucket and self.config_s3_key:
                accounts = self._load_accounts_from_s3()
            elif config_path:
                accounts = self._load_accounts_from_file(config_path)
            else:
                # Default location
                accounts = self._load_accounts_from_file('config/accounts.yaml')

            if not accounts:
                raise ConfigError("No accounts configured")

            logger.info(f"Loaded {len(accounts)} accounts")
            return accounts

        except FileNotFoundError as e:
            raise ConfigError(f"Account configuration file not found: {e}")
        except Exception as e:
            raise ConfigError(f"Failed to load accounts: {e}")

    def _load_accounts_from_file(self, path: str) -> List[AccountConfig]:
        """Load accounts from a local YAML or JSON file.

        Args:
            path: Path to configuration file

        Returns:
            List of AccountConfig objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ConfigError: If file format is invalid
        """
        try:
            with open(path, 'r') as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            if not isinstance(data, dict):
                raise ConfigError("Configuration file must contain a dictionary")

            accounts = data.get('accounts', [])
            if not isinstance(accounts, list):
                raise ConfigError("'accounts' must be a list")

            return [AccountConfig.from_dict(acc) for acc in accounts]

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML format: {e}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON format: {e}")

    def _load_accounts_from_s3(self) -> List[AccountConfig]:
        """Load accounts from S3.

        Returns:
            List of AccountConfig objects

        Raises:
            ConfigError: If S3 load fails
        """
        try:
            s3_client = boto3.client('s3')
            response = s3_client.get_object(
                Bucket=self.config_s3_bucket,
                Key=self.config_s3_key
            )
            content = response['Body'].read().decode('utf-8')

            if self.config_s3_key.endswith('.yaml') or self.config_s3_key.endswith('.yml'):
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            accounts = data.get('accounts', [])
            return [AccountConfig.from_dict(acc) for acc in accounts]

        except Exception as e:
            raise ConfigError(f"Failed to load accounts from S3: {e}")
