import { DeviceHub } from "./hub";
import type { Env } from "./types";

export { DeviceHub };

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
};

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (url.pathname === "/health") {
      return jsonResponse({ status: "ok" });
    }

    if (url.pathname === "/api/devices") {
      const auth = request.headers.get("Authorization");
      const token = auth?.startsWith("Bearer ") ? auth.slice(7) : null;
      if (!token || token !== env.RELAY_AUTH_TOKEN) {
        return jsonResponse({ error: "unauthorized" }, 401);
      }
      const id = env.DEVICE_HUB.idFromName("global");
      const hub = env.DEVICE_HUB.get(id);
      return hub.fetch(request);
    }

    if (url.pathname === "/ws/device" || url.pathname === "/ws/client") {
      if (request.headers.get("Upgrade") !== "websocket") {
        return jsonResponse({ error: "expected websocket" }, 426);
      }
      const id = env.DEVICE_HUB.idFromName("global");
      const hub = env.DEVICE_HUB.get(id);
      return hub.fetch(request);
    }

    return jsonResponse({ error: "not_found" }, 404);
  },
};
