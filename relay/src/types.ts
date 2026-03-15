// === Base ===

export interface BaseMessage {
  type: string;
  timestamp: number;
}

// === Device → Relay ===

export interface DeviceAuthMessage extends BaseMessage {
  type: "device:auth";
  token: string;
  device_id: string;
  device_name: string;
  platform: "darwin" | "linux" | "win32";
}

export interface DeviceHeartbeatMessage extends BaseMessage {
  type: "device:heartbeat";
  device_id: string;
}

export interface ResponseMessage extends BaseMessage {
  type: "response";
  request_id: string;
  device_id: string;
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export interface ResponseStreamMessage extends BaseMessage {
  type: "response:stream";
  request_id: string;
  device_id: string;
  chunk: string;
  done: boolean;
}

// === TMA → Relay ===

export interface ClientAuthMessage extends BaseMessage {
  type: "client:auth";
  token: string;
  telegram_user_id: number;
}

export interface DevicesListMessage extends BaseMessage {
  type: "devices:list";
}

export interface CommandMessage extends BaseMessage {
  type: "command";
  request_id: string;
  device_id: string;
  action: string;
  payload: Record<string, unknown>;
}

// === Relay → Client/Device ===

export interface AuthOkMessage extends BaseMessage {
  type: "auth:ok";
  devices?: DeviceInfo[];
}

export interface AuthErrorMessage extends BaseMessage {
  type: "auth:error";
  reason: string;
}

export interface DeviceOnlineMessage extends BaseMessage {
  type: "device:online";
  device_id: string;
  device_name: string;
  platform: string;
}

export interface DeviceOfflineMessage extends BaseMessage {
  type: "device:offline";
  device_id: string;
}

export interface ErrorMessage extends BaseMessage {
  type: "error";
  request_id: string;
  reason: string;
  device_id: string;
}

// === Internal ===

export type IncomingMessage =
  | DeviceAuthMessage
  | DeviceHeartbeatMessage
  | ClientAuthMessage
  | DevicesListMessage
  | CommandMessage
  | ResponseMessage
  | ResponseStreamMessage;

export interface DeviceInfo {
  device_id: string;
  device_name: string;
  platform: "darwin" | "linux" | "win32" | string;
  status: "online" | "offline";
  connected_at?: number;
  last_seen?: number;
}

export interface ConnectedDevice {
  ws: WebSocket;
  info: DeviceInfo;
  last_heartbeat: number;
}

export interface ConnectedClient {
  ws: WebSocket;
  telegram_user_id: number;
}

export interface Env {
  DEVICE_HUB: DurableObjectNamespace;
  RELAY_AUTH_TOKEN: string;
}
