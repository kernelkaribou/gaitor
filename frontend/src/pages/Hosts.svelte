<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { formatSize } from '../lib/utils.js';
  import ModelCard from '../components/ModelCard.svelte';
  import HostScanResults from '../components/HostScanResults.svelte';

  let { onBack } = $props();

  let hosts = $state([]);
  let selectedHost = $state(null);
  let syncStatus = $state([]);
  let categories = $state([]);
  let loading = $state(true);
  let syncing = $state({});
  let error = $state(null);
  let search = $state('');
  let activeCategory = $state(null);
  let confirmRemove = $state(null);
  let scanning = $state(false);
  let scanResults = $state(null);
  let scanKey = $state(0);
  let linking = $state({});

  function usagePercent(total, free) {
    if (!total) return 0;
    return Math.round(((total - free) / total) * 100);
  }

  function handleTaskComplete() {
    syncing = {};
    if (selectedHost) selectHost(selectedHost);
  }

  onMount(async () => {
    try {
      const [hostData, catsData] = await Promise.all([
        api.listHosts(),
        api.getCategories(),
      ]);
      hosts = hostData.hosts || [];
      categories = catsData.categories || [];
    } catch (err) {
      error = err.message;
    }
    loading = false;
    window.addEventListener('gaitor:task-complete', handleTaskComplete);
  });

  onDestroy(() => {
    window.removeEventListener('gaitor:task-complete', handleTaskComplete);
  });

  async function selectHost(host) {
    selectedHost = host;
    loading = true;
    search = '';
    activeCategory = null;
    try {
      const data = await api.getHostSyncStatus(host.id);
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
      await api.syncModelToHost(selectedHost.id, modelId);
    } catch (err) {
      error = err.message;
      syncing = { ...syncing, [modelId]: false };
    }
  }

  async function removeModel(modelId) {
    syncing = { ...syncing, [modelId]: true };
    try {
      await api.removeFromHost(selectedHost.id, modelId);
      await selectHost(selectedHost);
    } catch (err) {
      error = err.message;
    }
    syncing = { ...syncing, [modelId]: false };
  }

  async function applyRename(modelId) {
    syncing = { ...syncing, [modelId]: true };
    try {
      await api.applyRenameOnHost(selectedHost.id, modelId);
      await selectHost(selectedHost);
    } catch (err) {
      error = err.message;
    }
    syncing = { ...syncing, [modelId]: false };
  }

  async function handleHostScan() {
    scanning = true;
    error = null;
    try {
      const result = await api.scanHost(selectedHost.id);
      scanResults = result;
      scanKey += 1;
    } catch (err) {
      error = err.message;
    }
    scanning = false;
  }

  async function linkModel(relativePath, libraryModelId) {
    linking = { ...linking, [relativePath]: true };
    error = null;
    try {
      await api.linkHostModel(selectedHost.id, relativePath, libraryModelId);
      // Re-scan to refresh results
      const result = await api.scanHost(selectedHost.id);
      scanResults = result;
      scanKey += 1;
    } catch (err) {
      error = err.message;
    }
    linking = { ...linking, [relativePath]: false };
  }

  async function bulkLinkMatched() {
    if (!scanResults) return;
    const matched = scanResults.unmanaged.filter(u => u.match && u.match.confidence === 'high');
    if (matched.length === 0) return;
    error = null;
    linking = { ...linking, _bulk: true };
    try {
      const links = matched.map(u => ({
        relative_path: u.relative_path,
        library_model_id: u.match.library_model_id,
      }));
      await api.bulkLinkHostModels(selectedHost.id, links);
      const result = await api.scanHost(selectedHost.id);
      scanResults = result;
      scanKey += 1;
    } catch (err) {
      error = err.message;
    }
    linking = { ...linking, _bulk: false };
  }

  async function importModel(item, importName, importCategory) {
    linking = { ...linking, [item.relative_path]: true };
    error = null;
    try {
      await api.importFromHost(selectedHost.id, {
        relative_path: item.relative_path,
        name: importName,
        category: importCategory,
      });
      const result = await api.scanHost(selectedHost.id);
      scanResults = result;
      scanKey += 1;
    } catch (err) {
      error = err.message;
    }
    linking = { ...linking, [item.relative_path]: false };
  }

  function dismissScan() {
    scanResults = null;
    // Refresh sync status since linking/importing may have changed it
    if (selectedHost) selectHost(selectedHost);
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

  // Only show models that are actually on the host (not "not_synced")
  let hostModels = $derived(syncStatus.filter(s => s.status !== 'not_synced'));

  let filteredItems = $derived.by(() => {
    let result = hostModels;
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

  let categoryCountMap = $derived.by(() => {
    const map = {};
    for (const s of hostModels) {
      if (s.category) {
        map[s.category] = (map[s.category] || 0) + 1;
      }
    }
    return map;
  });

  let syncSummary = $derived.by(() => {
    const counts = { synced: 0, outdated: 0, rename_pending: 0, orphaned: 0 };
    for (const s of hostModels) {
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

  {#if !selectedHost}
    <!-- Host list -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-200">Hosts</h2>
    </div>

    {#if loading}
      <div class="text-center py-20 text-gray-500">Loading...</div>
    {:else if hosts.length === 0}
      <div class="text-center py-20">
        <h3 class="text-xl font-medium text-gray-300 mb-2">No hosts found</h3>
        <p class="text-gray-500 max-w-md mx-auto">
          Mount host directories as Docker volumes under <code class="bg-gray-800 px-1 rounded">/hosts/</code> to manage them here.
        </p>
      </div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {#each hosts as host}
          {@const isHealthy = host.health?.status === 'healthy'}
          {@const isDegraded = host.health?.status === 'degraded'}
          {@const isOffline = host.health?.status === 'offline' || host.health?.status === 'error'}
          <button
            class="bg-gray-800 rounded-lg border border-gray-700 p-5 hover:border-green-600/50 transition-colors text-left w-full {isOffline ? 'opacity-60' : ''}"
            onclick={() => selectHost(host)}
            disabled={isOffline}
          >
            <div class="flex items-center justify-between mb-2">
              <h3 class="font-medium text-gray-100">{host.name}</h3>
              <span class="text-xs px-2 py-0.5 rounded-full {isHealthy ? 'bg-green-900/40 text-green-400' : isDegraded ? 'bg-yellow-900/40 text-yellow-400' : 'bg-red-900/40 text-red-400'}">
                {isHealthy ? 'Healthy' : isDegraded ? 'Read-only' : 'Offline'}
              </span>
            </div>
            <p class="text-xs text-gray-500 font-mono mb-3">{host.path}</p>
            {#if isOffline || isDegraded}
              <p class="text-xs text-yellow-500 mb-2">{host.health?.message}</p>
            {/if}
            {#if host.disk_total}
              <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
                <div
                  class="bg-green-500 h-2 rounded-full"
                  style="width: {usagePercent(host.disk_total, host.disk_free)}%"
                ></div>
              </div>
              <p class="text-xs text-gray-500">
                {formatSize(host.disk_free)} free of {formatSize(host.disk_total)}
              </p>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  {:else}
    <!-- Host detail - Library-style layout -->
    <div class="flex gap-6">
      <!-- Category sidebar -->
      <aside class="w-48 shrink-0">
        <button class="text-gray-400 hover:text-gray-200 text-sm mb-4 flex items-center gap-1" onclick={() => selectedHost = null}>
          &#x2190; All Hosts
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
          {@const count = categoryCountMap[cat.id] || 0}
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
            <p class="text-gray-300">{hostModels.length} model{hostModels.length !== 1 ? 's' : ''} on host</p>
            {#if syncSummary.synced > 0}
              <p class="text-green-400">{syncSummary.synced} synced</p>
            {/if}
            {#if syncSummary.outdated > 0}
              <p class="text-yellow-400">{syncSummary.outdated} outdated</p>
            {/if}
            {#if syncSummary.rename_pending > 0}
              <p class="text-blue-400">{syncSummary.rename_pending} rename pending</p>
            {/if}
            {#if syncSummary.orphaned > 0}
              <p class="text-red-400">{syncSummary.orphaned} orphaned</p>
            {/if}
          </div>
        </div>

        <!-- Disk usage -->
        {#if selectedHost.disk_total}
          <div class="mt-4 pt-4 border-t border-gray-700">
            <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Disk Usage</h3>
            <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
              <div
                class="bg-green-500 h-2 rounded-full"
                style="width: {usagePercent(selectedHost.disk_total, selectedHost.disk_free)}%"
              ></div>
            </div>
            <p class="text-xs text-gray-500">{formatSize(selectedHost.disk_free)} free</p>
          </div>
        {/if}
      </aside>

      <!-- Main content -->
      <div class="flex-1 min-w-0">
        <!-- Controls bar -->
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-gray-200">{selectedHost.name}</h2>
            <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
              {hostModels.length} model{hostModels.length !== 1 ? 's' : ''} on host
            </span>
            <button
              class="px-3 py-1.5 text-sm rounded-md bg-yellow-600 hover:bg-yellow-500 text-white disabled:opacity-50"
              onclick={handleHostScan}
              disabled={scanning}
            >
              {scanning ? 'Scanning...' : 'Scan Host'}
            </button>
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
          </div>
        </div>

        <!-- Host scan results -->
        {#if scanResults && scanResults.count > 0}
          {#key scanKey}
            <HostScanResults
              results={scanResults}
              {categories}
              {linking}
              onLink={linkModel}
              onBulkLink={bulkLinkMatched}
              onImport={importModel}
              onDismiss={dismissScan}
            />
          {/key}
        {:else if scanResults && scanResults.count === 0}
          <div class="bg-gray-800 border border-gray-700 rounded-md px-4 py-3 mb-4 text-gray-400 text-sm">
            No unmanaged models found. All model files on this host are already managed.
            {#if scanResults.already_managed > 0}
              ({scanResults.already_managed} managed files detected)
            {/if}
            <button class="ml-2 underline text-gray-500" onclick={dismissScan}>dismiss</button>
          </div>
        {/if}

        {#if !(scanResults && scanResults.count > 0)}
        {#if loading}
          <div class="text-center py-10 text-gray-500">Loading...</div>
        {:else if filteredItems.length > 0}
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {#each filteredItems as item (item.model_id)}
              <div class="relative">
                <ModelCard
                  model={{
                    id: item.model_id,
                    name: item.model_name,
                    filename: item.filename,
                    category: item.category || 'other',
                    size: item.size,
                    thumbnail: item.thumbnail || null,
                    hash: item.hash || null,
                    base_model: item.base_model || null,
                  }}
                  {formatSize}
                  onSelect={() => {}}
                />
                <!-- Status overlay -->
                <div class="absolute top-2 right-2 flex items-center gap-1">
                  <span class="text-xs px-2 py-0.5 rounded border backdrop-blur-sm {statusColors[item.status] || 'bg-gray-700 text-gray-400 border-gray-600'}">
                    {statusLabels[item.status] || item.status}
                  </span>
                </div>
                <!-- Action bar -->
                <div class="absolute bottom-0 left-0 right-0 bg-gray-900/90 backdrop-blur-sm px-3 py-2 flex items-center justify-between rounded-b-lg">
                  {#if item.status === 'rename_pending'}
                    <span class="text-xs text-blue-400 truncate mr-2">Host: {item.host_filename}</span>
                    <button
                      class="px-2 py-1 text-xs rounded bg-blue-700 hover:bg-blue-600 text-white disabled:opacity-50 shrink-0"
                      onclick={() => applyRename(item.model_id)}
                      disabled={syncing[item.model_id]}
                    >
                      Apply Rename
                    </button>
                  {:else if item.status === 'outdated'}
                    <span class="text-xs text-yellow-500">Hash mismatch</span>
                    <button
                      class="px-2 py-1 text-xs rounded bg-yellow-700 hover:bg-yellow-600 text-white disabled:opacity-50 shrink-0"
                      onclick={() => syncModel(item.model_id)}
                      disabled={syncing[item.model_id]}
                    >
                      {syncing[item.model_id] ? 'Syncing...' : 'Re-sync'}
                    </button>
                  {:else if item.status === 'synced' || item.status === 'orphaned'}
                    <span class="text-xs text-gray-500">{item.synced_at ? new Date(item.synced_at).toLocaleDateString() : ''}</span>
                    {#if confirmRemove === item.model_id}
                      <div class="flex gap-1">
                        <button class="px-2 py-1 text-xs rounded bg-red-700 text-white" onclick={() => { confirmRemove = null; removeModel(item.model_id); }}>Remove</button>
                        <button class="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300" onclick={() => confirmRemove = null}>Cancel</button>
                      </div>
                    {:else}
                      <button
                        class="px-2 py-1 text-xs rounded bg-gray-700 hover:bg-red-800 text-gray-400 hover:text-red-300 disabled:opacity-50 shrink-0"
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
        {:else}
          <div class="text-center py-20">
            <h3 class="text-xl font-medium text-gray-300 mb-2">No models on this host</h3>
            <p class="text-gray-500 max-w-md mx-auto">
              {#if search || activeCategory}
                No models match your current filters.
              {:else}
                Sync models from the Library to add them to this host. Open a model in the Library and use the Hosts section to sync.
              {/if}
            </p>
          </div>
        {/if}
        {/if}
      </div>
    </div>
  {/if}
</div>
