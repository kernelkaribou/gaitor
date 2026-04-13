/**
 * WebSocket client for real-time progress updates.
 */

let ws = null;
let listeners = new Map();

export function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${window.location.host}/ws/progress`;

  ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const { type, ...payload } = data;
      const typeListeners = listeners.get(type) || [];
      typeListeners.forEach((callback) => callback(payload));
    } catch (e) {
      console.error('WebSocket message parse error:', e);
    }
  };

  ws.onclose = () => {
    setTimeout(connectWebSocket, 5000);
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
}

export function onProgress(type, callback) {
  if (!listeners.has(type)) {
    listeners.set(type, []);
  }
  listeners.get(type).push(callback);

  return () => {
    const typeListeners = listeners.get(type);
    const index = typeListeners.indexOf(callback);
    if (index > -1) typeListeners.splice(index, 1);
  };
}

export function disconnectWebSocket() {
  if (ws) {
    ws.close();
    ws = null;
  }
}
