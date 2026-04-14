<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { formatSize } from '../lib/utils.js';
  import ModelCard from '../components/ModelCard.svelte';
  import ModelDetail from '../components/ModelDetail.svelte';
  import ScanResults from '../components/ScanResults.svelte';
  import ConfirmDialog from '../components/ConfirmDialog.svelte';

  let { onNavigate } = $props();

  let libraryStatus = $state(null);
  let modelList = $state([]);
  let categories = $state([]);
  let libraryStats = $state(null);
  let search = $state('');
  let selectedModel = $state(null);
  let scanResults = $state(null);
  let scanKey = $state(0);
  let scanning = $state(false);
  let deleteTarget = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let activeCategory = $state(null);
  let currentView = $state('grid');

  // Category management
  let showAddCategory = $state(false);
  let newCatId = $state('');
  let newCatLabel = $state('');
  let renamingCat = $state(null);
  let renameCatId = $state('');
  let renameCatLabel = $state('');
  let confirmingCatRename = $state(false);

  // Subfolder management
  let collapsedGroups = $state({});

  // Bulk selection
  let selectMode = $state(false);
  let selectedIds = $state(new Set());
  let showBulkCategory = $state(false);
  let bulkCategory = $state('');
  let showBulkTags = $state(false);
  let bulkTagsAdd = $state('');
  let showBulkDelete = $state(false);

  function toggleSelect(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedIds = next;
  }

  function toggleSelectAll() {
    const visible = filteredModels.map(m => m.id);
    if (visible.every(id => selectedIds.has(id))) {
      selectedIds = new Set();
    } else {
      selectedIds = new Set(visible);
    }
  }

  function exitSelectMode() {
    selectMode = false;
    selectedIds = new Set();
    showBulkCategory = false;
    showBulkTags = false;
    showBulkDelete = false;
  }

  async function bulkApplyCategory() {
    if (!bulkCategory || selectedIds.size === 0) return;
    try {
      await api.bulkUpdateModels([...selectedIds], { category: bulkCategory });
      showBulkCategory = false;
      bulkCategory = '';
      exitSelectMode();
      await loadData();
    } catch (err) {
      error = err.message;
    }
  }

  async function bulkApplyTags() {
    if (!bulkTagsAdd.trim() || selectedIds.size === 0) return;
    try {
      const tags = bulkTagsAdd.split(',').map(t => t.trim()).filter(Boolean);
      await api.bulkUpdateModels([...selectedIds], { tags_add: tags });
      showBulkTags = false;
      bulkTagsAdd = '';
      exitSelectMode();
      await loadData();
    } catch (err) {
      error = err.message;
    }
  }

  async function bulkDeleteConfirmed(confirmText) {
    try {
      await api.bulkDeleteModels([...selectedIds], confirmText);
      showBulkDelete = false;
      exitSelectMode();
      selectedModel = null;
      await loadData();
    } catch (err) {
      throw err;
    }
  }

  async function bulkGroup() {
    if (selectedIds.size < 2) return;
    const ids = [...selectedIds];
    try {
      await api.setModelGroup(ids[0], ids.slice(1));
      exitSelectMode();
      await loadData();
    } catch (err) {
      error = err.message;
    }
  }

  async function addNewCategory() {
    if (!newCatId.trim()) return;
    const id = newCatId.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '');
    const label = newCatLabel.trim() || id.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    try {
      await api.createCategory({ id, label, extensions: [], description: '' });
      newCatId = '';
      newCatLabel = '';
      showAddCategory = false;
      await loadData();
    } catch (err) {
      error = err.message;
    }
  }

  function startRenameCategory(cat) {
    renamingCat = cat.id;
    renameCatId = cat.id;
    renameCatLabel = cat.label;
    confirmingCatRename = false;
  }

  function requestCatRenameConfirm() {
    confirmingCatRename = true;
  }

  async function confirmRenameCategory() {
    if (!renamingCat || !renameCatId.trim()) return;
    const id = renameCatId.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '');
    const label = renameCatLabel.trim() || id.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    try {
      await api.renameCategory(renamingCat, id, label);
      if (activeCategory === renamingCat) {
        activeCategory = id;
      }
      renamingCat = null;
      confirmingCatRename = false;
      await loadData();
    } catch (err) {
      error = err.message;
      confirmingCatRename = false;
    }
  }

  async function loadData() {
    loading = true;
    error = null;
    try {
      const [status, modelsData, catsData, stats] = await Promise.all([
        api.getLibraryStatus(),
        api.listModels(),
        api.getCategories(),
        api.getModelStats().catch(() => null),
      ]);
      libraryStatus = status;
      modelList = modelsData.models || [];
      categories = catsData.categories || [];
      libraryStats = stats;
    } catch (err) {
      error = err.message;
      console.error('Failed to load library:', err);
    }
    loading = false;
  }

  onMount(loadData);

  function onTaskComplete() {
    loadData();
  }
  onMount(() => {
    window.addEventListener('gaitor:task-complete', onTaskComplete);
  });
  onDestroy(() => {
    window.removeEventListener('gaitor:task-complete', onTaskComplete);
  });

  async function handleScan() {
    scanning = true;
    try {
      const result = await api.scanLibrary();
      scanResults = result;
      scanKey += 1;
    } catch (err) {
      error = err.message;
    }
    scanning = false;
  }

  async function handleCataloged() {
    scanResults = null;
    await loadData();
  }

  async function handleModelUpdated() {
    await loadData();
    if (selectedModel) {
      const fresh = modelList.find((m) => m.id === selectedModel.id);
      selectedModel = fresh || null;
    }
  }

  async function handleDelete(model) {
    deleteTarget = model;
  }

  async function confirmDelete(confirmText) {
    try {
      await api.deleteModel(deleteTarget.id, confirmText);
      deleteTarget = null;
      selectedModel = null;
      await loadData();
    } catch (err) {
      throw err;
    }
  }

  let filteredModels = $derived.by(() => {
    let result = modelList;
    if (activeCategory) {
      result = result.filter((m) => m.category === activeCategory);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          m.filename.toLowerCase().includes(q) ||
          (m.tags || []).some((t) => t.toLowerCase().includes(q))
      );
    }
    // Sort by most recently updated first
    return [...result].sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));
  });

  // Group models by subfolder when viewing a specific category
  let groupedModels = $derived.by(() => {
    const models = filteredModels;
    if (!activeCategory) return null;  // No grouping when viewing all
    const groups = {};
    for (const m of models) {
      // relative_path like "checkpoints/subfolder/file.safetensors"
      const parts = (m.relative_path || '').split('/');
      const subfolder = parts.length > 2 ? parts.slice(1, -1).join('/') : '';
      if (!groups[subfolder]) groups[subfolder] = [];
      groups[subfolder].push(m);
    }
    return groups;
  });

  let categoryCountMap = $derived.by(() => {
    const map = {};
    for (const m of modelList) {
      map[m.category] = (map[m.category] || 0) + 1;
    }
    return map;
  });

  let duplicateIds = $derived.by(() => {
    return new Set(libraryStats?.duplicate_ids || []);
  });
