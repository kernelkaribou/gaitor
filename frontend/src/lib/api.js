/**
 * API client for gAItor backend.
 */
const BASE_URL = '/api';

async function request(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body) {
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    let message = `HTTP ${response.status}`;
    if (typeof error.detail === 'string') {
      message = error.detail;
    } else if (Array.isArray(error.detail)) {
      message = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ');
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  // Settings
  getVersion: () => request('/settings/version'),
  getDiskUsage: () => request('/settings/disk'),
  getAuthStatus: () => request('/settings/auth'),
  getExportUrl: () => `${BASE_URL}/settings/export`,

  // Library
  getLibraryStatus: () => request('/library/status'),
  initializeLibrary: (name = 'Model Library') =>
    request('/library/initialize', { method: 'POST', body: JSON.stringify({ name }) }),
  scanLibrary: () => request('/library/scan', { method: 'POST' }),
  getCategories: () => request('/library/categories'),
  createCategory: (data) =>
    request('/library/categories', { method: 'POST', body: JSON.stringify(data) }),
  updateCategory: (id, data) =>
    request(`/library/categories/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) }),
  renameCategory: (id, newId, newLabel) =>
    request(`/library/categories/${encodeURIComponent(id)}/rename`, { method: 'POST', body: JSON.stringify({ new_id: newId, new_label: newLabel }) }),
  listSubfolders: (categoryId) =>
    request(`/library/categories/${encodeURIComponent(categoryId)}/subfolders`),
  deleteCategory: (id) =>
    request(`/library/categories/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  // Models
  listModels: () => request('/models/'),
  getModelStats: () => request('/models/stats'),
  getModelHostCounts: () => request('/models/host-counts'),
  getModel: (id) => request(`/models/${encodeURIComponent(id)}`),
  catalogModel: (data) =>
    request('/models/catalog', { method: 'POST', body: JSON.stringify(data) }),
  bulkCatalog: (models) =>
    request('/models/catalog/bulk', { method: 'POST', body: JSON.stringify({ models }) }),
  updateModel: (id, data) =>
    request(`/models/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) }),
  renameModel: (id, newName, renameFile = true) =>
    request(`/models/${encodeURIComponent(id)}/rename`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName, rename_file: renameFile }),
    }),
  moveModel: (id, subfolder) =>
    request(`/models/${encodeURIComponent(id)}/move`, {
      method: 'POST',
      body: JSON.stringify({ subfolder }),
    }),
  deleteModel: (id, confirmText) =>
    request(`/models/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      body: JSON.stringify({ confirm_text: confirmText }),
    }),
  computeHash: (id) => request(`/models/${encodeURIComponent(id)}/hash`, { method: 'POST' }),
  bulkUpdateModels: (modelIds, updates) =>
    request('/models/bulk/update', { method: 'POST', body: JSON.stringify({ model_ids: modelIds, ...updates }) }),
  bulkDeleteModels: (modelIds, confirmText) =>
    request('/models/bulk/delete', { method: 'POST', body: JSON.stringify({ model_ids: modelIds, confirm_text: confirmText }) }),
  getDownloadUrl: (id) => `${BASE_URL}/models/${encodeURIComponent(id)}/download`,
  getThumbnailUrl: (id) => `${BASE_URL}/models/${encodeURIComponent(id)}/thumbnail`,
  getModelHosts: (id) =>
    request(`/models/${encodeURIComponent(id)}/hosts`),
  getModelGroup: (id) =>
    request(`/models/${encodeURIComponent(id)}/group`),
  setModelGroup: (id, modelIds) =>
    request(`/models/${encodeURIComponent(id)}/group`, { method: 'PUT', body: JSON.stringify({ model_ids: modelIds }) }),
  removeFromGroup: (id) =>
    request(`/models/${encodeURIComponent(id)}/group`, { method: 'DELETE' }),

  async uploadThumbnail(modelId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${BASE_URL}/models/${encodeURIComponent(modelId)}/thumbnail`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  deleteThumbnail: (id) => request(`/models/${encodeURIComponent(id)}/thumbnail`, { method: 'DELETE' }),

  async uploadModel(file, name, category, description = '', tags = '', onProgress = null, subfolder = '', baseModel = '', customFilename = '') {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name);
      formData.append('category', category);
      formData.append('description', description);
      formData.append('tags', tags);
      formData.append('subfolder', subfolder);
      formData.append('base_model', baseModel);
      formData.append('custom_filename', customFilename);

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

  // Hosts
  listHosts: () => request('/hosts/'),
  getHostModels: (hostId) => request(`/hosts/${encodeURIComponent(hostId)}/models`),
  getHostSyncStatus: (hostId) => request(`/hosts/${encodeURIComponent(hostId)}/status`),
  syncModelToHost: (hostId, modelId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/sync`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  bulkSyncToHost: (hostId, modelIds) =>
    request(`/hosts/${encodeURIComponent(hostId)}/sync/bulk`, { method: 'POST', body: JSON.stringify({ model_ids: modelIds }) }),
  removeFromHost: (hostId, modelId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/remove`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  applyRenameOnHost: (hostId, modelId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/apply-rename`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  scanHost: (hostId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/scan`, { method: 'POST' }),
  linkHostModel: (hostId, relativePath, libraryModelId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/link`, { method: 'POST', body: JSON.stringify({ relative_path: relativePath, library_model_id: libraryModelId }) }),
  bulkLinkHostModels: (hostId, links) =>
    request(`/hosts/${encodeURIComponent(hostId)}/link/bulk`, { method: 'POST', body: JSON.stringify({ links }) }),
  importFromHost: (hostId, data) =>
    request(`/hosts/${encodeURIComponent(hostId)}/import`, { method: 'POST', body: JSON.stringify(data) }),
  addIgnorePattern: (hostId, pattern) =>
    request(`/hosts/${encodeURIComponent(hostId)}/ignore`, { method: 'POST', body: JSON.stringify({ pattern }) }),
  getIgnorePatterns: (hostId) =>
    request(`/hosts/${encodeURIComponent(hostId)}/ignore`),
  removeIgnorePattern: (hostId, pattern) =>
    request(`/hosts/${encodeURIComponent(hostId)}/ignore`, { method: 'DELETE', body: JSON.stringify({ pattern }) }),
  deleteUnmanagedFile: (hostId, relativePath) =>
    request(`/hosts/${encodeURIComponent(hostId)}/delete-file`, { method: 'POST', body: JSON.stringify({ relative_path: relativePath }) }),

  // Download (formerly Retrieve)
  getProviders: () => request('/retrieve/providers'),
  resolveUrl: (url) =>
    request('/retrieve/resolve', { method: 'POST', body: JSON.stringify({ url }) }),
  startDownload: (params) =>
    request('/retrieve/download', { method: 'POST', body: JSON.stringify(params) }),
  listHfFiles: (repoId) => request(`/retrieve/hf/${encodeURIComponent(repoId)}/files`),
  getCivitaiModel: (modelId) => request(`/retrieve/civitai/${encodeURIComponent(modelId)}`),

  // Bookmarks
  listBookmarks: () => request('/bookmarks/'),
  createBookmark: (data) =>
    request('/bookmarks/', { method: 'POST', body: JSON.stringify(data) }),
  updateBookmark: (id, data) =>
    request(`/bookmarks/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteBookmark: (id) =>
    request(`/bookmarks/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getBookmarkThumbnailUrl: (id) => `${BASE_URL}/bookmarks/${encodeURIComponent(id)}/thumbnail`,
  async uploadBookmarkThumbnail(bookmarkId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${BASE_URL}/bookmarks/${encodeURIComponent(bookmarkId)}/thumbnail`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },
  deleteBookmarkThumbnail: (id) =>
    request(`/bookmarks/${encodeURIComponent(id)}/thumbnail`, { method: 'DELETE' }),

  // Tasks
  getActiveTasks: () => request('/tasks'),
  cancelTask: (taskId) =>
    request(`/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' }),
};
