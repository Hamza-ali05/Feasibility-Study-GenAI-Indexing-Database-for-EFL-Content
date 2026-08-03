
import { API_URL } from "./apiClient";

function toWsBase(httpUrl) {
  const base = (httpUrl || "http://localhost:8000").replace(/\/$/, "");
  if (base.startsWith("https://")) {
    return `wss://${base.slice("https://".length)}`;
  }
  if (base.startsWith("http://")) {
    return `ws://${base.slice("http://".length)}`;
  }
  if (base.startsWith("ws://") || base.startsWith("wss://")) {
    return base;
  }
  return `ws://${base}`;
}

export function connectPipelineSocket(onMessage, onStatusChange) {
  const url = `${toWsBase(API_URL)}/ws/pipeline`;
  let current = null;
  let closedByUser = false;
  let attempt = 0;
  let reconnectTimer = null;

  const clearReconnect = () => {
    if (reconnectTimer != null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const notifyStatus = (connected) => {
    if (typeof onStatusChange === "function") {
      onStatusChange(connected);
    }
  };

  const scheduleReconnect = () => {
    if (closedByUser) return;
    const delay = Math.min(1000 * 2 ** attempt, 10000);
    attempt += 1;
    clearReconnect();
    reconnectTimer = setTimeout(open, delay);
  };

  const open = () => {
    clearReconnect();
    const ws = new WebSocket(url);
    current = ws;

    ws.onopen = () => {
      attempt = 0;
      notifyStatus(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (typeof onMessage === "function") {
          onMessage(data);
        }
      } catch (err) {

      }
    };

    ws.onerror = () => {

    };

    ws.onclose = () => {
      notifyStatus(false);
      if (current === ws && !closedByUser) {
        scheduleReconnect();
      }
    };
  };

  const handle = {
    get readyState() {
      return current ? current.readyState : WebSocket.CLOSED;
    },
    close() {
      closedByUser = true;
      clearReconnect();
      if (current) {
        try {
          current.close();
        } catch (e) {

        }
        current = null;
      }
    },
  };

  handle.__eflClose = () => handle.close();

  open();
  return handle;
}

export function disconnectSocket(ws) {
  if (!ws) return;
  if (typeof ws.__eflClose === "function") {
    ws.__eflClose();
    return;
  }
  if (typeof ws.close === "function") {
    try {
      ws.close();
    } catch (e) {

    }
  }
}
