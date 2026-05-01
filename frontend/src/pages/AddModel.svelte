<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { addToast } from '../lib/stores.js';
  import { formatSize } from '../lib/utils.js';

  let { onBack, prefill, onPrefillConsumed } = $props();

  let activeTab = $state('retrieve');
  let categories = $state([]);

  // --- Retrieve state ---
  let providers = $state([]);
  let url = $state('');
  let resolving = $state(false);
  let resolved = $state(null);
  let retrieveError = $state(null);
  let selectedFile = $state(null);
  let retrieveName = $state('');
  let retrieveCategory = $state('checkpoints');
  let retrieveDescription = $state('');
  let retrieveFilename = $state('');
  let retrieveSubfolder = $state('');
  let retrieveBaseModel = $state('');
  let retrieveThumbnailUrl = $state('');

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

  // --- Upload state ---
  let uploadFile = $state(null);
  let uploadName = $state('');
  let uploadCategory = $state('other');
  let uploadDescription = $state('');
  let uploadTags = $state('');
  let uploadFilename = $state('');
  let uploadSubfolder = $state('');
  let uploadBaseModel = $state('');
  let uploading = $state(false);
  let uploadProgress = $state(0);
  let uploadProgressBytes = $state({ loaded: 0, total: 0 });
  let uploadError = $state(null);

  // Track bookmark ID for auto-delete on successful download
  let promotingBookmarkId = $state(null);

  onMount(async () => {
    try {
      const [provData, catData] = await Promise.all([
        api.getProviders(),
        api.getCategories(),
      ]);
      providers = provData.providers || [];
      categories = catData.categories || [];
    } catch (err) {
      retrieveError = err.message;
    }

    // Apply prefill from bookmark promotion
    if (prefill) {
      activeTab = 'retrieve';
      url = prefill.source_url || '';
      retrieveName = prefill.name || '';
      retrieveDescription = prefill.description || '';
      retrieveBaseModel = prefill.base_model || '';
      retrieveThumbnailUrl = prefill.thumbnail_url || '';
      if (prefill.target_category) retrieveCategory = prefill.target_category;
      if (prefill.bookmark_id) promotingBookmarkId = prefill.bookmark_id;
      onPrefillConsumed?.();
      if (url) resolveUrl();
    }
  });

  // --- Retrieve functions ---
  async function resolveUrl() {
    if (!url.trim()) return;
    resolving = true;
    retrieveError = null;
    resolved = null;
    selectedFile = null;
    // Preserve bookmark prefill values; only clear non-prefilled fields
    const hadPrefill = !!promotingBookmarkId;
    if (!hadPrefill) {
      retrieveDescription = '';
      retrieveBaseModel = '';
      retrieveThumbnailUrl = '';
    }
    retrieveFilename = '';
    retrieveSubfolder = '';
    try {
      resolved = await api.resolveUrl(url);
      if (resolved.description && !retrieveDescription) {
        const doc = new DOMParser().parseFromString(resolved.description, 'text/html');
        retrieveDescription = (doc.body.textContent || '').slice(0, 500);
      }
      if (resolved.model_type && civitaiTypeMap[resolved.model_type] && !hadPrefill) {
        retrieveCategory = civitaiTypeMap[resolved.model_type];
      }
    } catch (err) {
      retrieveError = err.message || 'Failed to resolve URL';
    }
    resolving = false;
  }

  function selectFile(file, previewUrl = null, baseModel = null) {
    selectedFile = { ...file, previewUrl };
    retrieveName = file.filename.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
    retrieveFilename = file.filename;
    if (resolved?.model_info?.name) {
      retrieveName = resolved.model_info.name;
    }
    retrieveThumbnailUrl = previewUrl || resolved?.preview_url || '';
    retrieveBaseModel = baseModel || '';
  }

  async function startDownload() {
    if (!selectedFile) return;
    retrieveError = null;
    try {
      const params = {
        url: selectedFile.download_url,
        filename: retrieveFilename || selectedFile.filename,
        category: retrieveCategory,
        name: retrieveName || undefined,
        description: retrieveDescription || undefined,
        provider: resolved?.provider || 'url',
        thumbnail_url: retrieveThumbnailUrl || undefined,
        subfolder: retrieveSubfolder || undefined,
        base_model: retrieveBaseModel || undefined,
        page_url: url || undefined,
      };
      await api.startDownload(params);
      addToast({ type: 'info', title: 'Download started', message: `${retrieveName || selectedFile.filename}` });

      // Advisory: bookmark should be deleted after download completes, not now
      if (promotingBookmarkId) {
        addToast({ type: 'info', title: 'Bookmark kept', message: 'Remove it from Bookmarks once the download completes' });
        promotingBookmarkId = null;
      }

      resolved = null;
      selectedFile = null;
      url = '';
      retrieveName = '';
      retrieveDescription = '';
      retrieveFilename = '';
      retrieveSubfolder = '';
      retrieveBaseModel = '';
      retrieveThumbnailUrl = '';
    } catch (err) {
      retrieveError = err.message;
    }
  }

  function clearUrl() {
    url = '';
    resolved = null;
    selectedFile = null;
    retrieveError = null;
    retrieveDescription = '';
    retrieveName = '';
    retrieveFilename = '';
    retrieveSubfolder = '';
    retrieveBaseModel = '';
    retrieveThumbnailUrl = '';
  }

  // --- Upload functions ---
  function handleFileSelect(event) {
    const selected = event.target.files[0];
    if (selected) {
      uploadFile = selected;
      uploadFilename = selected.name;
      if (!uploadName) {
        uploadName = selected.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
      }
      const ext = selected.name.split('.').pop().toLowerCase();
      const extMap = { safetensors: 'checkpoints', ckpt: 'checkpoints', gguf: 'llm', pt: 'vae', pth: 'upscalers' };
      if (extMap[ext] && categories.some((c) => c.id === extMap[ext])) {
        uploadCategory = extMap[ext];
      }
    }
  }

  function handleUploadProgress(e) {
    uploadProgress = e.percent;
    uploadProgressBytes = { loaded: e.loaded, total: e.total };
  }

  async function handleUpload() {
    if (!uploadFile || !uploadName) return;
    uploading = true;
    uploadProgress = 0;
    uploadError = null;
    try {
      await api.uploadModel(
        uploadFile, uploadName, uploadCategory, uploadDescription, uploadTags,
        handleUploadProgress, uploadSubfolder, uploadBaseModel, uploadFilename
      );
      addToast({ type: 'success', title: 'Upload complete', message: `${uploadName} added to library` });
      uploadFile = null;
      uploadName = '';
      uploadCategory = 'other';
      uploadDescription = '';
      uploadTags = '';
      uploadFilename = '';
      uploadSubfolder = '';
      uploadBaseModel = '';
      uploadProgress = 0;
    } catch (err) {
      uploadError = err.message;
    }
    uploading = false;
  }
