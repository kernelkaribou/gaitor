<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';

  let { onBack } = $props();

  let destinations = $state([]);
  let selectedDest = $state(null);
  let syncStatus = $state([]);
  let loading = $state(true);
  let syncing = $state({});
  let error = $state(null);

  function formatSize(bytes) {
    if (!bytes) return '—';
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
      const data = await api.listDestinations();
      destinations = data.destinations || [];
    } catch (err) {
      error = err.message;
    }
    loading = false;
  });

  async function selectDestination(dest) {
    selectedDest = dest;
    loading = true;
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

  const statusColors = {
    synced: 'text-green-400',
    not_synced: 'text-gray-500',
    outdated: 'text-yellow-400',
    rename_pending: 'text-blue-400',
    orphaned: 'text-red-400',
  };
  const statusLabels = {
    synced: '✓ Synced',
    not_synced: '○ Not synced',
    outdated: '↻ Outdated',
    rename_pending: '↔ Rename pending',
    orphaned: '⚠ Orphaned',
  };
</script>

<div>
  {#if error}
    <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
      {error}
      <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
    </div>
  {/if}

  {#if !selectedDest}
    <!-- Destination list -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-200">Destinations</h2>
    </div>

    {#if loading}
      <div class="text-center py-20 text-gray-500">Loading...</div>
    {:else if destinations.length === 0}
      <div class="text-center py-20">
        <span class="text-6xl mb-4 block">📡</span>
        <h3 class="text-xl font-medium text-gray-300 mb-2">No destinations found</h3>
        <p class="text-gray-500 max-w-md mx-auto">
          Mount destination directories as Docker volumes under <code class="bg-gray-800 px-1 rounded">/dest/</code> to manage them here.
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
    <!-- Destination detail with sync status -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <button class="text-gray-400 hover:text-gray-200" onclick={() => selectedDest = null}>← Back</button>
        <h2 class="text-lg font-semibold text-gray-200">{selectedDest.name}</h2>
        {#if selectedDest.disk_free}
          <span class="text-xs text-gray-500">{formatSize(selectedDest.disk_free)} free</span>
        {/if}
      </div>
      <div class="flex gap-2">
        {#if syncStatus.filter(s => s.status === 'not_synced').length > 0}
          <button
            class="px-3 py-1.5 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white"
            onclick={bulkSync}
          >
            Sync All ({syncStatus.filter(s => s.status === 'not_synced').length})
          </button>
        {/if}
      </div>
    </div>

    {#if loading}
      <div class="text-center py-10 text-gray-500">Loading sync status...</div>
    {:else}
      <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
        {#each syncStatus as item (item.model_id)}
          <div class="px-4 py-3 flex items-center gap-4">
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
            <span class="text-xs shrink-0 w-28 {statusColors[item.status] || 'text-gray-500'}">
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
                <button
                  class="px-2 py-1 text-xs rounded bg-gray-700 hover:bg-red-800 text-gray-400 hover:text-red-300 disabled:opacity-50"
                  onclick={() => removeModel(item.model_id)}
                  disabled={syncing[item.model_id]}
                >
                  Remove
                </button>
              {/if}
            </div>
          </div>
        {/each}
        {#if syncStatus.length === 0}
          <div class="px-4 py-8 text-center text-gray-500">
            No models in library. Add models to the library first.
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
