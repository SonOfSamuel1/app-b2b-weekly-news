# Deployment Guide - Weekly Account-News Automation

This guide walks you through deploying the weekly news automation from scratch.

## Phase 1: Pre-Deployment Checklist

### 1.1 Install Required Tools

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install AWS SAM CLI
# See: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Install Python 3.12
python3 --version  # Should be 3.12 or higher

# Install dependencies
pip install -r requirements.txt
```

### 1.2 Configure AWS Credentials

```bash
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Output format (json)

# Verify
aws sts get-caller-identity
```

## Phase 2: Set Up Third-Party Services

### 2.1 Slack Setup

1. **Create Slack App**
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name: "Weekly News Bot"
   - Pick your workspace

2. **Add Bot Permissions**
   - Go to "OAuth & Permissions"
   - Under "Scopes" → "Bot Token Scopes", add:
     - `chat:write`
     - `chat:write.public` (optional, to post to channels without invitation)
   - Click "Install to Workspace"
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

3. **Get Channel ID**
   - Open Slack
   - Right-click your target channel → "View channel details"
   - Scroll down to find the Channel ID (e.g., `C1234567890`)
   - Invite the bot to the channel: `/invite @Weekly News Bot`

### 2.2 Newsdata.io Setup

1. Sign up at https://newsdata.io
2. Choose a paid plan (recommended: Pro or higher for production)
3. Copy your API key from the dashboard

### 2.3 Anthropic Setup

1. Sign up at https://console.anthropic.com
2. Go to API Keys
3. Create a new API key
4. Copy the key (starts with `sk-ant-`)
5. Add credits to your account

## Phase 3: Store Secrets in AWS

```bash
# Store Newsdata.io API key
aws secretsmanager create-secret \
    --name NEWS_DATA_API_KEY \
    --description "Newsdata.io API key for weekly news automation" \
    --secret-string "YOUR_NEWSDATA_API_KEY" \
    --region us-east-1

# Store Anthropic API key
aws secretsmanager create-secret \
    --name ANTHROPIC_API_KEY \
    --description "Anthropic API key for Claude" \
    --secret-string "YOUR_ANTHROPIC_API_KEY" \
    --region us-east-1

# Store Slack bot token
aws secretsmanager create-secret \
    --name SLACK_BOT_TOKEN \
    --description "Slack bot token for posting briefs" \
    --secret-string "xoxb-YOUR-SLACK-TOKEN" \
    --region us-east-1

# Verify secrets were created
aws secretsmanager list-secrets --region us-east-1
```

## Phase 4: Configure Your Accounts

Edit `config/accounts.yaml`:

```yaml
accounts:
  - company: "Your Company Name"
    website: "company.com"
    newsroom: "https://company.com/news/"  # optional
    keywords:
      - partnership
      - customer
      - acquisition
      - launch
      - funding
      # Add 4-10 relevant keywords
```

**Tips for choosing keywords:**
- Focus on business events (partnership, customer, acquisition)
- Include product-specific terms
- Add sector-specific terminology
- Avoid generic terms like "company" or "business"

## Phase 5: Configure Deployment

Edit `samconfig.toml`:

```toml
parameter_overrides = [
    "SlackChannelId=C1234567890",  # ← Replace with your channel ID
    "NewsdataSecretName=NEWS_DATA_API_KEY",
    "AnthropicSecretName=ANTHROPIC_API_KEY",
    "SlackSecretName=SLACK_BOT_TOKEN",
    "UseDynamoDB=true"  # Set to false if you don't want deduplication
]
```

Optional parameters:
- `ConfigS3Bucket` - If you want to store accounts.yaml in S3
- `ConfigS3Key` - Path to accounts.yaml in S3
- `ArchiveS3Bucket` - If you want to archive briefs in S3

## Phase 6: Deploy

### Option A: Using the deployment script (recommended)

```bash
# First deployment (guided)
./deploy.sh --guided

# Subsequent deployments
./deploy.sh
```

### Option B: Manual SAM commands

```bash
# Build
sam build

# Deploy (first time)
sam deploy --guided

# Deploy (subsequent)
sam deploy
```

During guided deployment, accept defaults or customize:
- Stack Name: `weekly-news-automation`
- AWS Region: `us-east-1` (or your preferred region)
- Confirm changes before deploy: Y
- Allow SAM CLI IAM role creation: Y
- Save arguments to configuration file: Y

## Phase 7: Verify Deployment

### 7.1 Check Stack Status

```bash
aws cloudformation describe-stacks \
    --stack-name weekly-news-automation \
    --query 'Stacks[0].StackStatus'

