<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { addToast } from '../lib/stores.js';
  import BookmarkCard from '../components/BookmarkCard.svelte';
  import BookmarkDetail from '../components/BookmarkDetail.svelte';

  let { onNavigate } = $props();

  let bookmarks = $state([]);
  let categories = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let search = $state('');
  let selectedBookmark = $state(null);
  let showAddForm = $state(false);

  // Add form state
  let addName = $state('');
  let addSourceUrl = $state('');
  let addProvider = $state('');
  let addDescription = $state('');
  let addNotes = $state('');
  let addBaseModel = $state('');
  let addTags = $state('');
  let addThumbnailUrl = $state('');
  let addTargetCategory = $state('');
  let adding = $state(false);

  let filteredBookmarks = $derived.by(() => {
    let list = bookmarks;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(b =>
        b.name?.toLowerCase().includes(q) ||
        b.description?.toLowerCase().includes(q) ||
        b.notes?.toLowerCase().includes(q) ||
        b.base_model?.toLowerCase().includes(q) ||
        b.source?.url?.toLowerCase().includes(q) ||
        b.source?.provider?.toLowerCase().includes(q) ||
        b.tags?.some(t => t.toLowerCase().includes(q))
      );
    }
    return list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  });

  onMount(() => loadData());

  async function loadData() {
    loading = true;
    error = null;
    try {
      const [bData, cData] = await Promise.all([
        api.listBookmarks(),
        api.getCategories(),
      ]);
      bookmarks = bData.bookmarks || [];
      categories = cData || [];
    } catch (err) {
      error = err.message;
    }
    loading = false;
  }

  function resetAddForm() {
    addName = '';
    addSourceUrl = '';
    addProvider = '';
    addDescription = '';
    addNotes = '';
    addBaseModel = '';
    addTags = '';
    addThumbnailUrl = '';
    addTargetCategory = '';
  }

  async function handleAdd() {
    if (!addName.trim()) return;
    adding = true;
    error = null;
    try {
      await api.createBookmark({
        name: addName.trim(),
        source_url: addSourceUrl.trim() || undefined,
        provider: addProvider || undefined,
        description: addDescription.trim() || undefined,
        notes: addNotes.trim() || undefined,
        base_model: addBaseModel.trim() || undefined,
        tags: addTags.split(',').map(t => t.trim()).filter(Boolean),
        thumbnail_url: addThumbnailUrl.trim() || undefined,
        target_category: addTargetCategory || undefined,
      });
      addToast({ type: 'success', title: 'Bookmark added' });
      showAddForm = false;
      resetAddForm();
      await loadData();
    } catch (err) {
      error = err.message;
    }
    adding = false;
  }

  async function handleDelete(id) {
    try {
      await api.deleteBookmark(id);
      addToast({ type: 'success', title: 'Bookmark deleted' });
      selectedBookmark = null;
      await loadData();
    } catch (err) {
      error = err.message;
    }
  }

  function handlePromote(bookmark) {
    selectedBookmark = null;
    onNavigate('add', {
      source_url: bookmark.source?.url || '',
      name: bookmark.name,
      description: bookmark.description || '',
      base_model: bookmark.base_model || '',
      tags: (bookmark.tags || []).join(', '),
      target_category: bookmark.target_category || '',
      thumbnail_url: bookmark.thumbnail_url || '',
      bookmark_id: bookmark.id,
    });
  }

  function selectBookmark(b) {
    selectedBookmark = b;
  }
</script>

