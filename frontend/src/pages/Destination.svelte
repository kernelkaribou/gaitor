<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import ModelCard from '../components/ModelCard.svelte';

  let { onBack } = $props();

  let destinations = $state([]);
  let selectedDest = $state(null);
  let syncStatus = $state([]);
  let categories = $state([]);
  let loading = $state(true);
  let syncing = $state({});
  let error = $state(null);
  let search = $state('');
  let activeCategory = $state(null);
  let currentView = $state('grid');
  let confirmRemove = $state(null);
  let selectedModels = $state(new Set());
  let confirmBulkAction = $state(false);

  function formatSize(bytes) {
    if (!bytes) return '-';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return `${size.toFixed(1)} ${units[i]}`;
  }

  function usagePercent(total, free) {
    if (!total) return 0;
    return Math.round(((total - free) / total) * 100);
  }

  onMount(async () => {
    try {
      const [destData, catsData] = await Promise.all([
        api.listDestinations(),
        api.getCategories(),
      ]);
      destinations = destData.destinations || [];
      categories = catsData.categories || [];
    } catch (err) {
      error = err.message;
    }
    loading = false;
  });

  async function selectDestination(dest) {
    selectedDest = dest;
    loading = true;
    search = '';
    activeCategory = null;
    try {
      const data = await api.getDestinationSyncStatus(dest.id);
      syncStatus = data.status || [];
    } catch (err) {
      error = err.message;
      syncStatus = [];
    }
    loading = false;
  }

  async function syncModel(modelId) {
    syncing = { ...syncing, [modelId]: true };
    error = null;
    try {
      await api.syncModelToDestination(selectedDest.id, modelId);
      await selectDestination(selectedDest);
    } catch (err) {
      error = err.message;
    }
    syncing = { ...syncing, [modelId]: false };
  }

  async function removeModel(modelId) {
    syncing = { ...syncing, [modelId]: true };
    try {
      await api.removeFromDestination(selectedDest.id, modelId);
      await selectDestination(selectedDest);
    } catch (err) {
      error = err.message;
    }
    syncing = { ...syncing, [modelId]: false };
  }

  async function applyRename(modelId) {
    syncing = { ...syncing, [modelId]: true };
    try {
      await api.applyRenameOnDestination(selectedDest.id, modelId);
      await selectDestination(selectedDest);
    } catch (err) {
      error = err.message;
    }
    syncing = { ...syncing, [modelId]: false };
  }

  async function bulkSync() {
    const notSynced = syncStatus.filter(s => s.status === 'not_synced').map(s => s.model_id);
    if (notSynced.length === 0) return;
    for (const id of notSynced) {
      await syncModel(id);
    }
  }

  function toggleSelect(modelId) {
    const next = new Set(selectedModels);
    if (next.has(modelId)) next.delete(modelId);
    else next.add(modelId);
    selectedModels = next;
  }

  function toggleSelectAll() {
    const visible = filteredItems().map(i => i.model_id);
    if (visible.every(id => selectedModels.has(id))) {
      selectedModels = new Set();
    } else {
      selectedModels = new Set(visible);
    }
  }

  let selectionInfo = $derived(() => {
    if (selectedModels.size === 0) return null;
    const items = syncStatus.filter(s => selectedModels.has(s.model_id));
    const hasUnsynced = items.some(s => s.status === 'not_synced' || s.status === 'outdated');
    const allSynced = items.every(s => s.status === 'synced');
    return { count: items.length, hasUnsynced, allSynced };
  });

  async function bulkSyncSelected() {
    confirmBulkAction = false;
    const ids = [...selectedModels].filter(id => {
      const item = syncStatus.find(s => s.model_id === id);
      return item && (item.status === 'not_synced' || item.status === 'outdated');
    });
    for (const id of ids) {
      await syncModel(id);
    }
    selectedModels = new Set();
  }

  async function bulkRemoveSelected() {
    confirmBulkAction = false;
    const ids = [...selectedModels].filter(id => {
      const item = syncStatus.find(s => s.model_id === id);
      return item && (item.status === 'synced' || item.status === 'orphaned');
    });
    for (const id of ids) {
      await removeModel(id);
    }
    selectedModels = new Set();
  }

  const statusColors = {
    synced: 'bg-green-900/30 text-green-400 border-green-800',
    not_synced: 'bg-gray-700/50 text-gray-400 border-gray-600',
    outdated: 'bg-yellow-900/30 text-yellow-400 border-yellow-800',
    rename_pending: 'bg-blue-900/30 text-blue-400 border-blue-800',
    orphaned: 'bg-red-900/30 text-red-400 border-red-800',
  };
  const statusLabels = {
    synced: 'Synced',
    not_synced: 'Not synced',
    outdated: 'Outdated',
    rename_pending: 'Rename pending',
    orphaned: 'Orphaned',
  };

  let filteredItems = $derived(() => {
    let result = syncStatus;
    if (activeCategory) {
      result = result.filter((s) => s.category === activeCategory);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) => s.model_name.toLowerCase().includes(q) || (s.filename && s.filename.toLowerCase().includes(q))
      );
    }
    return result;
  });

  let categoryCountMap = $derived(() => {
    const map = {};
    for (const s of syncStatus) {
      if (s.category) {
        map[s.category] = (map[s.category] || 0) + 1;
      }
    }
    return map;
  });

  let syncSummary = $derived(() => {
    const counts = { synced: 0, not_synced: 0, outdated: 0, rename_pending: 0, orphaned: 0 };
    for (const s of syncStatus) {
      if (counts[s.status] !== undefined) counts[s.status]++;
    }
    return counts;
  });
