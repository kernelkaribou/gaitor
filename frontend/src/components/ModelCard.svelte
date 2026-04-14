<script>
  import { api } from '../lib/api.js';
  import defaultThumb from '../assets/default-thumb.webp';

  let { model, formatSize, onSelect, isDuplicate, hostMode } = $props();

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
  const thumbUrl = $derived(model.thumbnail ? api.getThumbnailUrl(model.id) : null);
</script>

<button
  class="{hostMode ? '' : 'bg-gray-800 rounded-lg border border-gray-700 hover:border-green-600/50'} transition-colors cursor-pointer text-left w-full overflow-hidden"
  onclick={onSelect}
>
  {#if thumbUrl}
    <div class="w-full h-40 bg-gray-900 flex items-center justify-center">
      <img src={thumbUrl} alt={model.name} class="max-w-full max-h-40 object-contain" />
    </div>
  {:else}
    <div class="w-full h-40 bg-gray-900/50 flex items-center justify-center">
      <img src={defaultThumb} alt={model.name} class="max-w-full max-h-40 object-contain" />
    </div>
  {/if}
  <div class="p-4">
    <div class="flex items-start justify-between mb-2">
      <h3 class="font-medium text-gray-100 truncate text-sm">{model.name}</h3>
    </div>
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <span class="text-xs font-medium px-2.5 py-1 rounded bg-green-900/40 text-green-400 border border-green-700/40">
        {model.category}
      </span>
      {#if model.base_model}
        <span class="text-xs font-medium px-2 py-0.5 rounded bg-purple-900/40 text-purple-400 border border-purple-700/40">
          {model.base_model}
        </span>
      {/if}
    </div>
    <p class="text-xs text-gray-500 truncate mb-3">{model.filename}</p>
    <div class="flex items-center justify-between text-xs text-gray-500">
      <span>{formatSize(model.size)}</span>
      <div class="flex items-center gap-2">
        {#if model.group_id}
          <span class="text-blue-400" title="Grouped with other models">&#x26D3;</span>
        {/if}
        {#if isDuplicate}
          <span class="text-yellow-500" title="Duplicate hash detected">DUP</span>
        {/if}
        {#if model.hash?.sha256}
          <span class="text-green-500" title="Hash verified">&#x2713;</span>
        {/if}
        {#if extBadge}
          <span class="px-1.5 py-0.5 rounded {extColor} font-mono text-[10px]">{extBadge}</span>
        {/if}
      </div>
    </div>
  </div>
</button>
