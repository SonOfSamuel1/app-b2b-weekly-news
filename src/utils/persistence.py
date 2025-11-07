"""Persistence layer for tracking seen articles."""
import boto3
from typing import List, Set
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class DynamoDBPersistence:
    """DynamoDB-based persistence for tracking seen article URLs."""

    def __init__(self, table_name: str):
        """Initialize the persistence layer.

        Args:
            table_name: DynamoDB table name
        """
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    def mark_as_seen(self, account: str, url_hashes: List[str], pub_dates: List[str]) -> None:
        """Mark URLs as seen for an account.

        Args:
            account: Company/account name
            url_hashes: List of URL hashes
            pub_dates: List of publication dates
        """
        if not url_hashes:
            return

        # Calculate TTL (90 days from now)
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        # Batch write items
        with self.table.batch_writer() as batch:
            for url_hash, pub_date in zip(url_hashes, pub_dates):
                try:
                    batch.put_item(
                        Item={
                            'pk': f"ACCOUNT#{account}",
                            'sk': f"URL#{url_hash}",
                            'account': account,
                            'url_hash': url_hash,
                            'pub_date': pub_date,
                            'seen_at': datetime.utcnow().isoformat(),
                            'ttl': ttl
                        }
                    )
                except Exception as e:
                    print(f"Error marking URL as seen: {e}")

    def get_seen_urls(self, account: str) -> Set[str]:
        """Get all seen URL hashes for an account.

        Args:
            account: Company/account name

        Returns:
            Set of seen URL hashes
        """
        seen = set()
        pk = f"ACCOUNT#{account}"

        try:
            response = self.table.query(
                KeyConditionExpression='pk = :pk AND begins_with(sk, :sk_prefix)',
                ExpressionAttributeValues={
                    ':pk': pk,
                    ':sk_prefix': 'URL#'
                },
                ProjectionExpression='url_hash'
            )

            for item in response.get('Items', []):
                seen.add(item['url_hash'])

            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.table.query(
                    KeyConditionExpression='pk = :pk AND begins_with(sk, :sk_prefix)',
                    ExpressionAttributeValues={
                        ':pk': pk,
                        ':sk_prefix': 'URL#'
                    },
                    ProjectionExpression='url_hash',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )

                for item in response.get('Items', []):
                    seen.add(item['url_hash'])

        except ClientError as e:
            print(f"Error querying seen URLs: {e}")

        return seen

    def filter_unseen(self, account: str, articles: List[dict]) -> List[dict]:
        """Filter out articles that have been seen before.

        Args:
            account: Company/account name
            articles: List of article dictionaries

        Returns:
            List of unseen articles
        """
        seen_hashes = self.get_seen_urls(account)
        unseen = []

        for article in articles:
            url_hash = article.get('url_hash', '')
            if url_hash and url_hash not in seen_hashes:
                unseen.append(article)

        return unseen


class S3Archiver:
    """S3-based archiving for weekly briefs."""

    def __init__(self, bucket_name: str):
        """Initialize the S3 archiver.

        Args:
            bucket_name: S3 bucket name
        """
        self.bucket_name = bucket_name
        self.s3 = boto3.client('s3')

    def archive_brief(self, week_key: str, content: str) -> bool:
        """Archive a weekly brief to S3.

        Args:
            week_key: ISO week identifier (e.g., "2024-W12")
            content: Brief content to archive

        Returns:
            True if successful, False otherwise
        """
        key = f"briefs/{week_key}.json"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
            print(f"Archived brief to s3://{self.bucket_name}/{key}")
            return True

        except Exception as e:
            print(f"Error archiving brief: {e}")
            return False

    def get_brief(self, week_key: str) -> str:
        """Retrieve a brief from S3.

        Args:
            week_key: ISO week identifier

        Returns:
            Brief content or empty string if not found
        """
        key = f"briefs/{week_key}.json"

        try:
            response = self.s3.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read().decode('utf-8')

        except self.s3.exceptions.NoSuchKey:
            return ""
        except Exception as e:
            print(f"Error retrieving brief: {e}")
            return ""
