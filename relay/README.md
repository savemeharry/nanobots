# Nanobots Relay Server

WebSocket relay hub on Cloudflare Workers + Durable Objects. Connects TMA clients to user computers.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Login to Cloudflare:
   ```bash
   npx wrangler login
   ```

3. Set the shared auth token:
   ```bash
   npx wrangler secret put RELAY_AUTH_TOKEN
   ```

4. Deploy:
   ```bash
   npm run deploy
   ```

5. Note your worker URL: `nanobots-relay.<subdomain>.workers.dev`

## Local Development

```bash
npm run dev
```

## Endpoints

| Path | Description |
|------|-------------|
| `GET /health` | Health check |
| `GET /api/devices` | Device list (Bearer token auth) |
| `GET /ws/device` | WebSocket for device connections |
| `GET /ws/client` | WebSocket for TMA client connections |

## Logs

```bash
npm run tail
```
