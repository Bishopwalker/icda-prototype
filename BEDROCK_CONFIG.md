# AWS Bedrock Configuration for ICDA

## Quick Start

### Development (Commercial AWS)
```cmd
claude-icda.bat
```

### Production (GovCloud - FedRAMP/IL4/IL5)
```cmd
claude-icda-govcloud.bat
```

## Manual Setup

### Environment Variables
```bash
# Required
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-east-1  # or us-gov-west-1 for GovCloud

# Models (Opus 4.5 for best quality)
export ANTHROPIC_MODEL='us.anthropic.claude-opus-4-5-20251101-v1:0'
export ANTHROPIC_SMALL_FAST_MODEL='us.anthropic.claude-haiku-4-5-20251001-v1:0'
```

### AWS Profiles Configured
- `icda-commercial` - us-east-1 (development/testing)
- `icda` - us-gov-west-1 (GovCloud production)

### SSO Login
```cmd
aws sso login --profile icda-commercial  # Dev
aws sso login --profile icda             # GovCloud
```

## Compliance Notes

### GovCloud (us-gov-west-1)
- FedRAMP High authorized
- DoD IL4/IL5 authorized
- Use for USPS production work

### Required IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.*"
    }
  ]
}
```

## Model Options

| Model | ID | Use Case |
|-------|-----|----------|
| Opus 4.5 | `us.anthropic.claude-opus-4-5-20251101-v1:0` | Complex reasoning, architecture |
| Sonnet 4.5 | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | General coding |
| Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Fast tasks, background |

## Troubleshooting

### Credentials Expired
```cmd
aws sso login --profile icda-commercial
```

### Model Not Available
Check Bedrock model access in AWS Console:
```cmd
aws bedrock list-foundation-models --region us-east-1 --by-provider anthropic
```

### Check Inference Profiles
```cmd
aws bedrock list-inference-profiles --region us-east-1
```
