<script>
  import { api } from '../lib/api.js';

  let { model, categories, formatSize, onClose, onUpdated, onDelete } = $props();

  let editing = $state(false);
  let editName = $state(model.name);
  let editDescription = $state(model.description || '');
  let editCategory = $state(model.category);
  let editTags = $state((model.tags || []).join(', '));
  let renaming = $state(false);
  let renameName = $state(model.name);
  let saving = $state(false);
  let error = $state(null);

  // Thumbnail
  let thumbUrl = $derived(model.thumbnail ? api.getThumbnailUrl(model.id) + '?t=' + Date.now() : null);
  let uploadingThumb = $state(false);

  // Sync to destination
  let showSyncPicker = $state(false);
  let destinations = $state([]);
  let syncingTo = $state({});
  let loadingDests = $state(false);

  async function saveEdits() {
    saving = true;
    error = null;
    try {
      const tags = editTags.split(',').map((t) => t.trim()).filter(Boolean);
      await api.updateModel(model.id, {
        name: editName,
        description: editDescription,
        category: editCategory,
        tags,
      });
      editing = false;
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    saving = false;
  }

  async function handleRename() {
    saving = true;
    error = null;
    try {
      await api.renameModel(model.id, renameName, true);
      renaming = false;
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    saving = false;
  }

  async function handleHash() {
    error = null;
    try {
      await api.computeHash(model.id);
      onUpdated();
    } catch (err) {
      error = err.message;
    }
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
    loadingDests = true;
    try {
      const data = await api.listDestinations();
      destinations = data.destinations || [];
    } catch (err) {
      error = err.message;
    }
    loadingDests = false;
  }

  async function syncToDestination(destId) {
    syncingTo = { ...syncingTo, [destId]: true };
    error = null;
    try {
      await api.syncModelToDestination(destId, model.id);
    } catch (err) {
      error = err.message;
    }
    syncingTo = { ...syncingTo, [destId]: false };
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="fixed inset-0 bg-black/50 z-40" onclick={onClose}></div>

<!-- Slide-over panel -->
<div class="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-gray-800 border-l border-gray-700 z-50 overflow-y-auto">
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-lg font-semibold text-gray-100">Model Details</h2>
      <button class="text-gray-400 hover:text-gray-200 text-xl" onclick={onClose}>&#x2715;</button>
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
          <img src={thumbUrl} alt={model.name} class="w-full h-48 object-cover rounded-lg border border-gray-700" />
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
      <!-- Edit form -->
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Name</label>
          <input bind:value={editName} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Category</label>
          <select bind:value={editCategory} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500">
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Description</label>
          <textarea bind:value={editDescription} rows="3" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500 resize-none"></textarea>
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Tags (comma-separated)</label>
          <input bind:value={editTags} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" />
        </div>
        <div class="flex gap-2">
          <button class="px-4 py-2 text-sm rounded bg-green-600 hover:bg-green-500 text-white" onclick={saveEdits} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => editing = false}>Cancel</button>
        </div>
      </div>
    {:else if renaming}
      <!-- Rename form -->
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">New Name (also renames the file)</label>
          <input bind:value={renameName} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" />
        </div>
        <div class="flex gap-2">
          <button class="px-4 py-2 text-sm rounded bg-green-600 hover:bg-green-500 text-white" onclick={handleRename} disabled={saving}>
            {saving ? 'Renaming...' : 'Rename'}
          </button>
          <button class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => renaming = false}>Cancel</button>
        </div>
      </div>
    {:else if showSyncPicker}
      <!-- Sync to target picker -->
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-300">Sync to Target</h3>
          <button class="text-xs text-gray-500 hover:text-gray-300" onclick={() => showSyncPicker = false}>Back</button>
        </div>
        {#if loadingDests}
          <p class="text-sm text-gray-500">Loading targets...</p>
        {:else if destinations.length === 0}
          <p class="text-sm text-gray-500">No targets configured. Mount volumes under /dest/ in Docker.</p>
        {:else}
          <div class="space-y-2">
            {#each destinations as dest}
              <div class="flex items-center justify-between bg-gray-900 rounded-lg px-4 py-3 border border-gray-700">
                <div>
                  <p class="text-sm text-gray-200 font-medium">{dest.name}</p>
                  {#if dest.disk_free}
                    <p class="text-xs text-gray-500">{formatSize(dest.disk_free)} free</p>
                  {/if}
                </div>
                <button
                  class="px-3 py-1.5 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                  onclick={() => syncToDestination(dest.id)}
                  disabled={syncingTo[dest.id]}
                >
                  {syncingTo[dest.id] ? 'Syncing...' : 'Sync'}
                </button>
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
        {#if model.description}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Description</span>
            <p class="text-gray-300 text-sm mt-0.5">{model.description}</p>
          </div>
        {/if}
        {#if model.tags?.length}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Tags</span>
            <div class="flex flex-wrap gap-1 mt-1">
              {#each model.tags as tag}
                <span class="px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 text-xs">{tag}</span>
              {/each}
            </div>
          </div>
        {/if}
        <div>
          <span class="text-xs text-gray-500 uppercase tracking-wider">Hash (SHA-256)</span>
          {#if model.hash?.sha256}
            <p class="text-green-400 text-xs mt-0.5 font-mono truncate" title={model.hash.sha256}>&#x2713; {model.hash.sha256}</p>
          {:else}
            <p class="text-gray-500 text-sm mt-0.5">
              Not computed
              <button class="ml-2 text-green-400 underline text-xs" onclick={handleHash}>Compute now</button>
            </p>
          {/if}
        </div>
        {#if model.source?.provider}
          <div>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Source</span>
            <p class="text-gray-300 text-sm mt-0.5">{model.source.provider}
              {#if model.source.url}
                - <a href={model.source.url} target="_blank" rel="noopener" class="text-green-400 underline">{model.source.url}</a>
              {/if}
            </p>
          </div>
        {/if}
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
                  <span class="text-gray-400">{entry.action}</span>
                  - {new Date(entry.timestamp).toLocaleString()}
                  {#if entry.details?.from_name}
                    <span class="text-gray-600">({entry.details.from_name} -> {entry.details.to_name})</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Actions -->
        <div class="border-t border-gray-700 pt-4 flex flex-wrap gap-2">
          <button class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => editing = true}>Edit</button>
          <button class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => { renaming = true; renameName = model.name; }}>Rename</button>
          <button class="px-3 py-1.5 text-sm rounded bg-green-700 hover:bg-green-600 text-white" onclick={openSyncPicker}>Sync to Target</button>
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
