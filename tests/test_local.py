#!/usr/bin/env python3
"""Local testing script for the weekly news automation."""
import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.handler import lambda_handler


def test_dry_run():
    """Test with dry run mode (doesn't post to Slack)."""
    print("=" * 60)
    print("RUNNING DRY RUN TEST")
    print("=" * 60)

    event = {
        "dry_run": True
    }

    result = lambda_handler(event, None)

    print("\n" + "=" * 60)
    print("DRY RUN RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    return result


def test_single_account():
    """Test with a single account (requires account config modification)."""
    print("=" * 60)
    print("RUNNING SINGLE ACCOUNT TEST")
    print("=" * 60)

    # You can temporarily modify accounts.yaml to have just one account
    # or set up a test configuration file

    event = {
        "dry_run": True  # Keep dry_run to avoid posting
    }

    result = lambda_handler(event, None)

    print("\n" + "=" * 60)
    print("SINGLE ACCOUNT RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    return result


def test_live():
    """Test with actual Slack posting (USE WITH CAUTION)."""
    print("=" * 60)
    print("WARNING: RUNNING LIVE TEST")
    print("This will post to your configured Slack channel!")
    print("=" * 60)

    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Test cancelled.")
        return

    event = {
        "dry_run": False
    }

    result = lambda_handler(event, None)

    print("\n" + "=" * 60)
    print("LIVE TEST RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    return result


def verify_environment():
    """Verify that all required environment variables are set."""
    print("=" * 60)
    print("VERIFYING ENVIRONMENT")
    print("=" * 60)

    required_vars = [
        'SLACK_CHANNEL_ID',
        'NEWS_DATA_API_KEY',
        'ANTHROPIC_API_KEY',
        'SLACK_BOT_TOKEN'
    ]

    # For local testing, secrets might be in env vars instead of Secrets Manager
    missing = []
    for var in required_vars:
        value = os.environ.get(var, '')
        if value:
            print(f"✓ {var}: {'*' * 10}")
        else:
            print(f"✗ {var}: NOT SET")
            missing.append(var)

    if missing:
        print(f"\nMissing variables: {', '.join(missing)}")
        print("\nFor local testing, you can set these in your environment:")
        print("export NEWS_DATA_API_KEY='your-key'")
        print("export ANTHROPIC_API_KEY='your-key'")
        print("export SLACK_BOT_TOKEN='xoxb-your-token'")
        print("export SLACK_CHANNEL_ID='C1234567890'")
        return False

    print("\n✓ All required variables are set")
    return True


if __name__ == "__main__":
    # Check environment first
    if not verify_environment():
        print("\nPlease set the required environment variables before testing.")
        sys.exit(1)

    # Run tests
    if len(sys.argv) > 1:
        test_type = sys.argv[1]

        if test_type == "dry":
            test_dry_run()
        elif test_type == "single":
            test_single_account()
        elif test_type == "live":
            test_live()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python test_local.py [dry|single|live]")
            sys.exit(1)
    else:
        # Default to dry run
        test_dry_run()
