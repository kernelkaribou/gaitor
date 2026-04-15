<script>
  import { formatSize } from '../lib/utils.js';

  let { results, categories, onLink, onBulkLink, onImport, onIgnore, onDelete, onDismiss, linking = {} } = $props();

  let items = $state(
    (results.unmanaged || []).map((u) => ({
      ...u,
      importName: u.filename.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '),
      importCategory: u.guessed_category || 'other',
      showImport: false,
      confirmIgnore: false,
      confirmDelete: false,
    }))
  );

  let matchedCount = $derived(items.filter(i => i.match).length);
  let highConfidenceCount = $derived(items.filter(i => i.match?.confidence === 'high').length);
  let unmatchedCount = $derived(items.filter(i => !i.match).length);
  let totalCount = $derived(items.length);

  function removeItem(item) {
    items = items.filter(i => i.relative_path !== item.relative_path);
  }

  async function handleLink(relativePath, libraryModelId) {
    const ok = await onLink(relativePath, libraryModelId);
    if (ok) {
      items = items.filter(i => i.relative_path !== relativePath);
    }
  }

  async function handleBulkLink() {
    const linked = await onBulkLink();
    if (linked > 0) {
      items = items.filter(i => !(i.match && i.match.confidence === 'high'));
    }
  }

  async function handleImport(item, name, category) {
    const ok = await onImport(item, name, category);
    if (ok) removeItem(item);
  }

  async function handleIgnore(item) {
    const ok = await onIgnore(item);
    if (ok) removeItem(item);
  }

  async function handleDelete(item) {
    const ok = await onDelete(item);
    if (ok) removeItem(item);
  }
</script>

<div class="bg-gray-800 border border-yellow-700/50 rounded-lg">
  <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-sm font-medium text-gray-200">
        {totalCount} unmanaged model{totalCount !== 1 ? 's' : ''}{totalCount < results.count ? ` (${results.count - totalCount} resolved)` : ''}
      </span>
      {#if results.already_managed > 0}
        <span class="text-xs text-gray-500">{results.already_managed} already managed</span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      {#if highConfidenceCount > 0}
        <button
          class="px-3 py-1 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
          onclick={handleBulkLink}
          disabled={linking._bulk}
        >
          {linking._bulk ? 'Linking...' : `Link All Matched (${highConfidenceCount})`}
        </button>
      {/if}
      <button class="text-gray-400 hover:text-gray-200 text-sm" onclick={onDismiss}>&#x2715;</button>
    </div>
  </div>

  <!-- Summary -->
  <div class="px-4 py-2 border-b border-gray-700 flex gap-4 text-xs">
    {#if matchedCount > 0}
      <span class="text-green-400">{matchedCount} matched to library</span>
    {/if}
    {#if unmatchedCount > 0}
      <span class="text-yellow-400">{unmatchedCount} not in library</span>
    {/if}
  </div>

  <div class="divide-y divide-gray-700 max-h-[80vh] overflow-y-auto">
    {#each items as item, idx}
      <div class="px-4 py-3">
        <div class="flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-200 font-medium truncate">{item.filename}</p>
            <p class="text-xs text-gray-500 font-mono truncate">{item.relative_path}</p>
          </div>
          <span class="text-xs text-gray-500 shrink-0">{formatSize(item.size)}</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400 shrink-0">{item.guessed_category}</span>

          {#if item.match}
            <!-- Matched: show match info and Link button -->
            <div class="flex items-center gap-2 shrink-0">
              <div class="text-right">
                <p class="text-xs text-green-400">{item.match.library_name}</p>
                <p class="text-xs {item.match.confidence === 'high' ? 'text-green-600' : 'text-yellow-500'}">
                  {item.match.confidence === 'high' ? 'Name + size match' : 'Name match only'}
                </p>
              </div>
              <button
                class="px-3 py-1 text-xs rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
                onclick={() => handleLink(item.relative_path, item.match.library_model_id)}
                disabled={linking[item.relative_path]}
                title="Hash will be verified during linking"
              >
                {linking[item.relative_path] ? 'Linking...' : 'Link'}
              </button>
            </div>
          {:else}
            <!-- Unmatched: show Import, Ignore, Delete options -->
            <div class="flex items-center gap-2 shrink-0">
              {#if linking[item.relative_path]}
                <span class="text-xs text-blue-400">Importing...</span>
              {:else if item.showImport}
                <div class="flex items-center gap-2">
                  <input
                    bind:value={item.importName}
                    class="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 w-40 focus:outline-none focus:border-green-500"
                    placeholder="Model name"
                  />
                  <select
                    bind:value={item.importCategory}
                    class="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300"
                  >
                    {#each categories as cat}
                      <option value={cat.id}>{cat.label}</option>
                    {/each}
                  </select>
                  <button
                    class="px-3 py-1 text-xs rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
                    onclick={() => handleImport(item, item.importName, item.importCategory)}
                    disabled={!item.importName.trim()}
                  >
                    Import
                  </button>
                  <button
                    class="text-xs text-gray-500 hover:text-gray-300"
                    onclick={() => { item.showImport = false; }}
                  >Cancel</button>
                </div>
              {:else if item.confirmIgnore}
                <span class="text-xs text-yellow-400">Ignore from scans?</span>
                <button
                  class="px-3 py-1 text-xs rounded bg-yellow-700 hover:bg-yellow-600 text-white"
                  onclick={() => { handleIgnore(item); }}
                >Confirm</button>
                <button
                  class="text-xs text-gray-500 hover:text-gray-300"
                  onclick={() => { item.confirmIgnore = false; }}
                >Cancel</button>
              {:else if item.confirmDelete}
                <span class="text-xs text-red-400">Delete this file?</span>
                <button
                  class="px-3 py-1 text-xs rounded bg-red-700 hover:bg-red-600 text-white"
                  onclick={() => { handleDelete(item); }}
                >Confirm</button>
                <button
                  class="text-xs text-gray-500 hover:text-gray-300"
                  onclick={() => { item.confirmDelete = false; }}
                >Cancel</button>
              {:else}
                <button
                  class="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-300"
                  onclick={() => { item.showImport = true; }}
                >Import</button>
                <button
                  class="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-400"
                  onclick={() => { item.confirmIgnore = true; }}
                  title="Ignore model from scans"
                >Ignore</button>
                <button
                  class="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-red-900/50 text-gray-400 hover:text-red-300"
                  onclick={() => { item.confirmDelete = true; }}
                  title="Delete this file from the host"
                >Delete</button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</div>
