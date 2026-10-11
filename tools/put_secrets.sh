#!/usr/bin/env bash
# Load API keys into SSM Parameter Store as SecureStrings under /mordor/ (DESIGN.md §10.2).
# Reads values from the environment or from ./.env. Never commits anything.
set -euo pipefail
PREFIX="${SSM_PREFIX:-/mordor/}"
REGION="${AWS_REGION:-us-east-1}"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
put() {
  local leaf="$1" var="$2" val="${!2:-}"
  if [ -z "$val" ]; then echo "skip  ${PREFIX}${leaf} (${var} unset)"; return; fi
  aws ssm put-parameter --region "$REGION" --name "${PREFIX}${leaf}" --type SecureString \
      --value "$val" --overwrite >/dev/null && echo "wrote ${PREFIX}${leaf}"
}
put firms_map_key   FIRMS_MAP_KEY
put data_gov_api_key DATA_GOV_API_KEY
put openaq_api_key  OPENAQ_API_KEY
put location_api_key LOCATION_API_KEY
put ses_sender      SES_SENDER
