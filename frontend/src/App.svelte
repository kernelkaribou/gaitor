<script>
  import Layout from './components/Layout.svelte';
  import Library from './pages/Library.svelte';
  import Destination from './pages/Destination.svelte';
  import Retrieve from './pages/Retrieve.svelte';
  import Settings from './pages/Settings.svelte';
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
    <Retrieve />
  {:else if currentPage === 'settings'}
    <Settings />
  {/if}
</Layout>