</script>

<div>
  {#if error}
    <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
      {error}
      <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
    </div>
  {/if}

  {#if !selectedDest}
    <!-- Target list -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-200">Targets</h2>
    </div>

    {#if loading}
      <div class="text-center py-20 text-gray-500">Loading...</div>
    {:else if destinations.length === 0}
      <div class="text-center py-20">
        <span class="text-6xl mb-4 block">&#x1F4E1;</span>
        <h3 class="text-xl font-medium text-gray-300 mb-2">No targets found</h3>
        <p class="text-gray-500 max-w-md mx-auto">
          Mount target directories as Docker volumes under <code class="bg-gray-800 px-1 rounded">/dest/</code> to manage them here.
        </p>
      </div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {#each destinations as dest}
          <button
            class="bg-gray-800 rounded-lg border border-gray-700 p-5 hover:border-green-600/50 transition-colors text-left w-full"
            onclick={() => selectDestination(dest)}
          >
            <h3 class="font-medium text-gray-100 mb-2">{dest.name}</h3>
            <p class="text-xs text-gray-500 font-mono mb-3">{dest.path}</p>
            {#if dest.disk_total}
              <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
                <div
                  class="bg-green-500 h-2 rounded-full"
                  style="width: {usagePercent(dest.disk_total, dest.disk_free)}%"
                ></div>
              </div>
              <p class="text-xs text-gray-500">
                {formatSize(dest.disk_free)} free of {formatSize(dest.disk_total)}
              </p>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  {:else}
    <!-- Destination detail - Library-style layout -->
    <div class="flex gap-6">
      <!-- Category sidebar -->
      <aside class="w-48 shrink-0">
        <button class="text-gray-400 hover:text-gray-200 text-sm mb-4 flex items-center gap-1" onclick={() => selectedDest = null}>
          &#x2190; All Targets
        </button>

        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Categories</h3>
        <button
          class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-1 {activeCategory === null ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
          onclick={() => activeCategory = null}
        >
          All Models
          <span class="text-xs text-gray-500 ml-1">({syncStatus.length})</span>
        </button>
        {#each categories as cat}
          {@const count = categoryCountMap()[cat.id] || 0}
          {#if count > 0}
            <button
              class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-0.5 {activeCategory === cat.id ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
              onclick={() => activeCategory = cat.id}
            >
              {cat.label}
              <span class="text-xs text-gray-500 ml-1">({count})</span>
            </button>
          {/if}
        {/each}

        <!-- Summary -->
        <div class="mt-6 pt-4 border-t border-gray-700">
          <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Summary</h3>
          <div class="space-y-1 text-xs">
            <p class="text-gray-300">{syncStatus.length} total models</p>
            {#if syncSummary().synced > 0}
              <p class="text-green-400">{syncSummary().synced} synced to this target</p>
            {/if}
            {#if syncSummary().outdated > 0}
              <p class="text-yellow-400">{syncSummary().outdated} outdated</p>
            {/if}
            {#if syncSummary().rename_pending > 0}
              <p class="text-blue-400">{syncSummary().rename_pending} rename pending</p>
            {/if}
            {#if syncSummary().orphaned > 0}
              <p class="text-red-400">{syncSummary().orphaned} orphaned</p>
            {/if}
          </div>
        </div>

        <!-- Disk usage -->
        {#if selectedDest.disk_total}
          <div class="mt-4 pt-4 border-t border-gray-700">
            <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Disk Usage</h3>
            <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
              <div
                class="bg-green-500 h-2 rounded-full"
                style="width: {usagePercent(selectedDest.disk_total, selectedDest.disk_free)}%"
              ></div>
            </div>
            <p class="text-xs text-gray-500">{formatSize(selectedDest.disk_free)} free</p>
          </div>
        {/if}
      </aside>

      <!-- Main content -->
      <div class="flex-1 min-w-0">
        <!-- Controls bar -->
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-gray-200">{selectedDest.name}</h2>
            <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
              {syncStatus.length} models | {syncSummary().synced} synced
            </span>
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
              >&#x25A6;</button>
              <button
                class="px-2 py-1.5 text-sm transition-colors {currentView === 'list' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
                onclick={() => currentView = 'list'}
                title="List view"
              >&#x2630;</button>
            </div>
            <label class="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none" title="Select all visible">
              <input
                type="checkbox"
                checked={filteredItems().length > 0 && filteredItems().every(i => selectedModels.has(i.model_id))}
                onchange={toggleSelectAll}
                class="rounded"
              />
              All
            </label>
          </div>
        </div>

        <!-- Bulk action bar -->
        {#if selectionInfo()}
          <div class="flex items-center gap-3 mb-4 bg-gray-800 border border-gray-600 rounded-lg px-4 py-2">
            <span class="text-sm text-gray-300">{selectionInfo().count} selected</span>
            {#if confirmBulkAction}
              <span class="text-sm text-yellow-300">
                {selectionInfo().hasUnsynced ? `Sync ${selectionInfo().count} models to target?` : `Remove ${selectionInfo().count} models from target?`}
              </span>
              <button
                class="px-3 py-1 text-xs rounded {selectionInfo().hasUnsynced ? 'bg-green-600 hover:bg-green-500' : 'bg-red-700 hover:bg-red-600'} text-white"
                onclick={() => selectionInfo().hasUnsynced ? bulkSyncSelected() : bulkRemoveSelected()}
              >Yes</button>
              <button class="px-3 py-1 text-xs rounded bg-gray-700 text-gray-300" onclick={() => confirmBulkAction = false}>No</button>
            {:else}
              {#if selectionInfo().hasUnsynced}
                <button
                  class="px-3 py-1 text-xs rounded bg-green-600 hover:bg-green-500 text-white"
                  onclick={() => confirmBulkAction = true}
                >Sync Selected</button>
              {:else if selectionInfo().allSynced}
                <button
                  class="px-3 py-1 text-xs rounded bg-red-900/50 hover:bg-red-800 text-red-300"
                  onclick={() => confirmBulkAction = true}
                >Remove Selected</button>
              {/if}
            {/if}
            <button class="ml-auto text-xs text-gray-500 hover:text-gray-300" onclick={() => { selectedModels = new Set(); confirmBulkAction = false; }}>Clear</button>
          </div>
        {/if}

        {#if loading}
          <div class="text-center py-10 text-gray-500">Loading sync status...</div>
        {:else if filteredItems().length > 0}
          {#if currentView === 'grid'}
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {#each filteredItems() as item (item.model_id)}
                <div class="bg-gray-800 rounded-lg border transition-colors overflow-hidden {selectedModels.has(item.model_id) ? 'border-green-500' : 'border-gray-700 hover:border-green-600/50'}">
                  <div class="p-4">
                    <div class="flex items-start justify-between mb-2">
                      <label class="flex items-center gap-2 min-w-0">
                        <input type="checkbox" checked={selectedModels.has(item.model_id)} onchange={() => toggleSelect(item.model_id)} class="rounded shrink-0" />
                        <h3 class="font-medium text-gray-100 truncate text-sm">{item.model_name}</h3>
                      </label>
                      <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 shrink-0 ml-2">
                        {item.category || 'other'}
                      </span>
                    </div>
                    <p class="text-xs text-gray-500 truncate mb-2">{item.filename}</p>
                    <!-- Status badge -->
                    <div class="flex items-center justify-between mb-3">
                      <span class="text-xs px-2 py-0.5 rounded border {statusColors[item.status] || 'bg-gray-700 text-gray-400 border-gray-600'}">
                        {statusLabels[item.status] || item.status}
                      </span>
                      <span class="text-xs text-gray-500">{formatSize(item.size)}</span>
                    </div>
                    {#if item.status === 'rename_pending' && item.dest_filename}
                      <p class="text-xs text-blue-400 mb-2 truncate">On dest: {item.dest_filename}</p>
                    {/if}
                    <!-- Actions -->
                    <div class="flex gap-1">
                      {#if item.status === 'not_synced' || item.status === 'outdated'}
                        <button
                          class="flex-1 px-2 py-1.5 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                          onclick={() => syncModel(item.model_id)}
                          disabled={syncing[item.model_id]}
                        >
                          {syncing[item.model_id] ? 'Syncing...' : 'Sync'}
                        </button>
                      {:else if item.status === 'rename_pending'}
                        <button
                          class="flex-1 px-2 py-1.5 text-xs rounded bg-blue-700 hover:bg-blue-600 text-white disabled:opacity-50"
                          onclick={() => applyRename(item.model_id)}
                          disabled={syncing[item.model_id]}
                        >
                          Apply Rename
                        </button>
                      {/if}
                      {#if item.status === 'synced' || item.status === 'orphaned'}
                        {#if confirmRemove === item.model_id}
                          <div class="flex gap-1 flex-1">
                            <span class="text-xs text-red-400 self-center mr-1">Remove from target?</span>
                            <button class="flex-1 px-2 py-1 text-xs rounded bg-red-700 text-white" onclick={() => { confirmRemove = null; removeModel(item.model_id); }}>Yes</button>
                            <button class="flex-1 px-2 py-1 text-xs rounded bg-gray-700 text-gray-300" onclick={() => confirmRemove = null}>No</button>
                          </div>
                        {:else}
                          <button
                            class="flex-1 px-2 py-1.5 text-xs rounded bg-gray-700 hover:bg-red-800 text-gray-400 hover:text-red-300 disabled:opacity-50"
                            onclick={() => confirmRemove = item.model_id}
                            disabled={syncing[item.model_id]}
                          >
                            Remove
                          </button>
                        {/if}
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <!-- List view -->
            <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
              {#each filteredItems() as item (item.model_id)}
                <div class="px-4 py-3 flex items-center gap-4 {selectedModels.has(item.model_id) ? 'bg-green-900/10' : ''}">
                  <input type="checkbox" checked={selectedModels.has(item.model_id)} onchange={() => toggleSelect(item.model_id)} class="rounded shrink-0" />
                  <div class="flex-1 min-w-0">
                    <span class="text-gray-100 font-medium text-sm">{item.model_name}</span>
                    <span class="text-gray-600 text-xs ml-2">{item.filename}</span>
                    {#if item.status === 'rename_pending' && item.dest_filename}
                      <span class="text-blue-400 text-xs ml-2">(on dest: {item.dest_filename})</span>
                    {/if}
                  </div>
                  {#if item.category}
                    <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400 shrink-0">{item.category}</span>
                  {/if}
                  <span class="text-xs shrink-0 w-20 text-right text-gray-500">{formatSize(item.size)}</span>
                  <span class="text-xs shrink-0 px-2 py-0.5 rounded border {statusColors[item.status] || 'bg-gray-700 text-gray-400 border-gray-600'}">
                    {statusLabels[item.status] || item.status}
                  </span>
                  <div class="flex gap-1 shrink-0">
                    {#if item.status === 'not_synced' || item.status === 'outdated'}
                      <button
                        class="px-2 py-1 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                        onclick={() => syncModel(item.model_id)}
                        disabled={syncing[item.model_id]}
                      >
                        {syncing[item.model_id] ? '...' : 'Sync'}
                      </button>
                    {:else if item.status === 'rename_pending'}
                      <button
                        class="px-2 py-1 text-xs rounded bg-blue-700 hover:bg-blue-600 text-white disabled:opacity-50"
                        onclick={() => applyRename(item.model_id)}
                        disabled={syncing[item.model_id]}
                      >
                        Apply Rename
                      </button>
                    {:else if item.status === 'synced' || item.status === 'orphaned'}
                      {#if confirmRemove === item.model_id}
                        <div class="flex gap-1 items-center">
                          <span class="text-xs text-red-400 mr-1">Remove from target?</span>
                          <button class="px-2 py-1 text-xs rounded bg-red-700 text-white" onclick={() => { confirmRemove = null; removeModel(item.model_id); }}>Yes</button>
                          <button class="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300" onclick={() => confirmRemove = null}>No</button>
                        </div>
                      {:else}
                        <button
                          class="px-2 py-1 text-xs rounded bg-gray-700 hover:bg-red-800 text-gray-400 hover:text-red-300 disabled:opacity-50"
                          onclick={() => confirmRemove = item.model_id}
                          disabled={syncing[item.model_id]}
                        >
                          Remove
                        </button>
                      {/if}
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="text-center py-20">
            <span class="text-6xl mb-4 block">&#x1F4E1;</span>
            <h3 class="text-xl font-medium text-gray-300 mb-2">No models found</h3>
            <p class="text-gray-500 max-w-md mx-auto">
              {#if search || activeCategory}
                No models match your current filters. Try clearing the search or selecting a different category.
              {:else}
                No models in the library. Add models to the library first, then sync them here.
              {/if}
            </p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
