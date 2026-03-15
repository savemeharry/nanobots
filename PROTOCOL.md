# Nanobots WebSocket Protocol v1

This is the **shared contract** between ALL components. Every agent MUST follow this protocol exactly.
Any deviation will break compatibility between relay, backend, and frontend.

---

## Connection Flow

### Device (Computer) → Relay
1. Connect WSS to `wss://<relay-domain>/ws/device`
2. Send `device:auth` message
3. Receive `auth:ok` or `auth:error`
4. Start sending `device:heartbeat` every 30 seconds
5. Listen for `command` messages from TMA clients
6. Send `response` messages back

### TMA (Frontend) → Relay
1. Connect WSS to `wss://<relay-domain>/ws/client`
2. Send `client:auth` message
3. Receive `auth:ok` + initial device list
4. Listen for `device:online`, `device:offline` events
5. Send `command` messages targeting a specific device
6. Receive `response` messages from devices

---

## Authentication

All auth uses a shared secret token configured by the user.

```
Token format: any string, minimum 16 characters
Header alternative: Authorization: Bearer <token>  (for HTTP endpoints only)
```

---

## Message Format

All messages are JSON. Every message has a `type` field.

```typescript
interface BaseMessage {
  type: string;
  timestamp: number; // Unix epoch milliseconds
}
```

---

## Device → Relay Messages

### `device:auth`
Sent immediately after WebSocket connection opens.

```json
{
  "type": "device:auth",
  "token": "shared-secret-token",
  "device_id": "macbook-home",
  "device_name": "MacBook Home",
  "platform": "darwin",
  "timestamp": 1710000000000
}
```

- `device_id`: unique slug, alphanumeric + hyphens, max 32 chars. User sets this in config.
- `device_name`: human-readable label, max 64 chars.
- `platform`: one of `"darwin"`, `"linux"`, `"win32"`.

### `device:heartbeat`
Sent every 30 seconds to confirm liveness.

```json
{
  "type": "device:heartbeat",
  "device_id": "macbook-home",
  "timestamp": 1710000030000
}
```

### `response`
Reply to a command from TMA.

```json
{
  "type": "response",
  "request_id": "req_abc123",
  "device_id": "macbook-home",
  "success": true,
  "data": { ... },
  "timestamp": 1710000005000
}
```

The `data` field structure depends on the original command's `action`:

#### Response data for `action: "chat"`
```json
{
  "content": "Here are your files:\n- file1.txt\n- file2.txt"
}
```

#### Response data for `action: "exec"`
```json
{
  "stdout": "total 42\ndrwxr-xr-x ...",
  "stderr": "",
  "exit_code": 0
}
```

#### Response data for `action: "files:list"`
```json
{
  "path": "/Users/user/Desktop",
  "entries": [
    { "name": "file.txt", "type": "file", "size": 1024, "modified": "2025-03-14T10:00:00Z" },
    { "name": "folder", "type": "directory", "size": 0, "modified": "2025-03-14T09:00:00Z" }
  ]
}
```

#### Response data for `action: "files:read"`
```json
{
  "path": "/Users/user/Desktop/file.txt",
  "content": "file contents here",
  "encoding": "utf-8"
}
```

#### Response data for `action: "status"`
```json
{
  "agent_status": "idle",
  "uptime_seconds": 3600,
  "platform": "darwin",
  "hostname": "MacBook-Pro.local",
  "python_version": "3.11.5"
}
```

### `response:stream`
For streaming long responses (chat). Sent as multiple messages.

```json
{
  "type": "response:stream",
  "request_id": "req_abc123",
  "device_id": "macbook-home",
  "chunk": "partial text...",
  "done": false,
  "timestamp": 1710000005000
}
```

When streaming is complete, send final chunk with `"done": true`.

---

## TMA → Relay Messages

### `client:auth`
Sent immediately after WebSocket connection opens.

```json
{
  "type": "client:auth",
  "token": "shared-secret-token",
  "telegram_user_id": 123456789,
  "timestamp": 1710000000000
}
```

### `devices:list`
Request current device statuses.

```json
{
  "type": "devices:list",
  "timestamp": 1710000000000
}
```

