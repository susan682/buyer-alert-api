# Buyer Alert Image API

Flask API that generates SalonSpa Connection Buyer Alert social post images.
Used by n8n to auto-generate posts from GHL form submissions.

## Files required in root
- `app.py` — main API
- `requirements.txt`
- `Procfile`
- `TheSeasons-Regular.ttf` — font file
- `template_2.png` — dark photo template (centered text)
- `template_4.png` — light photo template (left-aligned teal text)

## Deploy to Railway
1. Create a new GitHub repo and push all files
2. In Railway: New Project → Deploy from GitHub repo
3. Railway auto-detects Python + Procfile — no config needed
4. Note your Railway URL (e.g. `https://buyer-alert-api.up.railway.app`)

## API Endpoints

### GET /health
Returns `{"status": "ok"}` — use for Railway health check.

### POST /generate
Generates a buyer alert PNG and returns it as base64.

**Request body:**
```json
{
    "template": 2,
    "types": "Salons, Spas",
    "states": "Pennsylvania, Florida",
    "budget": "Under $100,000"
}
```

**template:** `2` = dark photo (centered), `4` = light photo (left-aligned teal)

**Response:**
```json
{
    "image_b64": "<base64 encoded PNG>"
}
```

## n8n Usage
1. HTTP Request node → POST to `/generate` with buyer form data
2. Code node → decode base64, upload to GHL Media Storage
3. HTTP Request node → POST to GHL Social Planner API with image URL

## Template rotation
Tracked in n8n static data. Counter alternates 2 → 4 → 2 → 4 automatically.
