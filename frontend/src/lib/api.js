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
  initializeLibrary: (name = 'Model Library') =>
    request('/library/initialize', { method: 'POST', body: JSON.stringify({ name }) }),
  scanLibrary: () => request('/library/scan', { method: 'POST' }),
  getCategories: () => request('/library/categories'),
  createCategory: (data) =>
    request('/library/categories', { method: 'POST', body: JSON.stringify(data) }),
  updateCategory: (id, data) =>
    request(`/library/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCategory: (id) =>
    request(`/library/categories/${id}`, { method: 'DELETE' }),

  // Models
  listModels: () => request('/models/'),
  getModel: (id) => request(`/models/${id}`),
  catalogModel: (data) =>
    request('/models/catalog', { method: 'POST', body: JSON.stringify(data) }),
  bulkCatalog: (models) =>
    request('/models/catalog/bulk', { method: 'POST', body: JSON.stringify({ models }) }),
  updateModel: (id, data) =>
    request(`/models/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  renameModel: (id, newName, renameFile = true) =>
    request(`/models/${id}/rename`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName, rename_file: renameFile }),
    }),
  deleteModel: (id, confirmName) =>
    request(`/models/${id}`, {
      method: 'DELETE',
      body: JSON.stringify({ confirm_name: confirmName }),
    }),
  computeHash: (id) => request(`/models/${id}/hash`, { method: 'POST' }),
  getDownloadUrl: (id) => `${BASE_URL}/models/${id}/download`,

  async uploadModel(file, name, category, description = '', tags = '') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('category', category);
    formData.append('description', description);
    formData.append('tags', tags);
    const response = await fetch(`${BASE_URL}/models/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  // Destinations
  listDestinations: () => request('/destinations/'),
  getDestinationModels: (destId) => request(`/destinations/${destId}/models`),
  getDestinationSyncStatus: (destId) => request(`/destinations/${destId}/status`),
  syncModelToDestination: (destId, modelId) =>
    request(`/destinations/${destId}/sync`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  bulkSyncToDestination: (destId, modelIds) =>
    request(`/destinations/${destId}/sync/bulk`, { method: 'POST', body: JSON.stringify({ model_ids: modelIds }) }),
  removeFromDestination: (destId, modelId) =>
    request(`/destinations/${destId}/remove`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  applyRenameOnDestination: (destId, modelId) =>
    request(`/destinations/${destId}/apply-rename`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),

  // Retrieve
  listProviders: () => request('/retrieve/providers'),
};
