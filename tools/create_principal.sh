#!/usr/bin/env bash
# Create a principal login in the Cognito user pool with custom:school_id (DESIGN.md §10.1).
#   tools/create_principal.sh <email> <entity_id> <password> [role]
#   role: operator (default, holds a card) | verifier | analyst | auditor  (DESIGN.md §6.6)
set -euo pipefail
EMAIL="$1"; SCHOOL_ID="$2"; PASSWORD="$3"; ROLE="${4:-operator}"
STACK="${STACK_NAME:-mordor-dev}"; REGION="${AWS_REGION:-us-east-1}"
POOL=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
aws cognito-idp admin-create-user --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" \
  --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true Name=custom:school_id,Value="$SCHOOL_ID" Name=custom:role,Value="$ROLE" \
  --message-action SUPPRESS >/dev/null
aws cognito-idp admin-set-user-password --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" \
  --password "$PASSWORD" --permanent
echo "created $EMAIL -> entity $SCHOOL_ID, role $ROLE, in pool $POOL"
