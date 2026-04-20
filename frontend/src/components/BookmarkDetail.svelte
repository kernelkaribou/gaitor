<script>
  import { api } from '../lib/api.js';
  import { isSafeUrl } from '../lib/utils.js';

  let { bookmark, categories, onClose, onUpdated, onDelete, onPromote } = $props();

  let editing = $state(false);
  let saving = $state(false);
  let error = $state(null);
  let uploadingThumb = $state(false);
  let thumbCacheBust = $state(Date.now());
  let confirmDelete = $state(false);

  let thumbUrl = $derived(
    bookmark.thumbnail ? api.getBookmarkThumbnailUrl(bookmark.id) + '?t=' + thumbCacheBust : null
  );

  // Edit form state
  let editName = $state('');
  let editDescription = $state('');
  let editNotes = $state('');
  let editSourceUrl = $state('');
  let editBaseModel = $state('');
  let editTags = $state('');
  let editThumbnailUrl = $state('');
  let editTargetCategory = $state('');

  // Original values for dirty tracking
  let origName = $state('');
  let origDescription = $state('');
  let origNotes = $state('');
  let origSourceUrl = $state('');
  let origBaseModel = $state('');
  let origTags = $state('');
  let origThumbnailUrl = $state('');
  let origTargetCategory = $state('');

  let hasChanges = $derived(
    editName !== origName ||
    editDescription !== origDescription ||
    editNotes !== origNotes ||
    editSourceUrl !== origSourceUrl ||
    editBaseModel !== origBaseModel ||
    editTags !== origTags ||
    editThumbnailUrl !== origThumbnailUrl ||
    editTargetCategory !== origTargetCategory
  );

  function startEditing() {
    editName = bookmark.name;
    editDescription = bookmark.description || '';
    editNotes = bookmark.notes || '';
    editSourceUrl = bookmark.source?.url || '';
    editBaseModel = bookmark.base_model || '';
    editTags = (bookmark.tags || []).join(', ');
    editThumbnailUrl = bookmark.thumbnail_url || '';
    editTargetCategory = bookmark.target_category || '';

    origName = editName;
    origDescription = editDescription;
    origNotes = editNotes;
    origSourceUrl = editSourceUrl;
    origBaseModel = editBaseModel;
    origTags = editTags;
    origThumbnailUrl = editThumbnailUrl;
    origTargetCategory = editTargetCategory;

    editing = true;
  }

  async function saveEdits() {
    saving = true;
    error = null;
    try {
      const tags = editTags.split(',').map(t => t.trim()).filter(Boolean);
      const updates = {};

      if (editName !== origName) updates.name = editName;
      if (editDescription !== origDescription) updates.description = editDescription;
      if (editNotes !== origNotes) updates.notes = editNotes;
      if (editSourceUrl !== origSourceUrl) updates.source_url = editSourceUrl || null;
      if (editBaseModel !== origBaseModel) updates.base_model = editBaseModel.trim() || null;
      if (editTags !== origTags) updates.tags = tags;
      if (editThumbnailUrl !== origThumbnailUrl) updates.thumbnail_url = editThumbnailUrl || null;
      if (editTargetCategory !== origTargetCategory) updates.target_category = editTargetCategory || null;

      await api.updateBookmark(bookmark.id, updates);
      editing = false;
      onUpdated();
    } catch (err) {
      error = err.message;
    }
    saving = false;
  }

  async function handleThumbnailUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    uploadingThumb = true;
    error = null;
    try {
      await api.uploadBookmarkThumbnail(bookmark.id, file);
      thumbCacheBust = Date.now();
      if (!editing) onUpdated();
    } catch (err) {
      error = err.message;
    }
    uploadingThumb = false;
  }

  async function handleThumbnailRemove() {
    error = null;
    try {
      await api.deleteBookmarkThumbnail(bookmark.id);
      thumbCacheBust = Date.now();
      if (!editing) onUpdated();
    } catch (err) {
      error = err.message;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose();
  }

  import { onMount, onDestroy } from 'svelte';
  onMount(() => document.addEventListener('keydown', handleKeydown));
  onDestroy(() => document.removeEventListener('keydown', handleKeydown));

  function sourceDomain(urlStr) {
    try {
      const u = new URL(urlStr);
      return u.hostname.replace('www.', '');
    } catch {
      return urlStr;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="fixed inset-0 bg-black/50 z-40" onclick={onClose}></div>

<div class="fixed right-0 top-0 bottom-0 w-full max-w-xl bg-gray-800 border-l border-gray-700 z-50 overflow-y-auto">
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="min-w-0 mr-4">
        <h2 class="text-lg font-semibold text-gray-100 truncate">{bookmark.name}</h2>
        <p class="text-xs text-amber-400 mt-0.5">Bookmark</p>
      </div>
      <button class="text-gray-400 hover:text-gray-200 text-xl shrink-0" onclick={onClose}>{'\u2715'}</button>
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
            <img src={thumbUrl} alt={bookmark.name} class="max-w-full max-h-[400px] object-contain rounded-lg" />
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
        <label class="block w-full h-24 border-2 border-dashed border-gray-600 rounded-lg flex items-center justify-center text-gray-500 text-sm hover:border-amber-600/50 hover:text-gray-400 cursor-pointer transition-colors">
          {uploadingThumb ? 'Uploading...' : 'Click to add thumbnail'}
          <input type="file" accept="image/*" onchange={handleThumbnailUpload} class="hidden" disabled={uploadingThumb} />
        </label>
      {/if}
    </div>

    {#if editing}
      <!-- Edit Form -->
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Name</label>
          <input bind:value={editName} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Source URL</label>
          <input bind:value={editSourceUrl} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="https://..." />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Base Model</label>
          <input bind:value={editBaseModel} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="e.g. SDXL 1.0, Flux.1" />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Target Category</label>
          <select bind:value={editTargetCategory} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500">
            <option value="">None</option>
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
          <p class="text-xs text-gray-600 mt-0.5">Default category when downloading to library</p>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Tags</label>
          <input bind:value={editTags} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="Comma separated" />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Description</label>
          <textarea bind:value={editDescription} rows="3" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500 resize-none"></textarea>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Notes</label>
          <textarea bind:value={editNotes} rows="3" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500 resize-none" placeholder="Personal notes..."></textarea>
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">Thumbnail URL</label>
          <input bind:value={editThumbnailUrl} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="https://..." />
          <p class="text-xs text-gray-600 mt-0.5">Remote image URL (downloaded and stored locally as thumbnail)</p>
        </div>

        <div class="flex gap-2 pt-2">
          <button
            onclick={saveEdits}
            disabled={saving || !hasChanges || !editName.trim()}
            class="px-4 py-2 text-sm rounded bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button onclick={() => { editing = false; }} class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-300">
            Cancel
          </button>
        </div>
      </div>
    {:else}
      <!-- View Mode -->
      <div class="space-y-4">
        {#if bookmark.source?.url}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Source</h4>
            {#if isSafeUrl(bookmark.source.url)}
              <a href={bookmark.source.url} target="_blank" rel="noopener noreferrer" class="text-sm text-amber-400 hover:text-amber-300 underline">
                {sourceDomain(bookmark.source.url)}
              </a>
            {:else}
              <p class="text-sm text-gray-300">{bookmark.source.url}</p>
            {/if}
          </div>
        {/if}

        {#if bookmark.base_model}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Base Model</h4>
            <p class="text-sm text-gray-300">{bookmark.base_model}</p>
          </div>
        {/if}

        {#if bookmark.target_category}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Target Category</h4>
            <p class="text-sm text-gray-300">{categories.find(c => c.id === bookmark.target_category)?.label || bookmark.target_category}</p>
          </div>
        {/if}

        {#if bookmark.tags?.length}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Tags</h4>
            <div class="flex flex-wrap gap-1.5">
              {#each bookmark.tags as tag}
                <span class="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-300">{tag}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if bookmark.description}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Description</h4>
            <p class="text-sm text-gray-300 whitespace-pre-wrap">{bookmark.description}</p>
          </div>
        {/if}

        {#if bookmark.notes}
          <div>
            <h4 class="text-xs font-medium text-gray-400 mb-1">Notes</h4>
            <p class="text-sm text-gray-400 whitespace-pre-wrap italic">{bookmark.notes}</p>
          </div>
        {/if}

        <div class="text-xs text-gray-600 pt-2">
          Added {new Date(bookmark.created_at).toLocaleDateString()}
        </div>

        <!-- Actions -->
        <div class="flex flex-wrap gap-2 pt-4 border-t border-gray-700">
          <button onclick={startEditing} class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-300">
            Edit
          </button>
          {#if bookmark.source?.url}
            <button onclick={() => onPromote(bookmark)} class="px-3 py-1.5 text-sm rounded bg-green-700 hover:bg-green-600 text-green-100">
              Download to Library
            </button>
          {/if}
          {#if confirmDelete}
            <button onclick={() => onDelete(bookmark.id)} class="px-3 py-1.5 text-sm rounded bg-red-700 hover:bg-red-600 text-red-100">
              Confirm Delete
            </button>
            <button onclick={() => { confirmDelete = false; }} class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-300">
              Cancel
            </button>
          {:else}
            <button onclick={() => { confirmDelete = true; }} class="px-3 py-1.5 text-sm rounded bg-red-900/50 hover:bg-red-800 text-red-300">
              Delete
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>