### `command`
Send a command to a specific device.

```json
{
  "type": "command",
  "request_id": "req_abc123",
  "device_id": "macbook-home",
  "action": "chat",
  "payload": {
    "content": "Show files on desktop"
  },
  "timestamp": 1710000000000
}
```

#### Supported actions and their payloads:

| action | payload | description |
|--------|---------|-------------|
| `chat` | `{ "content": "message text" }` | Send message to AI agent |
| `exec` | `{ "command": "ls -la", "cwd": "/optional/path" }` | Execute shell command |
| `files:list` | `{ "path": "/Users/user/Desktop" }` | List directory |
| `files:read` | `{ "path": "/Users/user/file.txt" }` | Read file content |
| `files:roots` | `{}` | Get available root directories |
| `status` | `{}` | Get device status |
| `projects:list` | `{}` | List projects |
| `projects:create` | `{ "name": "my-project" }` | Create project |
| `projects:select` | `{ "name": "my-project" }` | Select project |

---

## Relay → TMA Messages

### `auth:ok`
Successful authentication. Includes initial device list.

```json
{
  "type": "auth:ok",
  "devices": [
    {
      "device_id": "macbook-home",
      "device_name": "MacBook Home",
      "platform": "darwin",
      "status": "online",
      "connected_at": 1710000000000
    },
    {
      "device_id": "pc-work",
      "device_name": "PC Work",
      "platform": "win32",
      "status": "offline",
      "last_seen": 1709990000000
    }
  ],
  "timestamp": 1710000000000
}
```

### `auth:error`
Authentication failed.

```json
{
  "type": "auth:error",
  "reason": "invalid_token",
  "timestamp": 1710000000000
}
```

### `device:online`
A device just connected.

```json
{
  "type": "device:online",
  "device_id": "macbook-home",
  "device_name": "MacBook Home",
  "platform": "darwin",
  "timestamp": 1710000000000
}
```

### `device:offline`
A device disconnected.

```json
{
  "type": "device:offline",
  "device_id": "macbook-home",
  "timestamp": 1710000000000
}
```

### `response` / `response:stream`
Forwarded from device to TMA (same format as device→relay, relay just passes through).

---

## Relay → Device Messages

### `auth:ok`
```json
{
  "type": "auth:ok",
  "timestamp": 1710000000000
}
```

### `auth:error`
```json
{
  "type": "auth:error",
  "reason": "invalid_token",
  "timestamp": 1710000000000
}
```

### `command`
Forwarded from TMA to device (same format, relay just passes through).

---

## HTTP Endpoints (Relay)

For TMA initial load and health checks. These are optional REST alternatives.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Returns `{ "status": "ok" }` |
| GET | `/api/devices` | Bearer token | Returns device list (same as `devices:list` response) |

---

## Error Handling

### Connection Errors
- Device: reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- TMA: reconnect with backoff (1s, 2s, 4s, max 30s), show "Reconnecting..." in UI

### Command Errors
If a command fails on the device, respond with:
```json
{
  "type": "response",
  "request_id": "req_abc123",
  "device_id": "macbook-home",
  "success": false,
  "error": "Permission denied",
  "timestamp": 1710000005000
}
```

### Device Not Found
If TMA sends command to offline device, relay responds:
```json
{
  "type": "error",
  "request_id": "req_abc123",
  "reason": "device_offline",
  "device_id": "macbook-home",
  "timestamp": 1710000000000
}
```

---

## Request ID Format

Generated by TMA: `req_` + 12 random alphanumeric characters.
Example: `req_a8f3k2m9x1b4`

---

## Config Schema (shared)

All components read from the same conceptual config:

```json
{
  "relay": {
    "url": "wss://nanobots-relay.<user>.workers.dev",
    "token": "your-shared-secret-token-minimum-16-chars"
  },
  "device": {
    "id": "macbook-home",
    "name": "MacBook Home"
  }
}
```

- Python backend reads this from `~/.nanobot/config.json` (field `relay` and `device`)
- TMA reads `relay.url` and `relay.token` from its config (injected at build or fetched from relay)
- Relay reads `token` from Cloudflare Worker environment variable `RELAY_AUTH_TOKEN`
