# Weekly Account-News Automation

A serverless AWS Lambda application that automatically fetches, filters, summarizes, and delivers weekly news briefs for your key B2B accounts via Slack.

## Features

- **Automated Weekly Runs**: Scheduled every Monday at 08:05 ET via EventBridge Scheduler
- **Multi-Source News Aggregation**: Uses Newsdata.io with three focused query strategies per account
- **Intelligent Filtering**: Removes duplicates, blocks spam domains, prioritizes reputable sources
- **AI Summarization**: Claude generates structured briefs organized by categories AEs care about
- **Slack Integration**: Posts clean, actionable briefs directly to your team channel
- **Optional Deduplication**: DynamoDB tracks seen articles to avoid repeats across runs
- **Cost-Efficient**: Serverless architecture with pay-per-use pricing

## Architecture

```
EventBridge Scheduler (Weekly)
        ↓
    Lambda Function
        ↓
    ├─→ Newsdata.io (News Aggregation)
    ├─→ Claude AI (Summarization)
    ├─→ Slack API (Delivery)
    └─→ DynamoDB (Optional: Deduplication)
```

## Prerequisites

### 1. AWS Account
- IAM permissions to create Lambda functions, EventBridge rules, DynamoDB tables, and IAM roles
- AWS CLI and SAM CLI installed

### 2. Slack Setup
1. Create a Slack app at https://api.slack.com/apps
2. Add the `chat:write` scope under OAuth & Permissions
3. Install the app to your workspace
4. Copy the Bot User OAuth Token (starts with `xoxb-`)
5. Invite the bot to your target channel
6. Copy the channel ID (right-click channel → View channel details)

### 3. Newsdata.io Account
1. Sign up at https://newsdata.io
2. Subscribe to a paid plan (free tier is limited for production)
3. Copy your API key

### 4. Anthropic API Access
1. Sign up at https://console.anthropic.com
2. Generate an API key
3. Ensure you have credits available

## Installation

### Step 1: Clone and Configure

```bash
git clone <repository-url>
cd app-b2b-weekly-news

# Install dependencies (for local testing)
pip install -r requirements.txt
```

### Step 2: Store Secrets in AWS Secrets Manager

```bash
# Store Newsdata.io API key
aws secretsmanager create-secret \
    --name NEWS_DATA_API_KEY \
    --secret-string "your-newsdata-api-key"

# Store Anthropic API key
aws secretsmanager create-secret \
    --name ANTHROPIC_API_KEY \
    --secret-string "your-anthropic-api-key"

# Store Slack bot token
aws secretsmanager create-secret \
    --name SLACK_BOT_TOKEN \
    --secret-string "xoxb-your-slack-token"
```

### Step 3: Configure Accounts

Edit `config/accounts.yaml` with your target accounts:

```yaml
accounts:
  - company: "Acme Corp"
    website: "acme.com"
    newsroom: "https://acme.com/news/"
    keywords:
      - partnership
      - customer
      - acquisition
      - launch
      - funding
```

See the sample file for detailed field descriptions.

### Step 4: Update SAM Configuration

Edit `samconfig.toml` and replace:
- `SlackChannelId=REPLACE_WITH_YOUR_CHANNEL_ID` with your actual Slack channel ID
- Adjust region if needed (default: `us-east-1`)

### Step 5: Deploy with SAM

```bash
# Build the Lambda package
sam build

# Deploy (first time - guided)
sam deploy --guided

# Subsequent deploys
sam deploy
```

The deployment will create:
- Lambda function with appropriate IAM role
- EventBridge Scheduler for weekly runs
- DynamoDB table (if enabled)
- CloudWatch Log Group and alarms

## Configuration

### Environment Variables (Lambda)

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_CHANNEL_ID` | - | Slack channel ID (required) |
| `TIMEZONE` | `America/New_York` | Timezone for date calculations |
| `DAYS_LOOKBACK` | `7` | Number of days to search for articles |
| `ARTICLES_PER_ACCOUNT` | `12` | Maximum articles per account |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250929` | Claude model to use |
| `USE_DYNAMODB` | `false` | Enable DynamoDB deduplication |
| `DYNAMODB_TABLE` | `weekly-news-seen-urls` | DynamoDB table name |

### Account Configuration Fields

Each account in `config/accounts.yaml` requires:

- **company** (required): Official legal name used in news searches
- **website** (required): Root domain without www
- **keywords** (required): 4-10 relevant business terms for filtering
- **newsroom** (optional): URL to company's press release page or RSS feed

## Testing

### Local Testing (Dry Run)

```bash
# Set environment variables for local testing
export NEWS_DATA_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL_ID="C1234567890"

# Run dry run test (doesn't post to Slack)
python tests/test_local.py dry
```

### Lambda Test (Dry Run)

```bash
# Invoke Lambda with dry_run flag
aws lambda invoke \
    --function-name WeeklyNewsFunction \
    --payload '{"dry_run": true}' \
    response.json

cat response.json
```

### Live Test

```bash
# Test with actual Slack posting (use a test channel first!)
aws lambda invoke \
    --function-name WeeklyNewsFunction \
    --payload '{"dry_run": false}' \
    response.json
```

## Usage

### Automatic Weekly Runs

Once deployed, the system runs automatically every Monday at 08:05 ET. No manual intervention required.

### Manual Trigger

