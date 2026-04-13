<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';

  let version = $state(null);
  let disk = $state(null);
  let auth = $state(null);
  let loading = $state(true);

  function formatSize(bytes) {
    if (!bytes) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return `${size.toFixed(1)} ${units[i]}`;
  }

  function usagePercent(total, free) {
    if (!total) return 0;
    return Math.round(((total - free) / total) * 100);
  }

  function usageColor(percent) {
    if (percent > 90) return 'bg-red-500';
    if (percent > 75) return 'bg-yellow-500';
    return 'bg-green-500';
  }

  onMount(async () => {
    try {
      const [v, d, a] = await Promise.all([
        api.getVersion(),
        api.getDiskUsage(),
        api.getAuthStatus(),
      ]);
      version = v;
      disk = d;
      auth = a;
    } catch (err) {
      console.error(err);
    }
    loading = false;
  });
</script>

<div class="max-w-3xl mx-auto">
  <h2 class="text-lg font-semibold text-gray-200 mb-6">Settings</h2>

  {#if loading}
    <div class="text-center py-10 text-gray-500">Loading...</div>
  {:else}

    <!-- Version -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Version</h3>
      <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">Model gAItor</span>
            <span class="text-gray-500 ml-2">v{version?.version || '?'}</span>
          </div>
          {#if version?.update_available}
            <a
              href={version.release_url}
              target="_blank"
              rel="noopener"
              class="text-sm text-green-400 hover:text-green-300"
            >
              v{version.latest} available →
            </a>
          {:else}
            <span class="text-xs text-gray-500">Up to date</span>
          {/if}
        </div>
      </div>
    </section>

    <!-- Disk Space -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Storage</h3>
      <div class="space-y-3">
        {#if disk?.library}
          {@const pct = usagePercent(disk.library.total, disk.library.free)}
          <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-gray-200 font-medium">📚 Library</span>
              <span class="text-xs text-gray-500">{disk.library.path}</span>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
              <div class="{usageColor(pct)} h-2 rounded-full" style="width: {pct}%"></div>
            </div>
            <div class="flex justify-between text-xs text-gray-500">
              <span>{formatSize(disk.library.used)} used</span>
              <span>{formatSize(disk.library.free)} free of {formatSize(disk.library.total)}</span>
            </div>
          </div>
        {/if}
        {#if disk?.destinations}
          {#each Object.entries(disk.destinations) as [name, info]}
            {@const pct = usagePercent(info.total, info.free)}
            <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-gray-200 font-medium">📡 {name}</span>
                <span class="text-xs text-gray-500">{info.path}</span>
              </div>
              <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
                <div class="{usageColor(pct)} h-2 rounded-full" style="width: {pct}%"></div>
              </div>
              <div class="flex justify-between text-xs text-gray-500">
                <span>{formatSize(info.used)} used</span>
                <span>{formatSize(info.free)} free of {formatSize(info.total)}</span>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    </section>

    <!-- Auth Tokens -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">API Authentication</h3>
      <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
        <div class="p-4 flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">🤗 Hugging Face</span>
            <p class="text-xs text-gray-500 mt-0.5">Set via <code class="bg-gray-700 px-1 rounded">HUGGINGFACE_TOKEN</code> env var</p>
          </div>
          <span class="text-xs px-2 py-1 rounded-full {auth?.huggingface?.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-700 text-gray-500'}">
            {auth?.huggingface?.configured ? '✓ Configured' : '○ Not set'}
          </span>
        </div>
        <div class="p-4 flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">🎨 CivitAI</span>
            <p class="text-xs text-gray-500 mt-0.5">Set via <code class="bg-gray-700 px-1 rounded">CIVITAI_API_KEY</code> env var</p>
          </div>
          <span class="text-xs px-2 py-1 rounded-full {auth?.civitai?.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-700 text-gray-500'}">
            {auth?.civitai?.configured ? '✓ Configured' : '○ Not set'}
          </span>
        </div>
      </div>
    </section>

    <!-- Paths -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Configuration</h3>
      <div class="bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-400">Library Path</span>
          <span class="text-gray-300 font-mono text-xs">{disk?.library?.path || '/library'}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">Destinations Root</span>
          <span class="text-gray-300 font-mono text-xs">/dest/</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">Port</span>
          <span class="text-gray-300 font-mono text-xs">8487</span>
        </div>
      </div>
    </section>

  {/if}
</div>
