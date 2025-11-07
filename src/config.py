"""Configuration management for the weekly news automation."""
import os
import json
import yaml
import boto3
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AccountConfig:
    """Configuration for a single account."""
    company: str
    website: str
    keywords: List[str]
    newsroom: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'AccountConfig':
        """Create an AccountConfig from a dictionary."""
        return cls(
            company=data['company'],
            website=data['website'],
            keywords=data['keywords'],
            newsroom=data.get('newsroom')
        )


class Config:
    """Main configuration class."""

    def __init__(self):
        # Environment variables
        self.slack_channel_id = os.environ.get('SLACK_CHANNEL_ID', '')
        self.timezone = os.environ.get('TIMEZONE', 'America/New_York')
        self.days_lookback = int(os.environ.get('DAYS_LOOKBACK', '7'))
        self.articles_per_account = int(os.environ.get('ARTICLES_PER_ACCOUNT', '12'))
        self.anthropic_model = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-5-20250929')
        self.config_s3_bucket = os.environ.get('CONFIG_S3_BUCKET', '')
        self.config_s3_key = os.environ.get('CONFIG_S3_KEY', '')
        self.use_dynamodb = os.environ.get('USE_DYNAMODB', 'false').lower() == 'true'
        self.dynamodb_table = os.environ.get('DYNAMODB_TABLE', 'weekly-news-seen-urls')

        # Secrets (lazy-loaded)
        self._secrets_cache: Optional[Dict[str, str]] = None

        # Domain filtering
        self.allowed_domains = [
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

        self.blocked_domains = [
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

    @property
    def secrets(self) -> Dict[str, str]:
        """Lazy-load secrets from AWS Secrets Manager."""
        if self._secrets_cache is None:
            self._secrets_cache = self._load_secrets()
        return self._secrets_cache

    def _load_secrets(self) -> Dict[str, str]:
        """Load all secrets from AWS Secrets Manager."""
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
            except Exception as e:
                print(f"Warning: Could not load secret {secret_name}: {e}")
                # Fall back to environment variable if available
                secrets[key] = os.environ.get(key, '')

        return secrets

    def load_accounts(self, config_path: Optional[str] = None) -> List[AccountConfig]:
        """Load account configurations from file or S3."""
        if self.config_s3_bucket and self.config_s3_key:
            return self._load_accounts_from_s3()
        elif config_path:
            return self._load_accounts_from_file(config_path)
        else:
            # Default location
            return self._load_accounts_from_file('config/accounts.yaml')

    def _load_accounts_from_file(self, path: str) -> List[AccountConfig]:
        """Load accounts from a local YAML or JSON file."""
        with open(path, 'r') as f:
            if path.endswith('.yaml') or path.endswith('.yml'):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        accounts = data.get('accounts', [])
        return [AccountConfig.from_dict(acc) for acc in accounts]

    def _load_accounts_from_s3(self) -> List[AccountConfig]:
        """Load accounts from S3."""
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
