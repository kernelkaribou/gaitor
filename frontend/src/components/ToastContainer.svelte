<script>
  import { toasts, removeToast } from '../lib/stores.js';
  import { formatSize } from '../lib/utils.js';
  import { onDestroy } from 'svelte';
  import { api } from '../lib/api.js';

  let toastList = $state([]);
  let cancelling = $state({});
  let confirmCancel = $state({});
  const unsubToasts = toasts.subscribe(v => toastList = v);
  onDestroy(unsubToasts);

  function formatSpeed(bytesPerSec) {
    if (!bytesPerSec || bytesPerSec <= 0) return '';
    return formatSize(bytesPerSec) + '/s';
  }

  function formatEta(seconds) {
    if (!seconds || seconds <= 0) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  }

  async function cancelTask(taskId) {
    if (!taskId || cancelling[taskId]) return;
    cancelling = { ...cancelling, [taskId]: true };
    try {
      await api.cancelTask(taskId);
    } catch (e) {
      console.error('Cancel failed:', e);
    }
    cancelling = { ...cancelling, [taskId]: false };
  }

  const typeStyles = {
    info: 'border-blue-700 bg-blue-900/80',
    success: 'border-green-700 bg-green-900/80',
    error: 'border-red-700 bg-red-900/80',
    progress: 'border-green-700 bg-gray-800',
  };
  const typeText = {
    info: 'text-blue-300',
    success: 'text-green-300',
    error: 'text-red-300',
    progress: 'text-gray-200',
  };
</script>

{#if toastList.length > 0}
  <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
    {#each toastList as toast (toast.id)}
      <div class="pointer-events-auto border rounded-lg px-4 py-3 shadow-lg {typeStyles[toast.type] || typeStyles.info} animate-slide-in">
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            {#if toast.title}
              <p class="text-sm font-medium {typeText[toast.type] || typeText.info} truncate">{toast.title}</p>
            {/if}
            {#if toast.message}
              <p class="text-xs text-gray-400 mt-0.5">{toast.message}</p>
            {/if}
            {#if toast.type === 'progress' && toast.progress !== null && toast.progress !== undefined}
              <div class="mt-2">
                <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
                  <span>{toast.progress}%</span>
                  <span>
                    {#if toast.downloaded && toast.total}
                      {formatSize(toast.downloaded)} / {formatSize(toast.total)}
                    {/if}
                    {#if toast.speed}
                      &middot; {formatSpeed(toast.speed)}
                    {/if}
                    {#if toast.eta}
                      &middot; {formatEta(toast.eta)} left
                    {/if}
                  </span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-1.5">
                  <div
                    class="bg-green-500 h-1.5 rounded-full transition-all duration-500"
                    style="width: {toast.progress}%"
                  ></div>
                </div>
              </div>
              {#if toast.taskId}
                <div class="mt-2 flex items-center gap-2">
                  {#if confirmCancel[toast.taskId]}
                    <span class="text-xs text-yellow-400">Cancel this download?</span>
                    <button
                      class="text-xs text-red-400 hover:text-red-300 font-medium disabled:opacity-50"
                      onclick={() => cancelTask(toast.taskId)}
                      disabled={cancelling[toast.taskId]}
                    >
                      {cancelling[toast.taskId] ? 'Cancelling...' : 'Yes'}
                    </button>
                    <button
                      class="text-xs text-gray-500 hover:text-gray-300"
                      onclick={() => confirmCancel = { ...confirmCancel, [toast.taskId]: false }}
                    >No</button>
                  {:else}
                    <button
                      class="text-xs text-red-400 hover:text-red-300"
                      onclick={() => confirmCancel = { ...confirmCancel, [toast.taskId]: true }}
                    >Cancel</button>
                  {/if}
                </div>
              {/if}
            {/if}
          </div>
          {#if !toast.persistent || toast.type !== 'progress'}
            <button
              class="text-gray-500 hover:text-gray-300 text-sm shrink-0"
              onclick={() => removeToast(toast.id)}
            >&#x2715;</button>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  :global(.animate-slide-in) {
    animation: slideIn 0.3s ease-out;
  }
</style>
