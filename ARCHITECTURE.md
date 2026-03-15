# Nanobots — Architecture Overview

## What is Nanobots

A multi-agent personal AI assistant system. Users interact with their computers remotely through a Telegram Mini App (TMA). Multiple computers can be connected simultaneously, each running a nanobot agent.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              CLOUDFLARE WORKERS + DURABLE OBJECTS               │
│                   (nanobots-relay.workers.dev)                  │
│                                                                 │
│   Durable Object: DeviceHub                                     │
│   ┌───────────────────────────────────────────────────────┐     │
│   │  devices: Map<deviceId, { ws, metadata }>             │     │
│   │  clients: Map<sessionId, ws>                          │     │
│   │  registry: SQLite (offline device history)            │     │
│   │                                                       │     │
│   │  Responsibilities:                                    │     │
│   │  • Authenticate devices & TMA clients                 │     │
│   │  • Track device presence (online/offline)             │     │
│   │  • Route commands: TMA → correct device               │     │
│   │  • Route responses: device → correct TMA client       │     │
│   │  • Persist device registry across hibernations        │     │
│   └───────────────────────────────────────────────────────┘     │
└────────┬──────────────────┬─────────────────┬──────────────────┘
         │ WSS              │ WSS             │ WSS
         │                  │                 │
┌────────▼──────┐  ┌───────▼───────┐  ┌──────▼────────────┐
│ Computer 1    │  │ Computer 2    │  │   TMA Frontend    │
│ "macbook-home"│  │ "pc-work"     │  │   (Netlify)       │
│               │  │               │  │                   │
│ Python:       │  │ Python:       │  │ • Device selector │
│ • relay client│  │ • relay client│  │ • Online/Offline  │
│ • agent loop  │  │ • agent loop  │  │ • Chat terminal   │
│ • tools       │  │ • tools       │  │ • File browser    │
│ • monitor API │  │ • monitor API │  │ • Projects        │
└───────────────┘  └───────────────┘  └───────────────────┘
```

## Project Structure

```
nanobots/
├── ARCHITECTURE.md          ← You are here
├── PROTOCOL.md              ← Shared WebSocket protocol (ALL agents must follow)
├── AGENT-1-RELAY.md         ← Tasks for Agent 1 (Cloudflare Worker)
├── AGENT-2-BACKEND.md       ← Tasks for Agent 2 (Python backend)
├── AGENT-3-FRONTEND.md      ← Tasks for Agent 3 (TMA frontend)
│
├── relay/                   ← Agent 1 creates this
│   ├── src/
│   │   ├── index.ts         ← Worker entry point
│   │   ├── hub.ts           ← DeviceHub Durable Object
│   │   └── types.ts         ← Shared TypeScript types
│   ├── wrangler.toml        ← Cloudflare config
│   ├── package.json
│   └── tsconfig.json
│
├── nanobot/                 ← Agent 2 modifies this (existing Python code)
│   ├── nanobot/
│   │   ├── relay/           ← NEW: relay client module
│   │   │   ├── __init__.py
│   │   │   └── client.py    ← WebSocket client to relay
│   │   ├── agent/           ← Existing: minor refactoring
│   │   ├── monitor/         ← Existing: refactor to work via relay
│   │   ├── config/          ← Existing: add relay config fields
│   │   ├── channels/        ← Existing: keep Telegram bot channel
│   │   └── ...
│   └── pyproject.toml
│
└── tma/                     ← Agent 3 creates/modifies this
    ├── index.html           ← Main TMA (move from nanobot/monitor/tma/)
    ├── config.js            ← Runtime config (relay URL, etc.)
    └── netlify.toml         ← Netlify deploy config
```

## Component Responsibilities

### Relay Server (Agent 1)
- Always-on WebSocket hub on Cloudflare Workers
- Authenticates devices and TMA clients via shared token
- Tracks which devices are online/offline
- Routes messages bidirectionally between TMA ↔ devices
- Persists device registry in Durable Object SQLite storage
- Uses Hibernatable WebSocket API (free tier friendly)

### Python Backend (Agent 2)
- Runs on user's computer(s)
- Connects to relay server via WebSocket on startup
- Receives commands from TMA (routed through relay)
- Executes commands using existing tools (shell, files, AI agent)
- Sends responses back through relay
- Auto-reconnects on connection loss
- Existing Telegram bot channel kept for direct bot interaction

### TMA Frontend (Agent 3)
- Static site deployed on Netlify
- Connects to relay server via WebSocket
- Shows device selector with online/offline status
- Routes all commands through relay to selected device
- Existing features preserved: terminal, file browser, projects, chat

## Shared Contract

**CRITICAL**: All three components MUST follow `PROTOCOL.md` exactly.

The protocol defines:
- WebSocket endpoint paths (`/ws/device`, `/ws/client`)
- All message types and their JSON schemas
- Authentication flow
- Error handling
- Request ID format
- Config schema

## Authentication Flow

```
1. User sets a shared token in ~/.nanobot/config.json
2. Same token is set as env var RELAY_AUTH_TOKEN on Cloudflare Worker
3. Same token is configured in TMA (via config.js or env)

Device connects → sends token → relay validates → auth:ok / auth:error
TMA connects    → sends token → relay validates → auth:ok + device list
```

## What Each Agent MUST NOT Do

| Agent | Must NOT touch |
|-------|---------------|
| Agent 1 (Relay) | Python code, TMA HTML/JS |
| Agent 2 (Backend) | relay/ directory, TMA HTML/JS |
| Agent 3 (Frontend) | relay/ directory, Python code |

All agents share ONLY the protocol defined in `PROTOCOL.md`.
