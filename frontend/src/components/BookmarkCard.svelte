<script>
  import { api } from '../lib/api.js';
  import defaultThumb from '../assets/default-thumb.webp';

  let { bookmark, onSelect } = $props();

  const thumbUrl = $derived(
    bookmark.thumbnail ? api.getBookmarkThumbnailUrl(bookmark.id) :
    bookmark.thumbnail_url ? bookmark.thumbnail_url : null
  );

  const providerLabel = $derived.by(() => {
    const url = bookmark.source?.url?.toLowerCase() || '';
    if (url.includes('huggingface.co') || url.includes('hf.co')) return 'HF';
    if (url.includes('civitai.com')) return 'Civit';
    if (url) return null;
    return null;
  });
</script>

<button
  class="bg-gray-800 rounded-lg border border-gray-700 hover:border-amber-600/50 transition-colors cursor-pointer text-left w-full overflow-hidden"
  onclick={onSelect}
>
  {#if thumbUrl}
    <div class="w-full h-40 bg-gray-900 flex items-center justify-center">
      <img src={thumbUrl} alt={bookmark.name} class="max-w-full max-h-40 object-contain" />
    </div>
  {:else}
    <div class="w-full h-40 bg-gray-900/50 flex items-center justify-center">
      <img src={defaultThumb} alt={bookmark.name} class="max-w-full max-h-40 object-contain opacity-30" />
    </div>
  {/if}
  <div class="p-4">
    <div class="flex items-start justify-between mb-2">
      <h3 class="font-medium text-gray-100 truncate text-sm">{bookmark.name}</h3>
    </div>
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      {#if providerLabel}
        <span class="text-xs font-medium px-2 py-0.5 rounded bg-amber-900/40 text-amber-400 border border-amber-700/40">
          {providerLabel}
        </span>
      {/if}
      {#if bookmark.base_model}
        <span class="text-xs font-medium px-2 py-0.5 rounded bg-purple-900/40 text-purple-400 border border-purple-700/40">
          {bookmark.base_model}
        </span>
      {/if}
      {#if bookmark.target_category}
        <span class="text-xs font-medium px-2 py-0.5 rounded bg-green-900/40 text-green-400 border border-green-700/40">
          {bookmark.target_category}
        </span>
      {/if}
    </div>
    {#if bookmark.description}
      <p class="text-xs text-gray-500 truncate mb-3">{bookmark.description}</p>
    {:else if bookmark.notes}
      <p class="text-xs text-gray-500 truncate mb-3">{bookmark.notes}</p>
    {/if}
    <div class="flex items-center justify-between text-xs text-gray-500">
      <div class="flex items-center gap-1.5 flex-wrap">
        {#each bookmark.tags.slice(0, 3) as tag}
          <span class="px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 text-[10px]">{tag}</span>
        {/each}
        {#if bookmark.tags.length > 3}
          <span class="text-gray-600 text-[10px]">+{bookmark.tags.length - 3}</span>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        {#if bookmark.source?.url}
          <svg class="w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <title>Has source URL</title>
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
        {/if}
      </div>
    </div>
  </div>
</button>