```bash
# Trigger an immediate run
aws lambda invoke \
    --function-name WeeklyNewsFunction \
    --payload '{}' \
    response.json
```

### Check Logs

```bash
# View recent logs
aws logs tail /aws/lambda/WeeklyNewsFunction --follow

# View specific log stream
aws logs get-log-events \
    --log-group-name /aws/lambda/WeeklyNewsFunction \
    --log-stream-name "2024/01/15/[\$LATEST]abc123"
```

## Output Format

Each weekly brief includes:

### For Each Account:
- **Products/Launches**: New products, features, or services
- **Customers/Partners**: New customers, partnerships, integrations
- **Exec & Hiring**: Leadership changes, key hires
- **Funding/M&A**: Funding rounds, acquisitions, financial milestones
- **Risks/Controversies**: Lawsuits, security incidents, negative press
- **Regulatory**: Compliance updates, policy changes
- **Talk track**: 2 conversation starters for AE calls
- **Links**: 8-12 vetted source articles with titles and sources

## Monitoring

### CloudWatch Metrics

The Lambda function logs:
- Accounts processed
- Articles fetched/filtered/kept per account
- Tokens used for summarization
- Errors and warnings

### CloudWatch Alarms

An alarm is created to alert when errors occur (default: ≥1 error in 5 minutes).

To add SNS notifications:

```bash
# Create SNS topic
aws sns create-topic --name weekly-news-alerts

# Subscribe your email
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:weekly-news-alerts \
    --protocol email \
    --notification-endpoint your-email@example.com

# Update the alarm to notify SNS
aws cloudwatch put-metric-alarm \
    --alarm-name weekly-news-errors \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:weekly-news-alerts
```

## Troubleshooting

### No Articles Found

**Possible causes:**
- API key exhausted or expired
- Account name doesn't match news coverage
- Too restrictive domain filtering

**Solutions:**
- Check Newsdata.io credit balance
- Try broader keywords
- Review `allowed_domains` in config.py

### Slack Posting Failed

**Possible causes:**
- Invalid bot token or channel ID
- Bot not invited to channel
- Message too large

**Solutions:**
- Verify bot token in Secrets Manager
- Re-invite bot to channel: `/invite @YourBot`
- Reduce `ARTICLES_PER_ACCOUNT` if messages are large

### Lambda Timeout

**Possible causes:**
- Too many accounts
- Slow API responses

**Solutions:**
- Increase Lambda timeout in template.yaml (max: 900s)
- Reduce number of accounts
- Add pagination limits in newsdata_client.py

### DynamoDB Errors

**Possible causes:**
- Table doesn't exist
- IAM permissions missing

**Solutions:**
- Verify table created: `aws dynamodb describe-table --table-name weekly-news-seen-urls`
- Check Lambda execution role has DynamoDB permissions

## Cost Estimation

### AWS Services
- **Lambda**: ~$0.20/month (assuming 4 runs/month × 5 minutes × 1536MB)
- **DynamoDB**: ~$1-2/month (on-demand pricing, depends on account count)
- **EventBridge**: Free (first 14M invocations/month)
- **CloudWatch Logs**: ~$0.50/month

### Third-Party APIs
- **Newsdata.io**: $29-149/month depending on plan
- **Anthropic Claude**: ~$1-5/month (depends on article volume)
- **Slack**: Free

**Total estimated cost**: $30-160/month

## Operational Tips

### Adding New Accounts
1. Edit `config/accounts.yaml`
2. Add company details and relevant keywords
3. Redeploy: `sam build && sam deploy`

### Adjusting Query Strategies
Edit `src/clients/newsdata_client.py`:
- Modify domain allowlists/blocklists
- Adjust query construction
- Change pagination limits

### Customizing Summary Format
Edit `src/clients/claude_client.py`:
- Modify the prompt in `_build_prompt()`
- Adjust section categories
- Change output token limits

### Scheduling Changes
Edit `template.yaml` → `WeeklySchedule` → `ScheduleExpression`:
- Current: `cron(5 13 ? * MON *)` = Monday 08:05 ET
- Daily: `cron(0 13 ? * * *)` = Every day 08:00 ET
- Bi-weekly: Use Step Functions for complex scheduling

## Project Structure

```
app-b2b-weekly-news/
├── src/
│   ├── handler.py              # Main Lambda handler
│   ├── config.py               # Configuration management
│   ├── clients/
│   │   ├── newsdata_client.py  # Newsdata.io API client
│   │   ├── claude_client.py    # Claude AI client
│   │   └── slack_client.py     # Slack API client
│   └── utils/
│       ├── article_filter.py   # Filtering and deduplication
│       └── persistence.py      # DynamoDB and S3 helpers
├── config/
│   └── accounts.yaml           # Account configuration
├── tests/
│   └── test_local.py          # Local testing harness
├── template.yaml              # AWS SAM template
├── samconfig.toml            # SAM deployment config
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Rotate API keys** quarterly
3. **Use least-privilege IAM** roles
4. **Enable CloudWatch Logs encryption** for sensitive data
5. **Restrict Secrets Manager access** to only this Lambda function

## Support and Contribution

For issues, questions, or contributions:
1. Check existing documentation
2. Review CloudWatch Logs for error details
3. Open an issue with logs and configuration (redact secrets!)

## License

This project is provided as-is for internal use.

---

**Built with**: AWS Lambda • Python 3.12 • Newsdata.io • Anthropic Claude • Slack API
