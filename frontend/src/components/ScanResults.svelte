<script>
  import { api } from '../lib/api.js';
  import { formatSize } from '../lib/utils.js';

  let { results, categories, onCataloged, onDismiss } = $props();

  let items = $state(
    (results.untracked || []).map((u) => ({
      ...u,
      selected: true,
      name: u.filename.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '),
      category: u.guessed_category || 'other',
      subfolder: u.relative_path.split('/').length > 2 ? u.relative_path.split('/').slice(1, -1).join('/') : '',
    }))
  );
  let cataloging = $state(false);
  let error = $state(null);

  function toggleAll(checked) {
    items = items.map((i) => ({ ...i, selected: checked }));
  }

  let allSelected = $derived(items.every((i) => i.selected));
  let selectedCount = $derived(items.filter((i) => i.selected).length);

  async function handleCatalog() {
    const selected = items.filter((i) => i.selected);
    if (selected.length === 0) return;
    cataloging = true;
    error = null;
    try {
      const models = selected.map((i) => ({
        relative_path: i.relative_path,
        name: i.name,
        category: i.category,
        target_subfolder: i.subfolder || '',
      }));
      await api.bulkCatalog(models);
      onCataloged();
    } catch (err) {
      error = err.message;
    }
    cataloging = false;
  }
</script>

<div class="bg-gray-800 border border-yellow-700/50 rounded-lg mb-4">
  <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-sm font-medium text-gray-200">{results.count} untracked model{results.count !== 1 ? 's' : ''} found</span>
    </div>
    <div class="flex items-center gap-2">
      <button
        class="px-3 py-1 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
        onclick={handleCatalog}
        disabled={cataloging || selectedCount === 0}
      >
        {cataloging ? 'Cataloging...' : `Catalog ${selectedCount} selected`}
      </button>
      <button class="text-gray-400 hover:text-gray-200 text-sm" onclick={onDismiss}>{'\u2715'}</button>
    </div>
  </div>

  {#if error}
    <div class="px-4 py-2 text-red-300 text-sm bg-red-900/20">{error}</div>
  {/if}

  <div class="divide-y divide-gray-700 max-h-[70vh] overflow-y-auto">
    <!-- Select all row -->
    <div class="px-4 py-2 flex items-center gap-3 bg-gray-750">
      <input type="checkbox" checked={allSelected} onchange={(e) => toggleAll(e.target.checked)} class="rounded" />
      <span class="text-xs text-gray-400">Select all</span>
    </div>

    {#each items as item, idx}
      <div class="px-4 py-2.5 flex items-center gap-3">
        <input type="checkbox" bind:checked={item.selected} class="rounded shrink-0" />
        <div class="flex-1 min-w-0 space-y-1">
          <input
            bind:value={item.name}
            class="bg-transparent border-b border-transparent hover:border-gray-600 focus:border-green-500 text-sm text-gray-200 w-full focus:outline-none py-0.5"
          />
          <p class="text-xs text-gray-500 truncate font-mono">{item.relative_path}</p>
        </div>
        <div class="flex flex-col gap-1 shrink-0">
          <select
            bind:value={item.category}
            class="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300"
          >
            {#each categories as cat}
              <option value={cat.id}>{cat.label}</option>
            {/each}
          </select>
          <input
            bind:value={item.subfolder}
            class="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-400 w-28"
            placeholder="subfolder"
            title="Subfolder within category (optional)"
          />
        </div>
        <span class="text-xs text-gray-500 shrink-0 w-16 text-right">{formatSize(item.size)}</span>
      </div>
    {/each}
  </div>
</div>