</script>

<div class="max-w-4xl mx-auto">
  <!-- Header with back button -->
  <div class="flex items-center gap-3 mb-6">
    <button
      class="px-3 py-1.5 text-sm rounded-md bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
      onclick={onBack}
    >
      Back to Library
    </button>
    <h2 class="text-lg font-semibold text-gray-200">Add Model</h2>
  </div>

  <!-- Tabs -->
  <div class="flex border-b border-gray-700 mb-6">
    <button
      class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === 'retrieve' ? 'border-green-500 text-gray-100' : 'border-transparent text-gray-400 hover:text-gray-200'}"
      onclick={() => activeTab = 'retrieve'}
    >
      Retrieve from Web
    </button>
    <button
      class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === 'upload' ? 'border-green-500 text-gray-100' : 'border-transparent text-gray-400 hover:text-gray-200'}"
      onclick={() => activeTab = 'upload'}
    >
      Upload File
    </button>
  </div>

  <!-- Retrieve tab -->
  {#if activeTab === 'retrieve'}
    {#if retrieveError}
      <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
        {retrieveError}
        <button class="ml-2 underline" onclick={() => retrieveError = null}>dismiss</button>
      </div>
    {/if}

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

    <!-- Resolved content -->
    {#if resolved}
      <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 mb-6">
        <div class="flex items-start gap-4">
          {#if resolved.preview_url}
            <img src={resolved.preview_url} alt="Preview" class="w-48 h-48 object-cover rounded-lg border border-gray-700 shrink-0" />
          {/if}
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
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
              <p class="text-xs text-gray-500 mb-3 line-clamp-3">{resolved.repo_info.description}</p>
            {/if}

            <!-- HuggingFace files -->
            {#if resolved.provider === 'huggingface' && resolved.files}
              <p class="text-gray-500 text-xs mb-2">{resolved.files.length} model file(s) found:</p>
              <div class="space-y-1 max-h-48 overflow-y-auto">
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
                      onclick={() => selectFile({ filename: file.name, download_url: file.download_url, size: file.size }, previewUrl, version.base_model)}
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
        </div>
      </div>
    {/if}

    <!-- Download form -->
    {#if selectedFile}
      <div class="bg-gray-800 border border-gray-700 rounded-lg p-5">
        <h3 class="text-gray-200 font-medium mb-4">Configure Download</h3>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs text-gray-400 mb-1">Model Name</label>
            <input
              type="text"
              bind:value={retrieveName}
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Filename</label>
            <input
              type="text"
              bind:value={retrieveFilename}
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Category</label>
            <select
              bind:value={retrieveCategory}
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm"
            >
              {#each categories as cat}
                <option value={cat.id}>{cat.label}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Subfolder (optional)</label>
            <input
              type="text"
              bind:value={retrieveSubfolder}
              placeholder="e.g. sdxl"
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Base Model (optional)</label>
            <input
              type="text"
              bind:value={retrieveBaseModel}
              placeholder="e.g. SDXL 1.0, SD 1.5, Flux.1"
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Description (optional)</label>
            <input
              type="text"
              bind:value={retrieveDescription}
              class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:border-green-600"
            />
          </div>
          <div class="col-span-2">
            <label class="block text-xs text-gray-400 mb-1">Thumbnail</label>
            {#if retrieveThumbnailUrl}
              <div class="flex items-center gap-3">
                <img src={retrieveThumbnailUrl} alt="Thumbnail" class="w-16 h-16 object-cover rounded border border-gray-700" />
                <div class="flex-1 min-w-0">
                  <p class="text-xs text-gray-500 truncate">{retrieveThumbnailUrl}</p>
                </div>
                <button
                  class="text-xs text-red-400 hover:text-red-300 shrink-0"
                  onclick={() => retrieveThumbnailUrl = ''}
                >Remove</button>
              </div>
            {:else}
              <p class="text-xs text-gray-600">No thumbnail</p>
            {/if}
          </div>
        </div>
        <div class="mt-4 flex items-center justify-between">
          <span class="text-xs text-gray-500">
            Size: {formatSize(selectedFile.size)}
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

    {#if !resolved && !selectedFile}
      <div class="text-center py-12">
        <p class="text-gray-500 max-w-md mx-auto">
          Paste any model URL above - HuggingFace, CivitAI, Ollama, or any direct download link.
          Models will be downloaded directly into your library.
        </p>
      </div>
    {/if}
  {/if}

  <!-- Upload tab -->
  {#if activeTab === 'upload'}
    {#if uploadError}
      <div class="bg-red-900/30 border border-red-700 rounded-md px-4 py-2 mb-4 text-red-300 text-sm">
        {uploadError}
        <button class="ml-2 underline" onclick={() => uploadError = null}>dismiss</button>
      </div>
    {/if}

    <div class="bg-gray-800 border border-gray-700 rounded-lg p-6">
      <div class="space-y-4">
        <!-- File input -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Model File</label>
          <input
            type="file"
            onchange={handleFileSelect}
            class="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-gray-700 file:text-gray-200 hover:file:bg-gray-600"
          />
          {#if uploadFile}
            <p class="text-xs text-gray-500 mt-1">{uploadFile.name} ({formatSize(uploadFile.size)})</p>
          {/if}
        </div>

        <!-- Name + Filename -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Model Name</label>
            <input
              bind:value={uploadName}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
              placeholder="My Model"
            />
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">Filename</label>
            <input
              bind:value={uploadFilename}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
              placeholder="model.safetensors"
            />
          </div>
        </div>

        <!-- Category + Subfolder -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Category</label>
            <select
              bind:value={uploadCategory}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
            >
              {#each categories as cat}
                <option value={cat.id}>{cat.label}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">Subfolder (optional)</label>
            <input
              bind:value={uploadSubfolder}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
              placeholder="e.g. sdxl"
            />
          </div>
        </div>

        <!-- Base Model + Tags -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Base Model (optional)</label>
            <input
              bind:value={uploadBaseModel}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
              placeholder="e.g. SDXL 1.0, SD 1.5, Flux.1"
            />
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">Tags (comma-separated, optional)</label>
            <input
              bind:value={uploadTags}
              class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500"
              placeholder="sdxl, base, 1024px"
            />
          </div>
        </div>

        <!-- Description -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Description (optional)</label>
          <textarea
            bind:value={uploadDescription}
            rows="2"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500 resize-none"
          ></textarea>
        </div>

        <!-- Progress bar -->
        {#if uploading}
          <div>
            <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>Uploading... {uploadProgress}%</span>
              <span>{formatSize(uploadProgressBytes.loaded)} / {formatSize(uploadProgressBytes.total)}</span>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2.5">
              <div
                class="bg-green-500 h-2.5 rounded-full transition-all duration-300"
                style="width: {uploadProgress}%"
              ></div>
            </div>
          </div>
        {/if}

        <!-- Upload button -->
        <div class="flex gap-2 pt-2">
          <button
            class="px-6 py-2 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleUpload}
            disabled={uploading || !uploadFile || !uploadName}
          >
            {uploading ? `Uploading ${uploadProgress}%` : 'Upload to Library'}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
