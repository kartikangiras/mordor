#!/usr/bin/env bash
# The six fictional walkthrough personas as Cognito users (AWS_INTEGRATION.md row 13).
#   tools/demo_users.sh create <password>   # demo stacks only; the password also goes in web/.env VITE_DEMO_PASSWORD
#   tools/demo_users.sh delete              # before anything real runs on the stack
set -euo pipefail
CMD="${1:-}"; STACK="${STACK_NAME:-mordor-dev}"; REGION="${AWS_REGION:-us-east-1}"
POOL=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
# email role entity  (entities: data/actors.demo.json; names: services/protocol/actors.py PERSONAS)
USERS=(
  "priya.demo@example.com analyst -"
  "anita.demo@example.com operator osm-way-388242027"
  "mehta.demo@example.com verifier -"
  "gurpreet.demo@example.com operator dao-demo-sangrur"
  "rekha.demo@example.com operator rwa-demo-rohini"
  "rao.demo@example.com auditor -"
  "kapoor.demo@example.com operator hosp-demo-rohini"
)
case "$CMD" in
  create)
    PASSWORD="${2:?password}"
    for u in "${USERS[@]}"; do set -- $u; EMAIL=$1; ROLE=$2; ENTITY=$3
      ATTRS="Name=email,Value=$EMAIL Name=email_verified,Value=true Name=custom:role,Value=$ROLE"
      [ "$ENTITY" != "-" ] && ATTRS="$ATTRS Name=custom:school_id,Value=$ENTITY"
      aws cognito-idp admin-create-user --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" --user-attributes $ATTRS --message-action SUPPRESS >/dev/null 2>&1 || true
      aws cognito-idp admin-set-user-password --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" --password "$PASSWORD" --permanent
      echo "ready $EMAIL ($ROLE${ENTITY:+, $ENTITY})"
    done ;;
  delete)
    for u in "${USERS[@]}"; do set -- $u; aws cognito-idp admin-delete-user --region "$REGION" --user-pool-id "$POOL" --username "$1" 2>/dev/null && echo "deleted $1" || echo "absent $1"; done ;;
  *) echo "usage: $0 create <password> | delete" >&2; exit 2 ;;
esac
