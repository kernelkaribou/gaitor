<script>
  import Layout from './components/Layout.svelte';
  import Library from './pages/Library.svelte';
  import Destination from './pages/Destination.svelte';
  import UpdateBanner from './components/UpdateBanner.svelte';

  let currentPage = $state('library');
</script>

<Layout bind:currentPage>
  <UpdateBanner />
  {#if currentPage === 'library'}
    <Library />
  {:else if currentPage === 'destinations'}
    <Destination onBack={() => currentPage = 'library'} />
  {:else if currentPage === 'retrieve'}
    <div class="text-center py-20">
      <span class="text-6xl mb-4 block">🌐</span>
      <h3 class="text-xl font-medium text-gray-300 mb-2">External Retrieval</h3>
      <p class="text-gray-500">Download models from Hugging Face and CivitAI — coming soon.</p>
    </div>
  {/if}
</Layout>
