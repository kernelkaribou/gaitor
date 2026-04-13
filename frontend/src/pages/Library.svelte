<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { models, searchQuery, viewMode, selectedCategory } from '../lib/stores.js';
  import ModelCard from '../components/ModelCard.svelte';
  import ModelDetail from '../components/ModelDetail.svelte';
  import UploadDialog from '../components/UploadDialog.svelte';
  import ScanResults from '../components/ScanResults.svelte';
  import ConfirmDialog from '../components/ConfirmDialog.svelte';

  let libraryStatus = $state(null);
  let modelList = $state([]);
  let categories = $state([]);
  let search = $state('');
  let selectedModel = $state(null);
  let showUpload = $state(false);
  let scanResults = $state(null);
  let scanning = $state(false);
  let deleteTarget = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let activeCategory = $state(null);
  let currentView = $state('grid');

  async function loadData() {
    loading = true;
    error = null;
    try {
      const [status, modelsData, catsData] = await Promise.all([
        api.getLibraryStatus(),
        api.listModels(),
        api.getCategories(),
      ]);
      libraryStatus = status;
      modelList = modelsData.models || [];
      categories = catsData.categories || [];
    } catch (err) {
      error = err.message;
      console.error('Failed to load library:', err);
    }
    loading = false;
  }

  onMount(loadData);

  async function handleScan() {
    scanning = true;
    try {
      const result = await api.scanLibrary();
      scanResults = result;
    } catch (err) {
      error = err.message;
    }
    scanning = false;
  }

  async function handleCataloged() {
    scanResults = null;
    await loadData();
  }

  async function handleUploaded() {
    showUpload = false;
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

  async function confirmDelete(confirmName) {
    try {
      await api.deleteModel(deleteTarget.id, confirmName);
      deleteTarget = null;
      selectedModel = null;
      await loadData();
    } catch (err) {
      throw err;
    }
  }

  function formatSize(bytes) {
    if (!bytes) return '-';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i++;
    }
    return `${size.toFixed(1)} ${units[i]}`;
  }

  let filteredModels = $derived(() => {
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
    return result;
  });

  let categoryCountMap = $derived(() => {
    const map = {};
    for (const m of modelList) {
      map[m.category] = (map[m.category] || 0) + 1;
    }
    return map;
  });
</script>

<div class="flex gap-6">
  <!-- Category sidebar -->
  <aside class="w-48 shrink-0">
    <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2 font-semibold">Categories</h3>
    <button
      class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-1 {activeCategory === null ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
      onclick={() => activeCategory = null}
    >
      All Models
      <span class="text-xs text-gray-500 ml-1">({modelList.length})</span>
    </button>
    {#each categories as cat}
      {@const count = categoryCountMap()[cat.id] || 0}
      <button
        class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors mb-0.5 {activeCategory === cat.id ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}"
        onclick={() => activeCategory = cat.id}
      >
        {cat.label}
        {#if count > 0}
          <span class="text-xs text-gray-500 ml-1">({count})</span>
        {/if}
      </button>
    {/each}
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
        <input
          type="text"
          bind:value={search}
          placeholder="Search models..."
          class="bg-gray-800 border border-gray-600 rounded-md px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-green-500 w-56"
        />
        <!-- View toggle -->
        <div class="flex border border-gray-600 rounded-md overflow-hidden">
          <button
            class="px-2 py-1.5 text-sm transition-colors {currentView === 'grid' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
            onclick={() => currentView = 'grid'}
            title="Grid view"
          >▦</button>
          <button
            class="px-2 py-1.5 text-sm transition-colors {currentView === 'list' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
            onclick={() => currentView = 'list'}
            title="List view"
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
          class="px-3 py-1.5 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white transition-colors"
          onclick={() => showUpload = true}
        >
          Upload
        </button>
      </div>
    </div>

    {#if error}
      <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
        {error}
        <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
      </div>
    {/if}

    <!-- Scan results -->
    {#if scanResults && scanResults.count > 0}
      <ScanResults
        results={scanResults}
        {categories}
        onCataloged={handleCataloged}
        onDismiss={() => scanResults = null}
      />
    {:else if scanResults && scanResults.count === 0}
      <div class="bg-gray-800 border border-gray-700 rounded-md px-4 py-3 mb-4 text-gray-400 text-sm">
        No untracked models found. All files are already cataloged.
        <button class="ml-2 underline text-gray-500" onclick={() => scanResults = null}>dismiss</button>
      </div>
    {/if}

    <!-- Model grid/list -->
    {#if loading}
      <div class="text-center py-20 text-gray-500">Loading...</div>
    {:else if filteredModels().length > 0}
      {#if currentView === 'grid'}
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {#each filteredModels() as model (model.id)}
            <ModelCard
              {model}
              {formatSize}
              onSelect={() => selectedModel = model}
            />
          {/each}
        </div>
      {:else}
        <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
          {#each filteredModels() as model (model.id)}
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
                <span class="text-green-500 text-xs shrink-0" title="Verified">✓</span>
              {/if}
            </button>
          {/each}
        </div>
      {/if}
    {:else}
      <div class="text-center py-20">
        <span class="text-6xl mb-4 block">🐊</span>
        <h3 class="text-xl font-medium text-gray-300 mb-2">No models yet</h3>
        <p class="text-gray-500 max-w-md mx-auto mb-4">
          Add models to your library by uploading files, scanning your library directory,
          or retrieving from Hugging Face and CivitAI.
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
            onclick={() => showUpload = true}
          >
            Upload a Model
          </button>
        </div>
      </div>
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

<!-- Upload dialog -->
{#if showUpload}
  <UploadDialog
    {categories}
    onUploaded={handleUploaded}
    onClose={() => showUpload = false}
  />
{/if}

<!-- Delete confirmation -->
{#if deleteTarget}
  <ConfirmDialog
    title="Delete Model from Library"
    message="This will permanently delete the model file and metadata from the library. This action cannot be undone."
    warningText="Type the model name to confirm:"
    confirmValue={deleteTarget.name}
    confirmLabel="Delete Forever"
    danger={true}
    onConfirm={confirmDelete}
    onCancel={() => deleteTarget = null}
  />
{/if}