</script>

<div class="flex gap-6">
  <!-- Category sidebar -->
  <aside class="w-52 shrink-0">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-xs uppercase tracking-wider text-gray-500 font-semibold">Categories</h3>
      <button
        class="w-6 h-6 flex items-center justify-center rounded-full bg-green-700 hover:bg-green-600 text-white text-sm font-bold transition-colors"
        title="Add category"
        onclick={() => showAddCategory = !showAddCategory}
      >+</button>
    </div>

    {#if showAddCategory}
      <div class="mb-3 p-3 bg-gray-800 border border-gray-700 rounded-lg">
        <p class="text-xs text-gray-400 mb-2 font-medium">New Category</p>
        <label class="block text-xs text-gray-500 mb-0.5">Folder name</label>
        <input
          type="text"
          bind:value={newCatId}
          placeholder="e.g. my_models"
          class="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-xs text-gray-200 mb-2 focus:outline-none focus:border-green-500"
          onkeydown={(e) => e.key === 'Enter' && addNewCategory()}
        />
        <label class="block text-xs text-gray-500 mb-0.5">Display title</label>
        <input
          type="text"
          bind:value={newCatLabel}
          placeholder="e.g. My Models (auto-generated if empty)"
          class="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-xs text-gray-200 mb-2 focus:outline-none focus:border-green-500"
          onkeydown={(e) => e.key === 'Enter' && addNewCategory()}
        />
        <div class="flex gap-1">
          <button class="flex-1 text-xs px-2 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded" onclick={addNewCategory}>Create</button>
          <button class="flex-1 text-xs px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded" onclick={() => { showAddCategory = false; newCatId = ''; newCatLabel = ''; }}>Cancel</button>
        </div>
      </div>
    {/if}

    <button
      class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-1 {activeCategory === null ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
      onclick={() => activeCategory = null}
    >
      All Models
      <span class="text-xs text-gray-500 ml-1">({modelList.length})</span>
    </button>

    {#each categories as cat}
      {@const count = categoryCountMap[cat.id] || 0}
      {#if renamingCat === cat.id}
        <div class="mb-1 p-2.5 bg-gray-800 border border-green-700/50 rounded-lg">
          {#if confirmingCatRename}
            <p class="text-xs text-yellow-400 mb-2">Renaming will move all files in this category. Continue?</p>
            <p class="text-xs text-gray-400 mb-1">Title: <span class="text-gray-200">{renameCatLabel.trim() || renameCatId.trim()}</span></p>
            <p class="text-xs text-gray-400 mb-2">Folder: <span class="text-gray-200 font-mono">{renameCatId.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '')}/</span></p>
            <div class="flex gap-1">
              <button class="flex-1 text-xs px-2 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded" onclick={confirmRenameCategory}>Confirm</button>
              <button class="flex-1 text-xs px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded" onclick={() => confirmingCatRename = false}>Back</button>
            </div>
          {:else}
            <label class="block text-xs text-gray-500 mb-0.5">Title</label>
            <input type="text" bind:value={renameCatLabel} class="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 mb-1.5 focus:outline-none focus:border-green-500" />
            <label class="block text-xs text-gray-500 mb-0.5">Folder</label>
            <input type="text" bind:value={renameCatId} class="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 font-mono mb-2 focus:outline-none focus:border-green-500" />
            <div class="flex gap-1">
              <button class="flex-1 text-xs px-2 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded" onclick={requestCatRenameConfirm}>Save</button>
              <button class="flex-1 text-xs px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded" onclick={() => renamingCat = null}>Cancel</button>
            </div>
          {/if}
        </div>
      {:else}
        <button
          class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-0.5 group {activeCategory === cat.id ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
          onclick={() => activeCategory = cat.id}
          ondblclick={() => !cat.is_default && startRenameCategory(cat)}
          title={cat.is_default ? cat.label : 'Double-click to rename'}
        >
          {cat.label}
          {#if count > 0}
            <span class="text-xs text-gray-500 ml-1">({count})</span>
          {/if}
        </button>
      {/if}
    {/each}

    <!-- Storage stats -->
    {#if libraryStats}
      <div class="mt-6 pt-4 border-t border-gray-700">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Storage</h3>
        <div class="space-y-1 text-xs">
          <p class="text-gray-300">{libraryStats.total_models} models</p>
          <p class="text-gray-400">{formatSize(libraryStats.total_size)} total</p>
          {#if libraryStats.duplicate_ids?.length > 0}
            <p class="text-yellow-400">{libraryStats.duplicate_ids.length} duplicates</p>
          {/if}
          {#if activeCategory && libraryStats.by_category?.[activeCategory]}
            <div class="mt-2 pt-2 border-t border-gray-700/50">
              <p class="text-gray-400">
                {libraryStats.by_category[activeCategory].count} in category
              </p>
              <p class="text-gray-500">
                {formatSize(libraryStats.by_category[activeCategory].size)}
              </p>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </aside>

  <!-- Main content -->
  <div class="flex-1 min-w-0">
    <!-- Controls bar -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <h2 class="text-lg font-semibold text-gray-200">
          {activeCategory ? categories.find(c => c.id === activeCategory)?.label || 'Library' : 'Library'}
        </h2>
        {#if libraryStatus}
          <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
            {libraryStatus.model_count ?? 0} models
          </span>
          {#if libraryStatus.disk_free}
            <span class="text-xs text-gray-500">
              {formatSize(libraryStatus.disk_free)} free
            </span>
          {/if}
        {/if}
      </div>
      <div class="flex items-center gap-2">
        <div class="relative">
          <input
            type="text"
            bind:value={search}
            placeholder="Search models..."
            class="bg-gray-800 border border-gray-600 rounded-md px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-green-500 w-56 pr-7"
          />
          {#if search}
            <button
              class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-xs"
              onclick={() => search = ''}
            >&#x2715;</button>
          {/if}
        </div>
        <!-- View toggle -->
        <div class="flex border border-gray-600 rounded-md overflow-hidden">
          <button
            class="px-2 py-1.5 text-sm transition-colors {currentView === 'grid' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
            onclick={() => currentView = 'grid'}
            title="Grid view"
            aria-label="Grid view"
          >▦</button>
          <button
            class="px-2 py-1.5 text-sm transition-colors {currentView === 'list' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
            onclick={() => currentView = 'list'}
            title="List view"
            aria-label="List view"
          >☰</button>
        </div>
        <button
          class="px-3 py-1.5 text-sm rounded-md bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
          onclick={handleScan}
          disabled={scanning}
        >
          {scanning ? 'Scanning...' : 'Scan'}
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded-md transition-colors {selectMode ? 'bg-blue-600 hover:bg-blue-500 text-white' : 'bg-gray-700 hover:bg-gray-600 text-gray-200'}"
          onclick={() => selectMode ? exitSelectMode() : (selectMode = true)}
        >
          {selectMode ? 'Cancel' : 'Select'}
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white transition-colors"
          onclick={() => onNavigate?.('add')}
        >
          Add Model
        </button>
      </div>
    </div>

    {#if error}
      <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
        {error}
        <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
      </div>
    {/if}

    <!-- Bulk action bar -->
    {#if selectMode}
      <div class="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 mb-4 flex items-center gap-3 flex-wrap">
        <button
          class="text-sm text-gray-400 hover:text-gray-200 underline"
          onclick={toggleSelectAll}
        >
          {filteredModels.length > 0 && filteredModels.every(m => selectedIds.has(m.id)) ? 'Deselect all' : 'Select all'}
        </button>
        <span class="text-sm text-gray-500">{selectedIds.size} selected</span>
        {#if selectedIds.size > 0}
          <div class="flex items-center gap-2 ml-auto">
            <button
              class="px-3 py-1.5 text-xs rounded bg-blue-900/50 hover:bg-blue-800 text-blue-300 disabled:opacity-50"
              onclick={bulkGroup}
              disabled={selectedIds.size < 2}
              title={selectedIds.size < 2 ? 'Select at least 2 models to group' : ''}
            >Group</button>
            <button
              class="px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-200"
              onclick={() => { showBulkCategory = true; showBulkTags = false; }}
            >Re-categorize</button>
            <button
              class="px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-200"
              onclick={() => { showBulkTags = true; showBulkCategory = false; }}
            >Add Tags</button>
            <button
              class="px-3 py-1.5 text-xs rounded bg-red-900/50 hover:bg-red-800 text-red-300"
              onclick={() => showBulkDelete = true}
            >Delete</button>
          </div>
        {/if}
      </div>

      {#if showBulkCategory}
        <div class="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 mb-4 flex items-center gap-3">
          <span class="text-sm text-gray-400">Move to:</span>
          <select
            bind:value={bulkCategory}
            class="bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-green-500"
          >
            <option value="">Select category</option>
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
          <button
            class="px-3 py-1.5 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
            onclick={bulkApplyCategory}
            disabled={!bulkCategory}
          >Apply</button>
          <button class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => showBulkCategory = false}>Cancel</button>
        </div>
      {/if}

      {#if showBulkTags}
        <div class="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 mb-4 flex items-center gap-3">
          <span class="text-sm text-gray-400">Add tags:</span>
          <input
            bind:value={bulkTagsAdd}
            placeholder="tag1, tag2, ..."
            class="bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-green-500 flex-1"
          />
          <button
            class="px-3 py-1.5 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
            onclick={bulkApplyTags}
            disabled={!bulkTagsAdd.trim()}
          >Apply</button>
          <button class="px-3 py-1.5 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={() => showBulkTags = false}>Cancel</button>
        </div>
      {/if}
    {/if}

    <!-- Scan results -->
    {#if scanResults && scanResults.count > 0}
      {#key scanKey}
        <ScanResults
          results={scanResults}
          {categories}
          onCataloged={handleCataloged}
          onDismiss={() => scanResults = null}
        />
      {/key}
    {:else if scanResults && scanResults.count === 0}
      <div class="bg-gray-800 border border-gray-700 rounded-md px-4 py-3 mb-4 text-gray-400 text-sm">
        No untracked models found. All files are already cataloged.
        <button class="ml-2 underline text-gray-500" onclick={() => scanResults = null}>dismiss</button>
      </div>
    {/if}

    <!-- Model grid/list (hidden while scan results are showing) -->
    {#if !(scanResults && scanResults.count > 0)}
      {#if loading}
      <div class="text-center py-20 text-gray-500">Loading...</div>
    {:else if filteredModels.length > 0}
      {#if activeCategory && groupedModels}
        <!-- Grouped by subfolder -->
        {#each Object.entries(groupedModels).sort(([a], [b]) => a === '' ? -1 : b === '' ? 1 : a.localeCompare(b)) as [subfolder, models] (subfolder)}
          {#if subfolder !== ''}
            <div class="mb-4">
              <button
                class="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 mb-2 px-1"
                onclick={() => collapsedGroups = { ...collapsedGroups, [subfolder]: !collapsedGroups[subfolder] }}
              >
                <span class="text-xs">{collapsedGroups[subfolder] ? '\u25B8' : '\u25BE'}</span>
                <span class="font-medium text-gray-300">{subfolder}</span>
                <span class="text-xs text-gray-600">({models.length})</span>
              </button>
              {#if !collapsedGroups[subfolder]}
                {#if currentView === 'grid'}
                  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 ml-4">
                    {#each models as model (model.id)}
                      <div class="relative">{#if selectMode}<button class="absolute top-2 left-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center text-xs transition-colors {selectedIds.has(model.id) ? 'bg-green-600 border-green-500 text-white' : 'bg-gray-800/80 border-gray-500 text-transparent hover:border-gray-300'}" onclick={(e) => { e.stopPropagation(); toggleSelect(model.id); }}>{selectedIds.has(model.id) ? '\u2713' : ''}</button>{/if}<ModelCard {model} {formatSize} isDuplicate={duplicateIds.has(model.id)} onSelect={() => selectMode ? toggleSelect(model.id) : (selectedModel = model)} /></div>
                    {/each}
                  </div>
                {:else}
                  <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700 ml-4">
                    {#each models as model (model.id)}
                      <button class="w-full text-left px-4 py-3 hover:bg-gray-750 transition-colors flex items-center gap-4" onclick={() => selectedModel = model}>
                        <div class="flex-1 min-w-0">
                          <span class="text-gray-100 font-medium">{model.name}</span>
                          <span class="text-gray-500 text-sm ml-2">{model.filename}</span>
                        </div>
                        <span class="text-sm text-gray-500 shrink-0 w-20 text-right">{formatSize(model.size)}</span>
                        {#if model.hash?.sha256}<span class="text-green-500 text-xs shrink-0" title="Verified">{'\u2713'}</span>{/if}
                      </button>
                    {/each}
                  </div>
                {/if}
              {/if}
            </div>
          {:else}
            <!-- Root level models (no subfolder) -->
            {#if currentView === 'grid'}
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-4">
                {#each models as model (model.id)}
                  <div class="relative">{#if selectMode}<button class="absolute top-2 left-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center text-xs transition-colors {selectedIds.has(model.id) ? 'bg-green-600 border-green-500 text-white' : 'bg-gray-800/80 border-gray-500 text-transparent hover:border-gray-300'}" onclick={(e) => { e.stopPropagation(); toggleSelect(model.id); }}>{selectedIds.has(model.id) ? '\u2713' : ''}</button>{/if}<ModelCard {model} {formatSize} isDuplicate={duplicateIds.has(model.id)} onSelect={() => selectMode ? toggleSelect(model.id) : (selectedModel = model)} /></div>
                {/each}
              </div>
            {:else}
              <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700 mb-4">
                {#each models as model (model.id)}
                  <button class="w-full text-left px-4 py-3 hover:bg-gray-750 transition-colors flex items-center gap-4" onclick={() => selectedModel = model}>
                    <div class="flex-1 min-w-0">
                      <span class="text-gray-100 font-medium">{model.name}</span>
                      <span class="text-gray-500 text-sm ml-2">{model.filename}</span>
                    </div>
                    <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400 shrink-0">{model.category}</span>
                    <span class="text-sm text-gray-500 shrink-0 w-20 text-right">{formatSize(model.size)}</span>
                    {#if model.hash?.sha256}<span class="text-green-500 text-xs shrink-0" title="Verified">{'\u2713'}</span>{/if}
                  </button>
                {/each}
              </div>
            {/if}
          {/if}
        {/each}
      {:else}
        <!-- Flat view (all categories or search) -->
        {#if currentView === 'grid'}
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {#each filteredModels as model (model.id)}
              <div class="relative">{#if selectMode}<button class="absolute top-2 left-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center text-xs transition-colors {selectedIds.has(model.id) ? 'bg-green-600 border-green-500 text-white' : 'bg-gray-800/80 border-gray-500 text-transparent hover:border-gray-300'}" onclick={(e) => { e.stopPropagation(); toggleSelect(model.id); }}>{selectedIds.has(model.id) ? '\u2713' : ''}</button>{/if}<ModelCard {model} {formatSize} isDuplicate={duplicateIds.has(model.id)} onSelect={() => selectMode ? toggleSelect(model.id) : (selectedModel = model)} /></div>
            {/each}
          </div>
        {:else}
          <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
            {#each filteredModels as model (model.id)}
              <button
                class="w-full text-left px-4 py-3 hover:bg-gray-750 transition-colors flex items-center gap-4"
                onclick={() => selectedModel = model}
              >
                <div class="flex-1 min-w-0">
                  <span class="text-gray-100 font-medium">{model.name}</span>
                  <span class="text-gray-500 text-sm ml-2">{model.filename}</span>
                </div>
                <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400 shrink-0">{model.category}</span>
                <span class="text-sm text-gray-500 shrink-0 w-20 text-right">{formatSize(model.size)}</span>
                {#if model.hash?.sha256}
                  <span class="text-green-500 text-xs shrink-0" title="Verified">{'\u2713'}</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      {/if}
    {:else}
      <div class="text-center py-20">
        <h3 class="text-xl font-medium text-gray-300 mb-2">No models yet</h3>
        <p class="text-gray-500 max-w-md mx-auto mb-4">
          Add models to your library by uploading files, scanning your library directory,
          or downloading from the web.
        </p>
        <div class="flex gap-3 justify-center">
          <button
            class="px-4 py-2 text-sm rounded-md bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
            onclick={handleScan}
          >
            Scan Library Directory
          </button>
          <button
            class="px-4 py-2 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white transition-colors"
            onclick={() => onNavigate?.('add')}
          >
            Add Model
          </button>
        </div>
      </div>
    {/if}
    {/if}
  </div>
</div>

<!-- Model detail slide-over -->
{#if selectedModel}
  <ModelDetail
    model={selectedModel}
    {categories}
    {formatSize}
    onClose={() => selectedModel = null}
    onUpdated={handleModelUpdated}
    onDelete={handleDelete}
  />
{/if}

<!-- Delete confirmation -->
{#if deleteTarget}
  <ConfirmDialog
    title="Delete Model from Library"
    message="This will permanently delete '{deleteTarget.name}' and its file from the library. This action cannot be undone."
    warningText="Type 'delete' to confirm:"
    confirmValue="delete"
    confirmLabel="Delete Forever"
    danger={true}
    onConfirm={confirmDelete}
    onCancel={() => deleteTarget = null}
  />
{/if}

{#if showBulkDelete}
  <ConfirmDialog
    title="Bulk Delete from Library"
    message="This will permanently delete {selectedIds.size} model(s) and their files from the library. This action cannot be undone."
    warningText="Type 'delete' to confirm:"
    confirmValue="delete"
    confirmLabel="Delete All"
    danger={true}
    onConfirm={bulkDeleteConfirmed}
    onCancel={() => showBulkDelete = false}
  />
{/if}
