/**
 * Svelte stores for application state.
 */
import { writable } from 'svelte/store';

export const updateInfo = writable(null); // { latest, release_url } when update available

/**
 * Global toast notifications and active tasks.
 * Each toast: { id, type, title, message, progress, speed, eta, persistent, timestamp }
 * type: 'info' | 'success' | 'error' | 'progress'
 */
export const toasts = writable([]);

let toastCounter = 0;

export function addToast({ type = 'info', title, message, persistent = false, duration = 5000 }) {
  const id = ++toastCounter;
  const toast = { id, type, title, message, persistent, timestamp: Date.now(), progress: null };
  toasts.update(t => [...t, toast]);
  if (!persistent && type !== 'progress') {
    setTimeout(() => removeToast(id), duration);
  }
  return id;
}

export function updateToast(id, updates) {
  toasts.update(t => t.map(toast => toast.id === id ? { ...toast, ...updates } : toast));
}

export function removeToast(id) {
  toasts.update(t => t.filter(toast => toast.id !== id));
}
