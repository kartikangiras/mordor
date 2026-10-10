# Local developer entry points. All Python runs with services/ on the path so that
# `from common import domain` works exactly as it does inside the Lambda package.
PY := .venv/bin/python
export PYTHONPATH := services

.PHONY: venv test ingest-firms ingest-weather forecast-local web-dev api-dev web-deploy sam-validate sam-build seed-local

venv:
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -r requirements-dev.txt

test:
	$(PY) -m pytest

ingest-firms:      ## fetch FIRMS into ./.data (no AWS needed)
	$(PY) -m ingest_firms.handler

ingest-weather:    ## fetch Open-Meteo winds + CAMS into ./.data
	$(PY) -m ingest_weather.handler

forecast-local:    ## single-hour run rendered into web/public/dev (M3). HOURS=48 for a full run.
	$(PY) -m forecast.cli --hours $(or $(HOURS),1) --out web/public/dev

web-dev:
	cd web && npm run dev

api-dev:           ## local FastAPI on :8000 (vite proxies /api here); dev auth via X-Dev-School-Id
	LOCAL_DATA_DIR=web/public/dev DEV_AUTH_BYPASS=1 NOTIFY_USE_AGENT=0 $(PY) -m uvicorn api.handler:app --port 8000 --app-dir services

web-deploy:        ## build the SPA, sync it to the WebBucket of STACK (default mordor-dev), invalidate CloudFront
	$(eval STACK ?= mordor-dev)
	$(eval REGION ?= us-east-1)
	$(eval WEB_BUCKET := $(shell aws cloudformation describe-stacks --region $(REGION) --stack-name $(STACK) --query "Stacks[0].Outputs[?OutputKey=='WebBucketName'].OutputValue" --output text))
	$(eval CDN_ID := $(shell aws cloudformation describe-stacks --region $(REGION) --stack-name $(STACK) --query "Stacks[0].Outputs[?OutputKey=='CdnDistributionId'].OutputValue" --output text))
	@grep -q '^VITE_DEMO_MODE=1' web/.env && echo 'demo mode: on (web/.env VITE_DEMO_MODE=1)' || echo 'demo mode: off'
	cd web && npm run build
	# web/public/dev holds ~59 MB of local forecast fixtures that vite copies into dist.
	# The deployed app reads /runs/* from the DATA bucket, so none of it is used in
	# production: excluding it keeps the deploy seconds rather than minutes.
	aws s3 sync web/dist s3://$(WEB_BUCKET) --delete --exclude 'dev/*' --region $(REGION)
	aws cloudfront create-invalidation --distribution-id $(CDN_ID) --paths '/*' >/dev/null && echo "deployed to $(WEB_BUCKET), invalidated $(CDN_ID)"

sam-validate:
	sam validate -t infra/template.yaml --lint

sam-build:
	sam build -t infra/template.yaml --use-container

seed-local:        ## copy committed static data (schools, calibration) into ./.data for local runs
	mkdir -p .data/static .data/validation/latest
	cp data/schools.geojson .data/static/schools.geojson
	cp data/climatology_2024.json .data/static/climatology_2024.json
	cp data/validation/latest/*.json .data/validation/latest/
