<script>
  let { model, formatSize, onSelect } = $props();

  const ext = $derived(model.filename?.split('.').pop()?.toLowerCase() || '');
  const extBadge = $derived(ext.toUpperCase());
  const extColor = $derived(
    ext === 'safetensors' ? 'bg-blue-900/50 text-blue-400' :
    ext === 'gguf' ? 'bg-purple-900/50 text-purple-400' :
    ext === 'ckpt' ? 'bg-yellow-900/50 text-yellow-400' :
    ext === 'bin' ? 'bg-gray-700 text-gray-400' :
    ext === 'pt' || ext === 'pth' ? 'bg-orange-900/50 text-orange-400' :
    ext === 'onnx' ? 'bg-teal-900/50 text-teal-400' :
    'bg-gray-700 text-gray-400'
  );
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
        <span class="px-1.5 py-0.5 rounded {extColor} font-mono text-[10px]">{extBadge}</span>
      {/if}
    </div>
  </div>
</button>
