# mordor — tomorrow's stubble smoke, as a decision

> **mordor** · धुआँ (smoke) — what it forecasts. A 5 km, hourly, 48-hour forecast of the *stubble-fire increment*
> to PM2.5 over Punjab, Haryana and NCR, delivered as a one-screen protocol to school principals.

**Hackathon:** WeMakeDevs × AWS "Environmental Hacks", Bharat Builds Tour Event 02 · Track 01 — Air.

This README is the judge-facing summary and is finished on Day 4 (M13). The full design,
build order, gates and honesty rules are in [`DESIGN.md`](DESIGN.md).

## What it does

```
PM2.5_total(x, t) = PM2.5_background(x, t)   [CAMS via Open-Meteo, ~40 km, consumed]
                  + PM2.5_fire(x, t)         [ours, 5 km, from NASA FIRMS + 925 hPa winds]
```

We claim skill on the second term only, and say so on screen.

**Enter the experience** at `/`: a cinematic terrain map, then eight steps, each opened by the
person who performs it and ending in a decision that writes a signed record: survey, register,
approve, plan, act, verify, impact, seal.

Two surfaces: a public **Smoke Map** (where it burns, where it will burn next, where the wind
takes it, when it arrives, which cities and how much of it is the fires) and a private **School
Protocol** card (indoor PT, shut windows, one-tap WhatsApp to parents), anchored to CAQM's GRAP
stages. Plus `/zones`: seventeen cities ranked by exposure with the background / fire split and
NO2 as a traffic tracer, and the active burning areas with a 48 h burning-risk score built from
fires, the 2024 season, NDVI change and forecast rain.

## AWS

Built and deployed with **AWS SAM CLI** (open source). Runs on Lambda, Step Functions,
DynamoDB, S3, CloudFront, API Gateway, EventBridge Scheduler, Cognito and Amazon Location
Service. Parent messages are generated with the **Strands Agents SDK** (open source) on the Anthropic API (Claude Sonnet 5), with Amazon Bedrock as the alternative provider.

## Run it locally (no AWS account needed)

```bash
make venv                 # Python 3.12 venv via uv
make test
make ingest-firms         # real VIIRS fires for the domain -> ./.data
make ingest-weather       # Open-Meteo winds + BLH + CAMS background -> ./.data
make forecast-local       # 48 h particle run, overlays + cards -> web/public/dev
make api-dev              # FastAPI on :8000 (dev auth), proxied by vite at /api
cd web && npm install && npm run dev
```

## Deploy

```bash
tools/put_secrets.sh      # FIRMS / data.gov.in / OpenAQ keys into SSM (/mordor/*)
sam build && sam deploy --guided
```

Every credential, key and console step the stack needs, with how to verify each one, is in
[`AWS_INTEGRATION.md`](AWS_INTEGRATION.md). After the deploy: `make web-deploy`.

## Limitations (honest, on purpose)

A simplified Lagrangian transport model: no chemistry, no vertical structure, one fitted
scaling constant whose fit quality (R², MAE) is shown in the UI footer. VIIRS sees fires
twice a day; fires that start and finish between overpasses are invisible. Not for medical
decisions. See `DESIGN.md` §13.
