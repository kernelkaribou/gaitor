<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { updateInfo } from '../lib/stores.js';

  onMount(async () => {
    try {
      const data = await api.getVersion();
      if (data.update_available) {
        updateInfo.set({ latest: data.latest, release_url: data.release_url });
      }
    } catch {
      // Version check is best-effort
    }
  });

  let info = $state(null);
  const unsubUpdate = updateInfo.subscribe((v) => (info = v));
  onDestroy(unsubUpdate);
</script>

{#if info}
  <div class="bg-green-900/50 border border-green-700 rounded-lg px-4 py-2 mb-4 flex items-center justify-between">
    <span class="text-green-300 text-sm">
      🐊 gAItor <strong>v{info.latest}</strong> is available!
    </span>
    {#if info.release_url}
      <a
        href={info.release_url}
        target="_blank"
        rel="noopener noreferrer"
        class="text-sm text-green-400 hover:text-green-300 underline"
      >
        View release →
      </a>
    {/if}
  </div>
{/if}
