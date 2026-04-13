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
  getDiskUsage: () => request('/settings/disk'),
  getAuthStatus: () => request('/settings/auth'),

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
  renameCategory: (id, newId, newLabel) =>
    request(`/library/categories/${id}/rename`, { method: 'POST', body: JSON.stringify({ new_id: newId, new_label: newLabel }) }),
  listSubfolders: (categoryId) =>
    request(`/library/categories/${categoryId}/subfolders`),
  createSubfolder: (categoryId, name) =>
    request(`/library/categories/${categoryId}/subfolders`, { method: 'POST', body: JSON.stringify({ name }) }),
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
  moveModel: (id, subfolder) =>
    request(`/models/${id}/move`, {
      method: 'POST',
      body: JSON.stringify({ subfolder }),
    }),
  deleteModel: (id, confirmName) =>
    request(`/models/${id}`, {
      method: 'DELETE',
      body: JSON.stringify({ confirm_name: confirmName }),
    }),
  computeHash: (id) => request(`/models/${id}/hash`, { method: 'POST' }),
  getDownloadUrl: (id) => `${BASE_URL}/models/${id}/download`,
  getThumbnailUrl: (id) => `${BASE_URL}/models/${id}/thumbnail`,

  async uploadThumbnail(modelId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${BASE_URL}/models/${modelId}/thumbnail`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  deleteThumbnail: (id) => request(`/models/${id}/thumbnail`, { method: 'DELETE' }),

  async uploadModel(file, name, category, description = '', tags = '', onProgress = null) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name);
      formData.append('category', category);
      formData.append('description', description);
      formData.append('tags', tags);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE_URL}/models/upload`);

      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            onProgress({ loaded: e.loaded, total: e.total, percent: Math.round((e.loaded / e.total) * 100) });
          }
        });
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve({});
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || `HTTP ${xhr.status}`));
          } catch {
            reject(new Error(`HTTP ${xhr.status}`));
          }
        }
      };

      xhr.onerror = () => reject(new Error('Upload failed - network error'));
      xhr.send(formData);
    });
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

  // Download (formerly Retrieve)
  getProviders: () => request('/retrieve/providers'),
  resolveUrl: (url) =>
    request('/retrieve/resolve', { method: 'POST', body: JSON.stringify({ url }) }),
  startDownload: (params) =>
    request('/retrieve/download', { method: 'POST', body: JSON.stringify(params) }),
  searchModels: (query, provider = 'huggingface', limit = 20) =>
    request('/retrieve/search', { method: 'POST', body: JSON.stringify({ query, provider, limit }) }),
  listHfFiles: (repoId) => request(`/retrieve/hf/${repoId}/files`),
  getCivitaiModel: (modelId) => request(`/retrieve/civitai/${modelId}`),

  // Tasks
  getActiveTasks: () => request('/tasks'),
  cancelTask: (taskId) =>
    request(`/tasks/${taskId}/cancel`, { method: 'POST' }),
};
