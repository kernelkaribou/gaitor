<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';

  let providers = $state([]);
  let url = $state('');
  let resolving = $state(false);
  let resolved = $state(null);
  let downloading = $state(false);
  let error = $state(null);
  let success = $state(null);

  // Download form
  let selectedFile = $state(null);
  let modelName = $state('');
  let category = $state('checkpoints');
  let description = $state('');

  // Search
  let searchQuery = $state('');
  let searchProvider = $state('huggingface');
  let searchResults = $state([]);
  let searching = $state(false);

  let categories = $state([]);

  function formatSize(bytes) {
    if (!bytes) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return `${size.toFixed(1)} ${units[i]}`;
  }

  onMount(async () => {
    try {
      const [provData, catData] = await Promise.all([
        api.getProviders(),
        api.getCategories(),
      ]);
      providers = provData.providers || [];
      categories = catData.categories || [];
    } catch (err) {
      error = err.message;
    }
  });

  async function resolveUrl() {
    if (!url.trim()) return;
    resolving = true;
    error = null;
    resolved = null;
    selectedFile = null;
    try {
      resolved = await api.resolveUrl(url);
    } catch (err) {
      error = err.message || 'Failed to resolve URL';
    }
    resolving = false;
  }

  function selectFile(file) {
    selectedFile = file;
    modelName = file.filename.replace(/\.[^.]+$/, '');
  }

  async function downloadModel() {
    if (!selectedFile) return;
    downloading = true;
    error = null;
    success = null;
    try {
      const result = await api.downloadModel({
        url: selectedFile.download_url,
        filename: selectedFile.filename,
        category,
        name: modelName || undefined,
        description: description || undefined,
        provider: resolved?.provider,
      });
      success = `Downloaded "${result.model?.name || selectedFile.filename}" to ${category}`;
      resolved = null;
      selectedFile = null;
      url = '';
    } catch (err) {
      error = err.message;
    }
    downloading = false;
  }

  async function searchModels() {
    if (!searchQuery.trim()) return;
    searching = true;
    error = null;
    searchResults = [];
    try {
      const data = await api.searchModels(searchQuery, searchProvider);
      searchResults = data.results || [];
    } catch (err) {
      error = err.message;
    }
    searching = false;
  }

  function selectSearchResult(result) {
    if (searchProvider === 'huggingface') {
      url = `https://huggingface.co/${result.repo_id}`;
    } else if (searchProvider === 'civitai') {
      url = `https://civitai.com/models/${result.id}`;
    }
    searchResults = [];
    searchQuery = '';
    resolveUrl();
  }
</script>

