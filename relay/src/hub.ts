import type {
  Env,
  IncomingMessage,
  DeviceInfo,
  ConnectedDevice,
  ConnectedClient,
  DeviceAuthMessage,
  DeviceHeartbeatMessage,
  ClientAuthMessage,
  CommandMessage,
  ResponseMessage,
  ResponseStreamMessage,
} from "./types";

export class DeviceHub implements DurableObject {
  private devices = new Map<string, ConnectedDevice>();
  private clients = new Map<string, ConnectedClient>();
  private initialized = false;

  constructor(
    private ctx: DurableObjectState,
    private env: Env,
  ) {}

  private ensureSchema(): void {
    if (this.initialized) return;
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'unknown',
        last_seen INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0
      )
    `);
    this.initialized = true;
  }

  async fetch(request: Request): Promise<Response> {
    this.ensureSchema();
    const url = new URL(request.url);

    if (url.pathname === "/api/devices") {
      const devices = this.getDeviceList();
      return new Response(JSON.stringify({ devices, timestamp: Date.now() }), {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    const tag = url.pathname === "/ws/device" ? "device" : "client";
    this.ctx.acceptWebSocket(server, [tag]);

    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws: WebSocket, raw: string | ArrayBuffer): Promise<void> {
    this.ensureSchema();
    const text = typeof raw === "string" ? raw : new TextDecoder().decode(raw);

    let msg: IncomingMessage;
    try {
      msg = JSON.parse(text);
    } catch {
      this.send(ws, { type: "error", reason: "invalid_json", request_id: "", device_id: "", timestamp: Date.now() });
      return;
    }

    switch (msg.type) {
      case "device:auth":
        this.handleDeviceAuth(ws, msg as DeviceAuthMessage);
        break;
      case "device:heartbeat":
        this.handleHeartbeat(msg as DeviceHeartbeatMessage);
        break;
      case "client:auth":
        this.handleClientAuth(ws, msg as ClientAuthMessage);
        break;
      case "devices:list":
        this.handleDevicesList(ws);
        break;
      case "command":
        this.handleCommand(ws, msg as CommandMessage);
        break;
      case "response":
      case "response:stream":
        this.handleResponse(msg as ResponseMessage | ResponseStreamMessage);
        break;
      default:
        this.send(ws, { type: "error", reason: "unknown_type", request_id: "", device_id: "", timestamp: Date.now() });
    }
  }

  async webSocketClose(ws: WebSocket, code: number, _reason: string): Promise<void> {
    this.ensureSchema();
    this.cleanupConnection(ws);
  }

  async webSocketError(ws: WebSocket, _error: unknown): Promise<void> {
    this.ensureSchema();
    this.cleanupConnection(ws);
  }

  async alarm(): Promise<void> {
    this.ensureSchema();
    const now = Date.now();
    for (const [id, device] of this.devices) {
      if (now - device.last_heartbeat > 90_000) {
        try {
          device.ws.close(1000, "heartbeat_timeout");
        } catch {
          // ws may already be closed
        }
        this.devices.delete(id);
        this.updateDeviceLastSeen(id, now);
        this.broadcastToClients({
          type: "device:offline",
          device_id: id,
          timestamp: now,
        });
      }
    }
    if (this.devices.size > 0) {
      this.ctx.storage.setAlarm(Date.now() + 90_000);
    }
  }

  // --- Handlers ---

  private handleDeviceAuth(ws: WebSocket, msg: DeviceAuthMessage): void {
    if (!this.authenticateToken(msg.token)) {
      this.send(ws, { type: "auth:error", reason: "invalid_token", timestamp: Date.now() });
      ws.close(4001, "invalid_token");
      return;
    }

    const now = Date.now();
    const info: DeviceInfo = {
      device_id: msg.device_id,
      device_name: msg.device_name,
      platform: msg.platform,
      status: "online",
      connected_at: now,
    };

    this.devices.set(msg.device_id, { ws, info, last_heartbeat: now });
    this.upsertDevice(msg.device_id, msg.device_name, msg.platform, now);
    this.send(ws, { type: "auth:ok", timestamp: now });

    this.broadcastToClients({
      type: "device:online",
      device_id: msg.device_id,
      device_name: msg.device_name,
      platform: msg.platform,
      timestamp: now,
    });

    // Arm heartbeat alarm
    this.ctx.storage.setAlarm(Date.now() + 90_000);
  }

  private handleHeartbeat(msg: DeviceHeartbeatMessage): void {
    const device = this.devices.get(msg.device_id);
    if (device) {
      device.last_heartbeat = Date.now();
    }
  }

  private handleClientAuth(ws: WebSocket, msg: ClientAuthMessage): void {
    if (!this.authenticateToken(msg.token)) {
      this.send(ws, { type: "auth:error", reason: "invalid_token", timestamp: Date.now() });
      ws.close(4001, "invalid_token");
      return;
    }

    const sessionId = crypto.randomUUID();
    this.clients.set(sessionId, { ws, telegram_user_id: msg.telegram_user_id });

    const tags = this.ctx.getTags(ws);
    // Re-tag with session id for cleanup
    // Note: tags are set at accept time and can't be changed, so we store mapping differently
    // We'll look up by ws reference in cleanup

    this.send(ws, {
      type: "auth:ok",
      devices: this.getDeviceList(),
      timestamp: Date.now(),
    });
  }

  private handleDevicesList(ws: WebSocket): void {
    this.send(ws, {
      type: "auth:ok",
      devices: this.getDeviceList(),
      timestamp: Date.now(),
    });
  }

  private handleCommand(_ws: WebSocket, msg: CommandMessage): void {
    const device = this.devices.get(msg.device_id);
    if (!device) {
      this.send(_ws, {
        type: "error",
        request_id: msg.request_id,
        reason: "device_offline",
        device_id: msg.device_id,
        timestamp: Date.now(),
      });
      return;
    }
    // Forward command to device as-is
    this.send(device.ws, msg);
  }

  private handleResponse(msg: ResponseMessage | ResponseStreamMessage): void {
    // Broadcast to all clients — client filters by request_id
    this.broadcastToClients(msg);
  }

  // --- Helpers ---

  private authenticateToken(token: string): boolean {
    return token === this.env.RELAY_AUTH_TOKEN;
  }

  private send(ws: WebSocket, data: Record<string, unknown>): void {
    try {
      ws.send(JSON.stringify(data));
    } catch {
      // connection may be dead
    }
  }

  private broadcastToClients(data: Record<string, unknown>): void {
    for (const [, client] of this.clients) {
      this.send(client.ws, data);
    }
  }

  private cleanupConnection(ws: WebSocket): void {
    const now = Date.now();

    // Check devices
    for (const [id, device] of this.devices) {
      if (device.ws === ws) {
        this.devices.delete(id);
        this.updateDeviceLastSeen(id, now);
        this.broadcastToClients({
          type: "device:offline",
          device_id: id,
          timestamp: now,
        });
        return;
      }
    }

    // Check clients
    for (const [sessionId, client] of this.clients) {
      if (client.ws === ws) {
        this.clients.delete(sessionId);
        return;
      }
    }
  }

  private getDeviceList(): DeviceInfo[] {
    const devices: DeviceInfo[] = [];

    // Online devices from memory
    const onlineIds = new Set<string>();
    for (const [id, device] of this.devices) {
      onlineIds.add(id);
      devices.push({ ...device.info });
    }

    // Offline devices from SQLite
    const rows = this.ctx.storage.sql.exec(
      "SELECT device_id, device_name, platform, last_seen FROM devices"
    );
    for (const row of rows) {
      const id = row.device_id as string;
      if (!onlineIds.has(id)) {
        devices.push({
          device_id: id,
          device_name: row.device_name as string,
          platform: row.platform as string,
          status: "offline",
          last_seen: row.last_seen as number,
        });
      }
    }

    return devices;
  }

  private upsertDevice(deviceId: string, deviceName: string, platform: string, now: number): void {
    this.ctx.storage.sql.exec(
      `INSERT INTO devices (device_id, device_name, platform, last_seen, created_at)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(device_id) DO UPDATE SET device_name = ?, platform = ?, last_seen = ?`,
      deviceId, deviceName, platform, now, now,
      deviceName, platform, now,
    );
  }

  private updateDeviceLastSeen(deviceId: string, now: number): void {
    this.ctx.storage.sql.exec(
      "UPDATE devices SET last_seen = ? WHERE device_id = ?",
      now, deviceId,
    );
  }
}
