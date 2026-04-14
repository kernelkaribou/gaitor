<script>
  import { api } from '../lib/api.js';
  import { isSafeUrl } from '../lib/utils.js';
  import { onMount, onDestroy } from 'svelte';

  let { model, categories, formatSize, onClose, onUpdated, onDelete } = $props();

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose();
  }
  onMount(() => document.addEventListener('keydown', handleKeydown));
  onDestroy(() => document.removeEventListener('keydown', handleKeydown));

  let editing = $state(false);
  let saving = $state(false);
  let hashing = $state(false);
  let error = $state(null);

  // Edit form state
  let editName = $state('');
  let editFilename = $state('');
  let editCategory = $state('');
  let editSubfolder = $state('');
  let editDescription = $state('');
  let editSourceUrl = $state('');
  let editBaseModel = $state('');
  let editTags = $state('');

  // Original values snapshot for dirty tracking
  let origName = $state('');
  let origFilename = $state('');
  let origCategory = $state('');
  let origSubfolder = $state('');
  let origDescription = $state('');
  let origSourceUrl = $state('');
  let origBaseModel = $state('');
  let origTags = $state('');

  // Path autocomplete
  let knownSubfolders = $state([]);
  let showPathSuggestions = $state(false);
  let pathInputFocused = $state(false);

  let filteredSuggestions = $derived(
    editSubfolder.trim()
      ? knownSubfolders.filter(s => s.toLowerCase().startsWith(editSubfolder.toLowerCase()) && s !== editSubfolder)
      : []
  );
  let isNewPath = $derived(
    editSubfolder.trim() !== '' && !knownSubfolders.includes(editSubfolder.trim()) && editSubfolder.trim() !== origSubfolder
  );

  // Thumbnail
  let thumbUrl = $derived(model.thumbnail ? api.getThumbnailUrl(model.id) + '?t=' + Date.now() : null);
  let uploadingThumb = $state(false);

  // Sync to host
  let showSyncPicker = $state(false);
  let hosts = $state([]);
  let syncingTo = $state({});
  let loadingHosts = $state(false);
  let confirmSyncHost = $state(null);

  function getModelSubfolder() {
    const parts = model.relative_path.split('/');
    return parts.length > 2 ? parts.slice(1, -1).join('/') : '';
  }

  function getFilenameBase() {
    const fn = model.filename || '';
    const dot = fn.lastIndexOf('.');
    return dot > 0 ? fn.substring(0, dot) : fn;
  }

  function getFilenameExt() {
    const fn = model.filename || '';
    const dot = fn.lastIndexOf('.');
    return dot > 0 ? fn.substring(dot) : '';
  }

  function startEditing() {
    editName = model.name;
    editFilename = getFilenameBase();
    editCategory = model.category;
    editSubfolder = getModelSubfolder();
    editDescription = model.description || '';
    editSourceUrl = model.source?.url || '';
    editBaseModel = model.base_model || '';
    editTags = (model.tags || []).join(', ');

    origName = editName;
    origFilename = editFilename;
    origCategory = editCategory;
    origSubfolder = editSubfolder;
    origDescription = editDescription;
    origSourceUrl = editSourceUrl;
    origBaseModel = editBaseModel;
    origTags = editTags;

    editing = true;
    loadSubfolders(editCategory);
  }

  let hasChanges = $derived(
    editName !== origName ||
    editFilename !== origFilename ||
    editCategory !== origCategory ||
    editSubfolder !== origSubfolder ||
    editDescription !== origDescription ||
    editSourceUrl !== origSourceUrl ||
    editBaseModel !== origBaseModel ||
    editTags !== origTags
  );

  async function loadSubfolders(categoryId) {
    try {
      const data = await api.listSubfolders(categoryId);
      knownSubfolders = data.subfolders || [];
    } catch {
      knownSubfolders = [];
    }
  }

  function handleCategoryChange() {
    loadSubfolders(editCategory);
    if (editCategory !== origCategory) {
      editSubfolder = '';
    }
  }

  function selectSuggestion(suggestion) {
    editSubfolder = suggestion;
    showPathSuggestions = false;
  }

  async function saveEdits() {
    saving = true;
    error = null;
    try {
      const tags = editTags.split(',').map(t => t.trim()).filter(Boolean);
      const updates = {};

      if (editName !== origName) updates.name = editName;
      if (editDescription !== origDescription) updates.description = editDescription;
      if (editCategory !== origCategory) updates.category = editCategory;
      if (editTags !== origTags) updates.tags = tags;
      if (editSourceUrl !== origSourceUrl) updates.source_url = editSourceUrl || null;
      if (editBaseModel !== origBaseModel) updates.base_model = editBaseModel.trim() || '';
      if (editFilename !== origFilename) updates.filename = editFilename + getFilenameExt();
      if (editSubfolder !== origSubfolder) updates.subfolder = editSubfolder;

      await api.updateModel(model.id, updates);
      editing = false;
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    saving = false;
  }

  async function handleHash() {
    error = null;
    hashing = true;
    try {
      await api.computeHash(model.id);
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    hashing = false;
  }

  async function handleThumbnailUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    uploadingThumb = true;
    error = null;
    try {
      await api.uploadThumbnail(model.id, file);
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    uploadingThumb = false;
  }

  async function handleThumbnailRemove() {
    error = null;
    try {
      await api.deleteThumbnail(model.id);
      onUpdated();
    } catch (err) {
      error = err.message;
    }
  }

  async function openSyncPicker() {
    showSyncPicker = true;
    loadingHosts = true;
    confirmSyncHost = null;
    try {
      const data = await api.listHosts();
      hosts = data.hosts || [];
    } catch (err) {
      error = err.message;
    }
    loadingHosts = false;
  }

  async function syncToHost(hostId) {
    syncingTo = { ...syncingTo, [hostId]: true };
    confirmSyncHost = null;
    error = null;
    try {
      await api.syncModelToHost(hostId, model.id);
    } catch (err) {
      error = err.message;
    }
    syncingTo = { ...syncingTo, [hostId]: false };
  }

  function formatHistoryEntry(entry) {
    const d = entry.details || {};
    switch (entry.action) {
      case 'added':
        if (d.method === 'upload') return 'Uploaded to library';
        if (d.method === 'catalog') return 'Cataloged from scan';
        if (d.method === 'download') return `Downloaded from ${d.source || 'external source'}`;
        return 'Added to library';
      case 'renamed': {
        const parts = [];
        if (d.from_name) parts.push(`"${d.from_name}" \u2192 "${d.to_name}"`);
        if (d.from_filename) parts.push(`file: ${d.from_filename} \u2192 ${d.to_filename}`);
        return parts.length ? `Renamed: ${parts.join(', ')}` : 'Renamed';
      }
      case 'metadata_updated': {
        const changes = [];
        if (d.category) changes.push(`category ${d.category.from} \u2192 ${d.category.to}`);
        if (d.subfolder) changes.push(`path ${d.subfolder.from} \u2192 ${d.subfolder.to}`);
        if (d.filename) changes.push(`file ${d.filename.from} \u2192 ${d.filename.to}`);
        if (d.tags) {
          const from = Array.isArray(d.tags.from) ? d.tags.from : [];
          const to = Array.isArray(d.tags.to) ? d.tags.to : [];
          const added = to.filter(t => !from.includes(t));
          const removed = from.filter(t => !to.includes(t));
          if (added.length) changes.push(`tags added: ${added.join(', ')}`);
          if (removed.length) changes.push(`tags removed: ${removed.join(', ')}`);
          if (!added.length && !removed.length) changes.push('tags updated');
        }
        if (d.name) changes.push(`name "${d.name.from}" \u2192 "${d.name.to}"`);
        if (d.description) changes.push('description updated');
        if (d.source_url) changes.push(`source URL ${d.source_url.to ? 'set' : 'cleared'}`);
        if (d.base_model) changes.push(`base model ${d.base_model.to ? `set to "${d.base_model.to}"` : 'cleared'}`);
        return changes.length ? changes.join('; ') : 'Metadata updated';
      }
      case 'synced':
        return `Synced to ${d.host || 'host'}`;
      case 'moved':
        return `Moved to ${d.to || 'new location'}`;
      default:
        return entry.action;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="fixed inset-0 bg-black/50 z-40" onclick={onClose}></div>

<!-- Slide-over panel -->
<div class="fixed right-0 top-0 bottom-0 w-full max-w-xl bg-gray-800 border-l border-gray-700 z-50 overflow-y-auto">
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-lg font-semibold text-gray-100">Model Details</h2>
      <button class="text-gray-400 hover:text-gray-200 text-xl" onclick={onClose}>{'\u2715'}</button>
    </div>

    {#if error}
      <div class="bg-red-900/30 border border-red-700 rounded-md px-3 py-2 mb-4 text-red-300 text-sm">
        {error}
      </div>
    {/if}

    <!-- Thumbnail -->
    <div class="mb-6">
      {#if thumbUrl}
        <div class="relative group">
          <div class="w-full flex items-center justify-center bg-gray-900 rounded-lg border border-gray-700" style="max-height: 400px;">
            <img src={thumbUrl} alt={model.name} class="max-w-full max-h-[400px] object-contain rounded-lg" />
          </div>
          <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
            <label class="px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-200 cursor-pointer">
              Change
              <input type="file" accept="image/*" onchange={handleThumbnailUpload} class="hidden" />
            </label>
            <button class="px-3 py-1.5 text-xs rounded bg-red-900/50 hover:bg-red-800 text-red-300" onclick={handleThumbnailRemove}>Remove</button>
          </div>
        </div>
      {:else}
        <label class="block w-full h-24 border-2 border-dashed border-gray-600 rounded-lg flex items-center justify-center text-gray-500 text-sm hover:border-green-600/50 hover:text-gray-400 cursor-pointer transition-colors">
          {uploadingThumb ? 'Uploading...' : 'Click to add thumbnail'}
          <input type="file" accept="image/*" onchange={handleThumbnailUpload} class="hidden" disabled={uploadingThumb} />
        </label>
      {/if}
    </div>

    {#if editing}
      <!-- Unified Edit Form -->
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Name</label>
          <input bind:value={editName} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" />
          <p class="text-xs text-gray-600 mt-0.5">How this model appears in the UI</p>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Filename</label>
          <div class="flex items-center gap-0">
            <input bind:value={editFilename} class="flex-1 bg-gray-900 border border-gray-600 rounded-l px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-green-500" />
            <span class="bg-gray-700 border border-l-0 border-gray-600 rounded-r px-3 py-2 text-sm text-gray-400 font-mono">{getFilenameExt()}</span>
          </div>
          <p class="text-xs text-gray-600 mt-0.5">Physical file name on disk</p>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Category</label>
          <select bind:value={editCategory} onchange={handleCategoryChange} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500">
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
        </div>

        <div class="relative">
          <label class="block text-sm text-gray-400 mb-1">Path</label>
          <input
            bind:value={editSubfolder}
            onfocus={() => { pathInputFocused = true; showPathSuggestions = true; }}
            onblur={() => setTimeout(() => { pathInputFocused = false; showPathSuggestions = false; }, 200)}
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-green-500"
            placeholder="Leave empty for category root"
          />
          {#if isNewPath}
            <p class="text-xs text-yellow-400 mt-0.5">New path will be created</p>
          {/if}
          {#if showPathSuggestions && filteredSuggestions.length > 0}
            <div class="absolute z-10 mt-1 w-full bg-gray-900 border border-gray-600 rounded shadow-lg max-h-32 overflow-y-auto">
              {#each filteredSuggestions as suggestion}
                <button
                  class="w-full text-left px-3 py-1.5 text-sm text-gray-300 font-mono hover:bg-gray-700 transition-colors"
                  onmousedown={(e) => { e.preventDefault(); selectSuggestion(suggestion); }}
                >{suggestion}</button>
              {/each}
            </div>
          {/if}
          <p class="text-xs text-gray-600 mt-0.5">Full path: <span class="font-mono text-gray-500">{editCategory}/{editSubfolder ? editSubfolder + '/' : ''}{editFilename}{getFilenameExt()}</span></p>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Source URL</label>
          <input bind:value={editSourceUrl} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" placeholder="https://..." />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Base Model</label>
          <input bind:value={editBaseModel} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" placeholder="e.g. SDXL 1.0, Flux.1" />
          <p class="text-xs text-gray-600 mt-0.5">Associated base model (useful for LoRAs, VAEs, etc.)</p>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Description</label>
          <textarea bind:value={editDescription} rows="2" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500 resize-none"></textarea>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Tags (comma-separated)</label>
          <input bind:value={editTags} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" />
        </div>

        <div class="flex gap-2 pt-2 border-t border-gray-700">
          <button
            class="px-4 py-2 text-sm rounded text-white transition-colors {hasChanges ? 'bg-green-600 hover:bg-green-500' : 'bg-gray-700 text-gray-500 cursor-not-allowed'}"
            onclick={saveEdits}
            disabled={saving || !hasChanges}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => editing = false}>Cancel</button>
        </div>
      </div>
    {:else if showSyncPicker}
      <!-- Sync to host picker -->
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-300">Sync to Host</h3>
          <button class="text-xs text-gray-500 hover:text-gray-300" onclick={() => showSyncPicker = false}>Back</button>
        </div>
        {#if loadingHosts}
          <p class="text-sm text-gray-500">Loading hosts...</p>
        {:else if hosts.length === 0}
          <p class="text-sm text-gray-500">No hosts configured. Mount volumes under /hosts/ in Docker.</p>
        {:else}
          <div class="space-y-2">
            {#each hosts as host}
              <div class="flex items-center justify-between bg-gray-900 rounded-lg px-4 py-3 border border-gray-700">
                <div>
                  <p class="text-sm text-gray-200 font-medium">{host.name}</p>
                  {#if host.disk_free}
                    <p class="text-xs text-gray-500">{formatSize(host.disk_free)} free</p>
                  {/if}
                </div>
                {#if confirmSyncHost === host.id}
                  <div class="flex gap-1">
                    <button
                      class="px-2 py-1 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                      onclick={() => syncToHost(host.id)}
                      disabled={syncingTo[host.id]}
                    >
                      {syncingTo[host.id] ? 'Syncing...' : 'Confirm'}
                    </button>
                    <button class="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300" onclick={() => confirmSyncHost = null}>No</button>
                  </div>
                {:else}
                  <button
                    class="px-3 py-1.5 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                    onclick={() => confirmSyncHost = host.id}
                    disabled={syncingTo[host.id]}
                  >
                    Sync
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <!-- View mode -->
      <div class="space-y-4">
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Name</span>
          <p class="text-gray-100 mt-0.5">{model.name}</p>
        </div>
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Filename</span>
          <p class="text-gray-300 text-sm mt-0.5 font-mono">{model.filename}</p>
        </div>
        <div class="flex gap-6">
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Category</span>
            <p class="text-gray-300 text-sm mt-0.5">{model.category}</p>
          </div>
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Size</span>
            <p class="text-gray-300 text-sm mt-0.5">{formatSize(model.size)}</p>
          </div>
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Format</span>
            <p class="text-gray-300 text-sm mt-0.5 font-mono">{model.filename?.split('.').pop() || '-'}</p>
          </div>
        </div>
        {#if model.base_model}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Base Model</span>
            <p class="text-gray-300 text-sm mt-0.5">{model.base_model}</p>
          </div>
        {/if}
        {#if model.description}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Description</span>
            <p class="text-gray-300 text-sm mt-0.5">{model.description}</p>
          </div>
        {/if}
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Hash (SHA-256)</span>
          {#if model.hash?.sha256}
            <p class="text-green-400 text-xs mt-0.5 font-mono truncate" title={model.hash.sha256}>{'\u2713'} {model.hash.sha256}</p>
          {:else if hashing}
            <p class="text-gray-400 text-sm mt-0.5">Computing hash...</p>
          {:else}
            <p class="text-gray-500 text-sm mt-0.5">
              Not computed
              <button class="ml-2 text-green-400 underline text-xs" onclick={handleHash}>Compute now</button>
            </p>
          {/if}
        </div>
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Source</span>
          {#if model.source?.url}
            <p class="text-sm mt-0.5">
              {#if model.source.provider && model.source.provider !== 'manual'}
                <span class="text-gray-400">{model.source.provider}</span>
                <span class="text-gray-600 mx-1">-</span>
              {/if}
              {#if isSafeUrl(model.source.url)}
                <a href={model.source.url} target="_blank" rel="noopener noreferrer" class="text-green-400 hover:text-green-300 underline break-all">{model.source.url}</a>
              {:else}
                <span class="text-gray-300 break-all">{model.source.url}</span>
              {/if}
            </p>
          {:else}
            <p class="text-gray-500 text-sm mt-0.5">Not specified</p>
          {/if}
        </div>
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Tags</span>
          {#if model.tags?.length}
            <div class="flex flex-wrap gap-1 mt-1">
              {#each model.tags as tag}
                <span class="px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 text-xs">{tag}</span>
              {/each}
            </div>
          {:else}
            <p class="text-gray-600 text-sm mt-0.5 italic">No tags</p>
          {/if}
        </div>
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Path</span>
          <p class="text-gray-500 text-xs mt-0.5 font-mono">{model.relative_path}</p>
        </div>

        <!-- History -->
        {#if model.history?.length}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">History</span>
            <div class="mt-1 space-y-1">
              {#each model.history.slice().reverse() as entry}
                <div class="text-xs text-gray-500">
                  <span class="text-gray-400">{formatHistoryEntry(entry)}</span>
                  <span class="text-gray-600 ml-1">{new Date(entry.timestamp).toLocaleString()}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Actions -->
        <div class="border-t border-gray-700 pt-4 flex flex-wrap gap-2">
          <button class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={startEditing}>Edit</button>
          <button class="px-3 py-1.5 text-sm rounded bg-green-700 hover:bg-green-600 text-white" onclick={openSyncPicker}>Sync to Host</button>
          <a
            href={api.getDownloadUrl(model.id)}
            download
            class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200 inline-block"
          >Download</a>
          <button
            class="px-3 py-1.5 text-sm rounded bg-red-900/50 hover:bg-red-800 text-red-300 ml-auto"
            onclick={() => onDelete(model)}
          >Delete</button>
        </div>
      </div>
    {/if}
  </div>
</div>
