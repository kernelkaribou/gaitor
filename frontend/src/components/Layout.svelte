<script>
  import ToastContainer from './ToastContainer.svelte';

  let { children: content, currentPage = $bindable('library') } = $props();
</script>

<div class="min-h-screen bg-gray-900 text-gray-100">
  <!-- Header -->
  <header class="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-2xl">&#x1F40A;</span>
      <h1 class="text-xl font-bold text-green-400">gAItor</h1>
    </div>
    <nav class="flex items-center gap-4">
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors {currentPage === 'library' ? 'bg-gray-700 text-gray-200' : 'hover:bg-gray-700 text-gray-400'}"
        onclick={() => currentPage = 'library'}
      >
        Library
      </button>
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors {currentPage === 'targets' ? 'bg-gray-700 text-gray-200' : 'hover:bg-gray-700 text-gray-400'}"
        onclick={() => currentPage = 'targets'}
      >
        Targets
      </button>
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors {currentPage === 'download' ? 'bg-gray-700 text-gray-200' : 'hover:bg-gray-700 text-gray-400'}"
        onclick={() => currentPage = 'download'}
      >
        Download
      </button>
      <div class="w-px h-6 bg-gray-600"></div>
      <button
        class="p-1.5 rounded-md transition-colors {currentPage === 'settings' ? 'bg-gray-700 text-gray-200' : 'hover:bg-gray-700 text-gray-400'}"
        title="Settings"
        aria-label="Settings"
        onclick={() => currentPage = 'settings'}
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    </nav>
  </header>

  <!-- Main content -->
  <main class="p-6">
    {@render content()}
  </main>

  <ToastContainer />
</div>
