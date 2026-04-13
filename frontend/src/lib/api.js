/**
 * API client for Model gAItor backend.
 */
const BASE_URL = '/api';

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  // Settings
  getVersion: () => request('/settings/version'),

  // Library
  getLibraryStatus: () => request('/library/status'),

  // Models
  listModels: () => request('/models/'),

  // Destinations
  listDestinations: () => request('/destinations/'),

  // Retrieve
  listProviders: () => request('/retrieve/providers'),
};
