<script>
  import { onMount, onDestroy } from 'svelte';

  let { title, message, warningText, confirmValue, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel } = $props();

  function handleKeydown(e) {
    if (e.key === 'Escape' && !confirming) onCancel();
  }
  onMount(() => document.addEventListener('keydown', handleKeydown));
  onDestroy(() => document.removeEventListener('keydown', handleKeydown));

  let inputValue = $state('');
  let error = $state(null);
  let confirming = $state(false);

  let isMatch = $derived(inputValue === confirmValue);

  async function handleConfirm() {
    if (!isMatch) return;
    confirming = true;
    error = null;
    try {
      await onConfirm(inputValue);
    } catch (err) {
      error = err.message;
      confirming = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="fixed inset-0 bg-black/60 z-50" onclick={() => !confirming && onCancel()}></div>

<!-- Dialog -->
<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
  <div class="bg-gray-800 rounded-lg border {danger ? 'border-red-700' : 'border-gray-700'} w-full max-w-sm shadow-xl">
    <div class="p-6">
      <h2 class="text-lg font-semibold {danger ? 'text-red-400' : 'text-gray-100'} mb-2">{title}</h2>
      <p class="text-sm text-gray-400 mb-4">{message}</p>

      {#if error}
        <div class="bg-red-900/30 border border-red-700 rounded-md px-3 py-2 mb-3 text-red-300 text-sm">{error}</div>
      {/if}

      {#if warningText}
        <p class="text-sm text-gray-300 mb-2">{warningText}</p>
        <p class="text-xs text-gray-500 mb-2 font-mono bg-gray-900 px-2 py-1 rounded">{confirmValue}</p>
        <input
          bind:value={inputValue}
          placeholder="Type to confirm..."
          class="w-full bg-gray-900 border {danger ? 'border-red-700/50 focus:border-red-500' : 'border-gray-600 focus:border-green-500'} rounded px-3 py-2 text-sm text-gray-200 focus:outline-none mb-4"
        />
      {/if}

      <div class="flex gap-2 justify-end">
        <button class="px-4 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 text-gray-200 disabled:opacity-50" onclick={onCancel} disabled={confirming}>Cancel</button>
        <button
          class="px-4 py-2 text-sm rounded {danger ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600 hover:bg-green-500'} text-white disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleConfirm}
          disabled={confirming || (warningText && !isMatch)}
        >
          {confirming ? 'Processing...' : confirmLabel}
        </button>
      </div>
    </div>
  </div>
</div>
