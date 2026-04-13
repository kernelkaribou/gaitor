<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { formatSize } from '../lib/utils.js';

  let version = $state(null);
  let disk = $state(null);
  let auth = $state(null);
  let stats = $state(null);
  let loading = $state(true);

  function usagePercent(total, free) {
    if (!total) return 0;
    return Math.round(((total - free) / total) * 100);
  }

  function usageColor(percent) {
    if (percent > 90) return 'bg-red-500';
    if (percent > 75) return 'bg-yellow-500';
    return 'bg-green-500';
  }

  const PIE_COLORS = [
    '#22c55e', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444',
    '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
    '#14b8a6', '#e879f9', '#facc15', '#fb923c', '#818cf8',
  ];

  const OTHER_THRESHOLD = 2; // categories below this % are grouped into "Other"

  function buildPieSlices(byCategory) {
    if (!byCategory) return [];
    const entries = Object.entries(byCategory)
      .map(([cat, data]) => ({ cat, size: data.size, count: data.count }))
      .filter(e => e.size > 0)
      .sort((a, b) => b.size - a.size);

    const total = entries.reduce((s, e) => s + e.size, 0);
    if (total === 0) return [];

    const major = [];
    let otherSize = 0;
    let otherCount = 0;
    let otherNames = [];

    for (const e of entries) {
      const pct = (e.size / total) * 100;
      if (pct >= OTHER_THRESHOLD || major.length < 8) {
        major.push(e);
      } else {
        otherSize += e.size;
        otherCount += e.count;
        otherNames.push(e.cat);
      }
    }

    if (otherSize > 0) {
      major.push({ cat: `Other (${otherNames.length})`, size: otherSize, count: otherCount });
    }

    let cumulative = 0;
    return major.map((e, i) => {
      const startAngle = (cumulative / total) * 360;
      const sliceAngle = (e.size / total) * 360;
      cumulative += e.size;
      return {
        ...e,
        percent: ((e.size / total) * 100).toFixed(1),
        color: PIE_COLORS[i % PIE_COLORS.length],
        startAngle,
        sliceAngle,
      };
    });
  }

  function describeArc(cx, cy, r, startAngle, endAngle) {
    const start = polarToCartesian(cx, cy, r, endAngle);
    const end = polarToCartesian(cx, cy, r, startAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
  }

  function polarToCartesian(cx, cy, r, angleDeg) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  onMount(async () => {
    try {
      const [v, d, a, s] = await Promise.all([
        api.getVersion(),
        api.getDiskUsage(),
        api.getAuthStatus(),
        api.getModelStats().catch(() => null),
      ]);
      version = v;
      disk = d;
      auth = a;
      stats = s;
    } catch (err) {
      console.error(err);
    }
    loading = false;
  });

  let pieSlices = $derived(buildPieSlices(stats?.by_category));
</script>

<div class="max-w-3xl mx-auto">
  <h2 class="text-lg font-semibold text-gray-200 mb-6">Settings</h2>

  {#if loading}
    <div class="text-center py-10 text-gray-500">Loading...</div>
  {:else}

    <!-- Storage -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Storage</h3>
      <div class="space-y-3">
        {#if disk?.library}
          {@const pct = usagePercent(disk.library.total, disk.library.free)}
          <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-gray-200 font-medium">Library</span>
              <span class="text-xs text-gray-500 font-mono">{disk.library.path}</span>
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
                <span class="text-gray-200 font-medium">{name}</span>
                <span class="text-xs text-gray-500 font-mono">{info.path}</span>
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

    <!-- Category Breakdown Pie Chart -->
    {#if stats && pieSlices.length > 0}
      <section class="mb-8">
        <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Model Breakdown</h3>
        <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <div class="flex items-center justify-between mb-3 text-sm text-gray-400">
            <span>{stats.total_models} models</span>
            <span>{formatSize(stats.total_size)} total</span>
          </div>
          <div class="flex items-start gap-6">
            <!-- Pie chart (SVG) -->
            <div class="shrink-0">
              <svg width="160" height="160" viewBox="0 0 160 160">
                {#if pieSlices.length === 1}
                  <circle cx="80" cy="80" r="70" fill={pieSlices[0].color} />
                {:else}
                  {#each pieSlices as slice}
                    <path
                      d={describeArc(80, 80, 70, slice.startAngle, slice.startAngle + slice.sliceAngle)}
                      fill={slice.color}
                      stroke="#1f2937"
                      stroke-width="1"
                    />
                  {/each}
                {/if}
              </svg>
            </div>
            <!-- Legend -->
            <div class="flex-1 min-w-0 space-y-1.5 max-h-[160px] overflow-y-auto">
              {#each pieSlices as slice}
                <div class="flex items-center gap-2 text-xs">
                  <span class="w-2.5 h-2.5 rounded-sm shrink-0" style="background: {slice.color}"></span>
                  <span class="text-gray-300 truncate flex-1">{slice.cat}</span>
                  <span class="text-gray-500 shrink-0">{slice.count}</span>
                  <span class="text-gray-400 shrink-0 w-16 text-right">{formatSize(slice.size)}</span>
                  <span class="text-gray-600 shrink-0 w-10 text-right">{slice.percent}%</span>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </section>
    {/if}

    <!-- Auth Tokens -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">API Authentication</h3>
      <div class="bg-gray-800 rounded-lg border border-gray-700 divide-y divide-gray-700">
        <div class="p-4 flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">Hugging Face</span>
            {#if auth?.huggingface?.configured}
              <p class="text-xs text-gray-500 mt-0.5 font-mono tracking-widest">{'*'.repeat(20)}</p>
            {:else}
              <p class="text-xs text-gray-500 mt-0.5">Not configured</p>
            {/if}
          </div>
          <span class="text-xs px-2 py-1 rounded-full {auth?.huggingface?.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-700 text-gray-500'}">
            {auth?.huggingface?.configured ? 'Configured' : 'Not set'}
          </span>
        </div>
        <div class="p-4 flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">CivitAI</span>
            {#if auth?.civitai?.configured}
              <p class="text-xs text-gray-500 mt-0.5 font-mono tracking-widest">{'*'.repeat(20)}</p>
            {:else}
              <p class="text-xs text-gray-500 mt-0.5">Not configured</p>
            {/if}
          </div>
          <span class="text-xs px-2 py-1 rounded-full {auth?.civitai?.configured ? 'bg-green-900/40 text-green-400' : 'bg-gray-700 text-gray-500'}">
            {auth?.civitai?.configured ? 'Configured' : 'Not set'}
          </span>
        </div>
      </div>
    </section>

    <!-- Metadata Export -->
    <section class="mb-8">
      <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Backup</h3>
      <div class="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-gray-200 font-medium">Export Library Metadata</span>
            <p class="text-xs text-gray-500 mt-0.5">Download all model metadata, categories, and settings as a JSON file</p>
          </div>
          <a
            href={api.getExportUrl()}
            download="gaitor-export.json"
            class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
          >
            Export JSON
          </a>
        </div>
      </div>
    </section>

    <!-- Version (at bottom) -->
    <section class="mb-8 pt-4 border-t border-gray-700">
      <div class="flex items-center justify-between text-sm">
        <div>
          <span class="text-gray-400">gAItor</span>
          <span class="text-gray-600 ml-1">v{version?.version || '?'}</span>
        </div>
        {#if version?.update_available}
          <a
            href={version.release_url}
            target="_blank"
            rel="noopener noreferrer"
            class="text-green-400 hover:text-green-300 text-xs"
          >
            v{version.latest} available
          </a>
        {:else}
          <span class="text-xs text-gray-600">Up to date</span>
        {/if}
      </div>
    </section>

  {/if}
</div>