<div class="max-w-4xl mx-auto">
  {#if error}
    <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
      {error}
      <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
    </div>
  {/if}
  {#if success}
    <div class="bg-green-900/30 border border-green-700 rounded-md px-4 py-2 mb-4 text-green-300 text-sm">
      ✓ {success}
      <button class="ml-2 underline" onclick={() => success = null}>dismiss</button>
    </div>
  {/if}

  <h2 class="text-lg font-semibold text-gray-200 mb-4">Retrieve Models</h2>

  <!-- Providers status -->
  <div class="flex gap-3 mb-6">
    {#each providers as p}
      <span class="text-xs px-2 py-1 rounded-full {p.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-800 text-gray-500'}">
        {p.name}: {p.configured ? '✓ Connected' : '○ No token'}
      </span>
    {/each}
  </div>

  <!-- URL input -->
  <div class="flex gap-2 mb-6">
    <input
      type="text"
      bind:value={url}
      placeholder="Paste a HuggingFace or CivitAI URL..."
      class="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-600"
      onkeydown={(e) => e.key === 'Enter' && resolveUrl()}
    />
    <button
      class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg disabled:opacity-50"
      onclick={resolveUrl}
      disabled={resolving || !url.trim()}
    >
      {resolving ? 'Resolving...' : 'Resolve'}
    </button>
  </div>

  <!-- Search -->
  <div class="mb-6">
    <div class="flex gap-2">
      <select
        bind:value={searchProvider}
        class="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-300"
      >
        <option value="huggingface">Hugging Face</option>
        <option value="civitai">CivitAI</option>
      </select>
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search models..."
        class="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-600"
        onkeydown={(e) => e.key === 'Enter' && searchModels()}
      />
      <button
        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg disabled:opacity-50"
        onclick={searchModels}
        disabled={searching || !searchQuery.trim()}
      >
        {searching ? '...' : 'Search'}
      </button>
    </div>
    {#if searchResults.length > 0}
      <div class="mt-2 bg-gray-800 border border-gray-700 rounded-lg divide-y divide-gray-700 max-h-64 overflow-y-auto">
        {#each searchResults as result}
          <button
            class="w-full px-4 py-2 text-left hover:bg-gray-700 transition-colors"
            onclick={() => selectSearchResult(result)}
          >
            <span class="text-gray-100 text-sm font-medium">{result.name || result.repo_id}</span>
            {#if result.author || result.creator}
              <span class="text-gray-500 text-xs ml-2">by {result.author || result.creator}</span>
            {/if}
            {#if result.downloads}
              <span class="text-gray-600 text-xs ml-2">↓ {result.downloads.toLocaleString()}</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Resolved content -->
  {#if resolved}
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 mb-6">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">{resolved.provider}</span>
        {#if resolved.repo_id}
          <span class="text-gray-400 text-sm font-mono">{resolved.repo_id}</span>
        {/if}
        {#if resolved.model_info?.name}
          <span class="text-gray-200 font-medium">{resolved.model_info.name}</span>
        {/if}
      </div>

      <!-- HuggingFace files -->
      {#if resolved.provider === 'huggingface' && resolved.files}
        <p class="text-gray-500 text-xs mb-2">{resolved.files.length} model file(s) found:</p>
        <div class="space-y-1">
          {#each resolved.files as file}
            <button
              class="w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors
                {selectedFile?.filename === file.filename ? 'bg-green-900/30 border border-green-700' : 'bg-gray-900 hover:bg-gray-700'}"
              onclick={() => selectFile(file)}
            >
              <span class="text-gray-200 font-mono text-xs">{file.filename}</span>
              <span class="text-gray-500 text-xs">{formatSize(file.size)}</span>
            </button>
          {/each}
        </div>
      {/if}

      <!-- CivitAI versions -->
      {#if resolved.provider === 'civitai' && resolved.model_info?.versions}
        {#each resolved.model_info.versions as version}
          <div class="mb-3">
            <p class="text-gray-400 text-sm font-medium mb-1">{version.name} ({version.base_model})</p>
            {#each version.files as file}
              <button
                class="w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors
                  {selectedFile?.download_url === file.download_url ? 'bg-green-900/30 border border-green-700' : 'bg-gray-900 hover:bg-gray-700'}"
                onclick={() => selectFile({ filename: file.name, download_url: file.download_url, size: file.size })}
              >
                <span class="text-gray-200 font-mono text-xs">{file.name}</span>
                <span class="text-gray-500 text-xs">{formatSize(file.size)}</span>
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
  {/if}

  <!-- Download form -->
  {#if selectedFile}
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-5">
      <h3 class="text-gray-200 font-medium mb-3">Download: {selectedFile.filename}</h3>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Name</label>
          <input
            type="text"
            bind:value={modelName}
            class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
          />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Category</label>
          <select
            bind:value={category}
            class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm"
          >
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
        </div>
        <div class="col-span-2">
          <label class="block text-xs text-gray-400 mb-1">Description (optional)</label>
          <input
            type="text"
            bind:value={description}
            class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
          />
        </div>
      </div>
      <div class="mt-4 flex items-center justify-between">
        <span class="text-xs text-gray-500">Size: {formatSize(selectedFile.size)}</span>
        <button
          class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg disabled:opacity-50"
          onclick={downloadModel}
          disabled={downloading}
        >
          {downloading ? 'Downloading...' : 'Download to Library'}
        </button>
      </div>
    </div>
  {/if}

  {#if !resolved && !selectedFile && searchResults.length === 0}
    <div class="text-center py-12">
      <span class="text-5xl mb-4 block">🌐</span>
      <p class="text-gray-500 max-w-md mx-auto">
        Paste a HuggingFace or CivitAI URL above, or use search to find models.
        Models will be downloaded directly into your library.
      </p>
    </div>
  {/if}
</div>
