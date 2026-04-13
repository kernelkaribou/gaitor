<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { models, searchQuery, viewMode } from '../lib/stores.js';
  import ModelCard from '../components/ModelCard.svelte';

  let libraryStatus = $state(null);
  let modelList = $state([]);
  let search = $state('');

  onMount(async () => {
    try {
      const [status, modelsData] = await Promise.all([
        api.getLibraryStatus(),
        api.listModels(),
      ]);
      libraryStatus = status;
      modelList = modelsData.models || [];
    } catch (err) {
      console.error('Failed to load library:', err);
    }
  });

  let filteredModels = $derived(
    search
      ? modelList.filter(
          (m) =>
            m.name.toLowerCase().includes(search.toLowerCase()) ||
            m.filename.toLowerCase().includes(search.toLowerCase())
        )
      : modelList
  );
</script>

<div>
  <!-- Search and controls bar -->
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center gap-3">
      <h2 class="text-lg font-semibold text-gray-200">Library</h2>
      {#if libraryStatus}
        <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
          {libraryStatus.status}
        </span>
      {/if}
    </div>
    <div class="flex items-center gap-3">
      <input
        type="text"
        bind:value={search}
        placeholder="Search models..."
        class="bg-gray-800 border border-gray-600 rounded-md px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-green-500 w-64"
      />
      <button class="px-3 py-1.5 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white transition-colors">
        Scan for Models
      </button>
    </div>
  </div>

  <!-- Model grid -->
  {#if filteredModels.length > 0}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {#each filteredModels as model (model.id)}
        <ModelCard {model} />
      {/each}
    </div>
  {:else}
    <div class="text-center py-20">
      <span class="text-6xl mb-4 block">🐊</span>
      <h3 class="text-xl font-medium text-gray-300 mb-2">No models yet</h3>
      <p class="text-gray-500 max-w-md mx-auto">
        Add models to your library by uploading files, scanning your library directory,
        or retrieving from Hugging Face and CivitAI.
      </p>
    </div>
  {/if}
</div>
