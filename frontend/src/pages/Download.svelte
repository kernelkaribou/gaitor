<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { addToast } from '../lib/stores.js';
  import { formatSize } from '../lib/utils.js';

  let providers = $state([]);
  let url = $state('');
  let resolving = $state(false);
  let resolved = $state(null);
  let error = $state(null);

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

  // CivitAI type to category mapping
  const civitaiTypeMap = {
    'Checkpoint': 'checkpoints',
    'LORA': 'loras',
    'TextualInversion': 'embeddings',
    'Hypernetwork': 'hypernetworks',
    'Controlnet': 'controlnet',
    'Upscaler': 'upscale_models',
    'VAE': 'vae',
    'LoCon': 'loras',
    'DoRA': 'loras',
    'MotionModule': 'animatediff_models',
  };

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
    description = '';
    try {
      resolved = await api.resolveUrl(url);

      // Auto-populate metadata from source
      if (resolved.description) {
        // Strip HTML tags from CivitAI descriptions
        description = resolved.description.replace(/<[^>]*>/g, '').slice(0, 500);
      }

      // Auto-select category from CivitAI model type
      if (resolved.model_type && civitaiTypeMap[resolved.model_type]) {
        category = civitaiTypeMap[resolved.model_type];
      }
    } catch (err) {
      error = err.message || 'Failed to resolve URL';
    }
    resolving = false;
  }

  function selectFile(file, previewUrl = null) {
    selectedFile = { ...file, previewUrl };
    modelName = file.filename.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');

    // If CivitAI, use model name instead of filename
    if (resolved?.model_info?.name) {
      modelName = resolved.model_info.name;
    }
  }

  async function startDownload() {
    if (!selectedFile) return;
    error = null;
    try {
      const params = {
        url: selectedFile.download_url,
        filename: selectedFile.filename,
        category,
        name: modelName || undefined,
        description: description || undefined,
        provider: resolved?.provider || 'url',
        thumbnail_url: selectedFile.previewUrl || resolved?.preview_url || undefined,
      };
      await api.startDownload(params);
      addToast({ type: 'info', title: 'Download started', message: `${modelName || selectedFile.filename}` });

      // Clear form for next download
      resolved = null;
      selectedFile = null;
      url = '';
      modelName = '';
      description = '';
    } catch (err) {
      error = err.message;
    }
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

  function clearUrl() {
    url = '';
    resolved = null;
    selectedFile = null;
    error = null;
    description = '';
    modelName = '';
  }

  function clearSearch() {
    searchQuery = '';
    searchResults = [];
  }
</script>

<div class="max-w-4xl mx-auto">
  {#if error}
    <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
      {error}
      <button class="ml-2 underline" onclick={() => error = null}>dismiss</button>
    </div>
  {/if}

  <h2 class="text-lg font-semibold text-gray-200 mb-4">Download Models</h2>

  <!-- Providers status -->
  <div class="flex gap-3 mb-6">
    {#each providers as p}
      <span class="text-xs px-2 py-1 rounded-full {p.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-800 text-gray-500'}">
        {p.name}: {p.configured ? 'Connected' : 'No token'}
      </span>
    {/each}
  </div>

  <!-- URL input -->
  <div class="flex gap-2 mb-6">
    <div class="flex-1 relative">
      <input
        type="text"
        bind:value={url}
        placeholder="Paste any model URL (HuggingFace, CivitAI, Ollama, or direct link)..."
        class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-600 pr-8"
        onkeydown={(e) => e.key === 'Enter' && resolveUrl()}
      />
      {#if url}
        <button
          class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-sm"
          onclick={clearUrl}
        >&#x2715;</button>
      {/if}
    </div>
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
      <div class="flex-1 relative">
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search models..."
          class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-600 pr-8"
          onkeydown={(e) => e.key === 'Enter' && searchModels()}
        />
        {#if searchQuery}
          <button
            class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-sm"
            onclick={clearSearch}
          >&#x2715;</button>
        {/if}
      </div>
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
            {#if result.type}
              <span class="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 ml-2">{result.type}</span>
            {/if}
            {#if result.author || result.creator}
              <span class="text-gray-500 text-xs ml-2">by {result.author || result.creator}</span>
            {/if}
            {#if result.downloads}
              <span class="text-gray-600 text-xs ml-2">{result.downloads.toLocaleString()} downloads</span>
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
        <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">{resolved.provider || 'url'}</span>
        {#if resolved.repo_id}
          <span class="text-gray-400 text-sm font-mono">{resolved.repo_id}</span>
        {/if}
        {#if resolved.model_info?.name}
          <span class="text-gray-200 font-medium">{resolved.model_info.name}</span>
        {/if}
        {#if resolved.model_type}
          <span class="text-xs px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-400">{resolved.model_type}</span>
        {/if}
      </div>

      {#if resolved.repo_info?.description}
        <p class="text-xs text-gray-500 mb-3 line-clamp-2">{resolved.repo_info.description}</p>
      {/if}

      <!-- CivitAI preview image -->
      {#if resolved.preview_url}
        <div class="mb-3">
          <img src={resolved.preview_url} alt="Preview" class="w-32 h-32 object-cover rounded-lg border border-gray-700" />
        </div>
      {/if}

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
              {@const previewUrl = version.images?.[0] || resolved.preview_url || null}
              <button
                class="w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors
                  {selectedFile?.download_url === file.download_url ? 'bg-green-900/30 border border-green-700' : 'bg-gray-900 hover:bg-gray-700'}"
                onclick={() => selectFile({ filename: file.name, download_url: file.download_url, size: file.size }, previewUrl)}
              >
                <span class="text-gray-200 font-mono text-xs">{file.name}</span>
                <span class="text-gray-500 text-xs">{formatSize(file.size)}</span>
              </button>
            {/each}
          </div>
        {/each}
      {/if}

      <!-- Generic URL files -->
      {#if resolved.provider === 'url' && resolved.files}
        <p class="text-gray-500 text-xs mb-2">Direct download:</p>
        <div class="space-y-1">
          {#each resolved.files as file}
            <button
              class="w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors
                {selectedFile?.filename === file.filename ? 'bg-green-900/30 border border-green-700' : 'bg-gray-900 hover:bg-gray-700'}"
              onclick={() => selectFile(file)}
            >
              <span class="text-gray-200 font-mono text-xs">{file.filename}</span>
              {#if file.size}
                <span class="text-gray-500 text-xs">{formatSize(file.size)}</span>
              {/if}
            </button>
          {/each}
        </div>
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
        <span class="text-xs text-gray-500">
          Size: {formatSize(selectedFile.size)}
          {#if selectedFile.previewUrl || resolved?.preview_url}
            &middot; Preview image will be saved as thumbnail
          {/if}
        </span>
        <button
          class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg"
          onclick={startDownload}
        >
          Download to Library
        </button>
      </div>
    </div>
  {/if}

  {#if !resolved && !selectedFile && searchResults.length === 0}
    <div class="text-center py-12">
      <span class="text-5xl mb-4 block">&#x1F310;</span>
      <p class="text-gray-500 max-w-md mx-auto">
        Paste any model URL above - HuggingFace, CivitAI, Ollama, or any direct download link.
        Use search to browse HuggingFace and CivitAI catalogs.
        Models will be downloaded directly into your library.
      </p>
    </div>
  {/if}
</div>
