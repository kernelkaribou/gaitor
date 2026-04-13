<script>
  let { model, formatSize, onSelect } = $props();

  const extBadge = $derived(model.filename?.split('.').pop()?.toUpperCase() || '');
</script>

<button
  class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-green-600/50 transition-colors cursor-pointer text-left w-full"
  onclick={onSelect}
>
  <div class="flex items-start justify-between mb-2">
    <h3 class="font-medium text-gray-100 truncate text-sm">{model.name}</h3>
    <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 shrink-0 ml-2">
      {model.category}
    </span>
  </div>
  <p class="text-xs text-gray-500 truncate mb-3">{model.filename}</p>
  <div class="flex items-center justify-between text-xs text-gray-500">
    <span>{formatSize(model.size)}</span>
    <div class="flex items-center gap-2">
      {#if model.hash?.sha256}
        <span class="text-green-500" title="Hash verified">✓</span>
      {/if}
      {#if extBadge}
        <span class="px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 font-mono text-[10px]">{extBadge}</span>
      {/if}
    </div>
  </div>
</button>
