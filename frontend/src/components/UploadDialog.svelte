<script>
  import { api } from '../lib/api.js';
  import { formatSize } from '../lib/utils.js';
  import { onMount, onDestroy } from 'svelte';

  let { categories, onUploaded, onClose } = $props();

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose();
  }
  onMount(() => document.addEventListener('keydown', handleKeydown));
  onDestroy(() => document.removeEventListener('keydown', handleKeydown));

  let file = $state(null);
  let name = $state('');
  let category = $state('other');
  let description = $state('');
  let tags = $state('');
  let uploading = $state(false);
  let progress = $state(0);
  let progressBytes = $state({ loaded: 0, total: 0 });
  let error = $state(null);

  function handleFileSelect(event) {
    const selected = event.target.files[0];
    if (selected) {
      file = selected;
      if (!name) {
        name = selected.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
      }
      const ext = selected.name.split('.').pop().toLowerCase();
      const extMap = { safetensors: 'checkpoints', ckpt: 'checkpoints', gguf: 'llm', pt: 'vae', pth: 'upscalers' };
      if (extMap[ext] && categories.some((c) => c.id === extMap[ext])) {
        category = extMap[ext];
      }
    }
  }

  function handleProgress(e) {
    progress = e.percent;
    progressBytes = { loaded: e.loaded, total: e.total };
  }

  async function handleUpload() {
    if (!file || !name) return;
    uploading = true;
    progress = 0;
    error = null;
    try {
      await api.uploadModel(file, name, category, description, tags, handleProgress);
      onUploaded();
    } catch (err) {
      error = err.message;
    }
    uploading = false;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="fixed inset-0 bg-black/50 z-40" onclick={onClose}></div>

<!-- Dialog -->
<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
  <div class="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md shadow-xl">
    <div class="p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-100">Upload Model</h2>
        <button class="text-gray-400 hover:text-gray-200 text-xl" onclick={onClose}>&#x2715;</button>
      </div>

      {#if error}
        <div class="bg-red-900/30 border border-red-700 rounded-md px-3 py-2 mb-4 text-red-300 text-sm">{error}</div>
      {/if}

      <div class="space-y-4">
        <!-- File input -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Model File</label>
          <input
            type="file"
            onchange={handleFileSelect}
            class="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-gray-700 file:text-gray-200 hover:file:bg-gray-600"
          />
          {#if file}
            <p class="text-xs text-gray-500 mt-1">{file.name} ({formatSize(file.size)})</p>
          {/if}
        </div>

        <!-- Name -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Model Name</label>
          <input bind:value={name} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" placeholder="My Model" />
        </div>

        <!-- Category -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Category</label>
          <select bind:value={category} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500">
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
        </div>

        <!-- Description -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Description (optional)</label>
          <textarea bind:value={description} rows="2" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500 resize-none"></textarea>
        </div>

        <!-- Tags -->
        <div>
          <label class="block text-sm text-gray-400 mb-1">Tags (comma-separated, optional)</label>
          <input bind:value={tags} class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-green-500" placeholder="sdxl, base, 1024px" />
        </div>

        <!-- Progress bar -->
        {#if uploading}
          <div>
            <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>Uploading... {progress}%</span>
              <span>{formatSize(progressBytes.loaded)} / {formatSize(progressBytes.total)}</span>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2.5">
              <div
                class="bg-green-500 h-2.5 rounded-full transition-all duration-300"
                style="width: {progress}%"
              ></div>
            </div>
          </div>
        {/if}

        <!-- Upload button -->
        <div class="flex gap-2 pt-2">
          <button
            class="flex-1 px-4 py-2 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleUpload}
            disabled={uploading || !file || !name}
          >
            {uploading ? `Uploading ${progress}%` : 'Upload'}
          </button>
          <button class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200" onclick={onClose} disabled={uploading}>Cancel</button>
        </div>
      </div>
    </div>
  </div>
</div>
