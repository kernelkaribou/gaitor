/**
 * WebSocket client for real-time task progress updates.
 */
import { toasts, addToast, updateToast, removeToast } from './stores.js';

let ws = null;
let reconnectTimer = null;
const taskToastMap = new Map();

export function connectWebSocket() {
  if (ws && ws.readyState <= 1) return;

  // Clear any pending reconnect timer to prevent accumulation
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${window.location.host}/ws/tasks`;

  ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'init' && data.tasks) {
        for (const task of data.tasks) {
          handleTaskUpdate(task);
        }
      } else if (data.type === 'update') {
        handleTaskUpdate(data);
      }
    } catch (e) {
      console.error('WebSocket message parse error:', e);
    }
  };

  ws.onclose = () => {
    ws = null;
    reconnectTimer = setTimeout(connectWebSocket, 5000);
  };

  ws.onerror = () => {};
}

export function disconnectWebSocket() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null; // prevent reconnect on intentional close
    ws.close();
    ws = null;
  }
}

function handleTaskUpdate(task) {
  const existingToastId = taskToastMap.get(task.task_id);

  if (task.status === 'completed') {
    if (existingToastId) {
      removeToast(existingToastId);
      taskToastMap.delete(task.task_id);
    }
    addToast({ type: 'success', title: task.message || task.title, duration: 6000 });
    window.dispatchEvent(new CustomEvent('gaitor:task-complete', { detail: task }));
  } else if (task.status === 'failed') {
    if (existingToastId) {
      removeToast(existingToastId);
      taskToastMap.delete(task.task_id);
    }
    addToast({ type: 'error', title: task.title, message: task.message, duration: 10000 });
  } else if (task.status === 'cancelled') {
    if (existingToastId) {
      removeToast(existingToastId);
      taskToastMap.delete(task.task_id);
    }
    addToast({ type: 'info', title: 'Cancelled', message: task.title, duration: 4000 });
  } else if (task.status === 'running') {
    if (existingToastId) {
      updateToast(existingToastId, {
        progress: task.progress,
        downloaded: task.downloaded,
        total: task.total,
        speed: task.speed,
        eta: task.eta,
        message: task.message,
        taskId: task.task_id,
      });
    } else {
      const toastId = addToast({
        type: 'progress',
        title: task.title,
        persistent: true,
        taskId: task.task_id,
      });
      taskToastMap.set(task.task_id, toastId);
      updateToast(toastId, {
        progress: task.progress,
        downloaded: task.downloaded,
        total: task.total,
        speed: task.speed,
        eta: task.eta,
        taskId: task.task_id,
      });
    }
  }
}