<div>
  <!-- Controls bar -->
  <div class="flex items-center justify-between mb-6 gap-4">
    <div class="flex items-center gap-3">
      <h2 class="text-lg font-semibold text-gray-100">Bookmarks</h2>
      <span class="text-sm text-gray-500">{filteredBookmarks.length} item{filteredBookmarks.length !== 1 ? 's' : ''}</span>
    </div>
    <div class="flex items-center gap-3">
      <input
        type="text"
        bind:value={search}
        placeholder="Search bookmarks..."
        class="bg-gray-800 border border-gray-600 rounded-md px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-amber-500 w-64"
      />
      <button
        onclick={() => { showAddForm = !showAddForm; if (!showAddForm) resetAddForm(); }}
        class="px-3 py-1.5 text-sm rounded-md transition-colors {showAddForm ? 'bg-amber-600 text-white' : 'bg-gray-700 hover:bg-gray-600 text-gray-300'}"
      >
        {showAddForm ? 'Cancel' : 'Add Bookmark'}
      </button>
    </div>
  </div>

  {#if error}
    <div class="bg-red-900/30 border border-red-700 rounded-md px-3 py-2 mb-4 text-red-300 text-sm">
      {error}
    </div>
  {/if}

  <!-- Add Form -->
  {#if showAddForm}
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 mb-6">
      <h3 class="text-sm font-medium text-gray-200 mb-4">New Bookmark</h3>
      <div class="grid grid-cols-2 gap-4">
        <div class="col-span-2 sm:col-span-1">
          <label class="block text-xs text-gray-400 mb-1">Name *</label>
          <input bind:value={addName} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="Model name" />
        </div>
        <div class="col-span-2 sm:col-span-1">
          <label class="block text-xs text-gray-400 mb-1">Source URL</label>
          <input bind:value={addSourceUrl} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="https://..." />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Provider</label>
          <select bind:value={addProvider} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500">
            <option value="">None</option>
            <option value="huggingface">Hugging Face</option>
            <option value="civitai">CivitAI</option>
            <option value="url">Direct URL</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Base Model</label>
          <input bind:value={addBaseModel} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="e.g. SDXL 1.0, Flux.1" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Target Category</label>
          <select bind:value={addTargetCategory} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500">
            <option value="">None</option>
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Tags</label>
          <input bind:value={addTags} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="Comma separated" />
        </div>
        <div class="col-span-2">
          <label class="block text-xs text-gray-400 mb-1">Description</label>
          <textarea bind:value={addDescription} rows="2" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500 resize-none" placeholder="Model description..."></textarea>
        </div>
        <div class="col-span-2">
          <label class="block text-xs text-gray-400 mb-1">Notes</label>
          <textarea bind:value={addNotes} rows="2" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500 resize-none" placeholder="Personal notes..."></textarea>
        </div>
        <div class="col-span-2">
          <label class="block text-xs text-gray-400 mb-1">Thumbnail URL</label>
          <input bind:value={addThumbnailUrl} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500" placeholder="https://..." />
        </div>
      </div>
      <div class="flex gap-2 mt-4">
        <button
          onclick={handleAdd}
          disabled={adding || !addName.trim()}
          class="px-4 py-2 text-sm rounded bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {adding ? 'Adding...' : 'Add Bookmark'}
        </button>
      </div>
    </div>
  {/if}

  <!-- Content -->
  {#if loading}
    <div class="text-center py-12 text-gray-500">Loading bookmarks...</div>
  {:else if filteredBookmarks.length === 0}
    <div class="text-center py-16">
      <div class="text-gray-600 text-4xl mb-4">
        <svg class="w-16 h-16 mx-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <p class="text-gray-500 text-sm mb-2">
        {search ? 'No bookmarks match your search' : 'No bookmarks yet'}
      </p>
      {#if !search}
        <p class="text-gray-600 text-xs">Save references to models you want to remember</p>
      {/if}
    </div>
  {:else}
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {#each filteredBookmarks as bm (bm.id)}
        <BookmarkCard bookmark={bm} onSelect={() => selectBookmark(bm)} />
      {/each}
    </div>
  {/if}
</div>

{#if selectedBookmark}
  <BookmarkDetail
    bookmark={selectedBookmark}
    {categories}
    onClose={() => { selectedBookmark = null; }}
    onUpdated={loadData}
    onDelete={handleDelete}
    onPromote={handlePromote}
  />
{/if}