# Should output: "CREATE_COMPLETE" or "UPDATE_COMPLETE"
```

### 7.2 Test with Dry Run

```bash
# Invoke Lambda with dry_run flag
aws lambda invoke \
    --function-name weekly-news-automation-WeeklyNewsFunction-XXXXX \
    --payload '{"dry_run": true}' \
    --cli-binary-format raw-in-base64-out \
    response.json

# Check response
cat response.json | jq .

# View logs
aws logs tail /aws/lambda/weekly-news-automation-WeeklyNewsFunction-XXXXX --follow
```

**Find your exact function name:**
```bash
aws lambda list-functions --query 'Functions[?contains(FunctionName, `WeeklyNews`)].FunctionName'
```

### 7.3 Test Live (Optional)

**⚠️ This will post to your Slack channel!**

```bash
aws lambda invoke \
    --function-name weekly-news-automation-WeeklyNewsFunction-XXXXX \
    --payload '{"dry_run": false}' \
    --cli-binary-format raw-in-base64-out \
    response.json
```

## Phase 8: Monitor and Tune

### 8.1 Check Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/FUNCTION_NAME --follow

# Recent logs
aws logs tail /aws/lambda/FUNCTION_NAME --since 1h

# Search for errors
aws logs tail /aws/lambda/FUNCTION_NAME --filter-pattern "ERROR"
```

### 8.2 Review CloudWatch Metrics

Go to AWS Console → CloudWatch → Metrics:
- Lambda → Duration
- Lambda → Errors
- Lambda → Invocations

### 8.3 Test the Schedule

The EventBridge schedule runs every Monday at 08:05 ET. To verify:

```bash
aws scheduler get-schedule \
    --name weekly-news-monday-morning

# Check next invocation time
```

To trigger manually before Monday:
```bash
aws lambda invoke \
    --function-name FUNCTION_NAME \
    --payload '{}' \
    response.json
```

## Phase 9: Operational Tasks

### Add/Remove Accounts

1. Edit `config/accounts.yaml`
2. Redeploy:
   ```bash
   sam build && sam deploy
   ```

### Update Schedule

1. Edit `template.yaml` → `WeeklySchedule` → `ScheduleExpression`
2. Redeploy:
   ```bash
   sam build && sam deploy
   ```

### Update Environment Variables

1. Edit `template.yaml` → `WeeklyNewsFunction` → `Environment`
2. Redeploy:
   ```bash
   sam build && sam deploy
   ```

### Rotate Secrets

```bash
# Update a secret
aws secretsmanager update-secret \
    --secret-id NEWS_DATA_API_KEY \
    --secret-string "NEW_API_KEY"

# No redeployment needed - Lambda will fetch the new value on next run
```

## Troubleshooting

### Issue: "Secrets Manager access denied"

**Solution:**
```bash
# Check Lambda execution role
aws iam get-role --role-name weekly-news-automation-WeeklyNewsFunctionRole-XXXXX

# Verify it has secretsmanager:GetSecretValue permission
```

### Issue: "No articles found for any account"

**Possible causes:**
1. Newsdata.io API key invalid or exhausted
2. Account names don't match news coverage
3. Date range too narrow

**Solutions:**
- Check Newsdata.io dashboard for API status
- Test with well-known companies first (e.g., Salesforce, Microsoft)
- Increase `DAYS_LOOKBACK` to 14

### Issue: Lambda timeout

**Solution:**
```bash
# Increase timeout in template.yaml
# Under WeeklyNewsFunction:
Timeout: 600  # 10 minutes

# Redeploy
sam build && sam deploy
```

### Issue: "Slack posting failed"

**Solutions:**
1. Verify bot token: `aws secretsmanager get-secret-value --secret-id SLACK_BOT_TOKEN`
2. Check channel ID is correct
3. Ensure bot is invited to channel: `/invite @Weekly News Bot`
4. Test bot manually with Slack API tester

## Cost Optimization

### Reduce Lambda costs:
- Decrease `MemorySize` to 1024 MB if acceptable
- Reduce `ARTICLES_PER_ACCOUNT` to 8-10

### Reduce API costs:
- Use more specific keywords to reduce API calls
- Increase `DAYS_LOOKBACK` so fewer runs are needed
- Disable DynamoDB if not needed

## Cleanup (Uninstall)

To completely remove the stack:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name weekly-news-automation

# Delete secrets
aws secretsmanager delete-secret --secret-id NEWS_DATA_API_KEY --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id ANTHROPIC_API_KEY --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id SLACK_BOT_TOKEN --force-delete-without-recovery

# DynamoDB table will be deleted automatically with the stack
```

## Support

For issues:
1. Check CloudWatch Logs first
2. Review this guide
3. Consult the main README.md
4. Open an issue with logs (redact any secrets!)

---

**Deployment complete!** Your weekly news automation should now run every Monday at 08:05 ET.
