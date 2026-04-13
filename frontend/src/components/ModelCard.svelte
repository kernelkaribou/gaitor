<script>
  let { model } = $props();
</script>

<div class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-500 transition-colors cursor-pointer">
  <div class="flex items-start justify-between mb-2">
    <h3 class="font-medium text-gray-100 truncate">{model.name}</h3>
    <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 shrink-0 ml-2">
      {model.category}
    </span>
  </div>
  <p class="text-sm text-gray-400 truncate">{model.filename}</p>
  <div class="flex items-center justify-between mt-3 text-xs text-gray-500">
    <span>{model.size_display || '—'}</span>
    <span>{model.format || ''}</span>
  </div>
</div>
