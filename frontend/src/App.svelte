<script>
  import Layout from './components/Layout.svelte';
  import Library from './pages/Library.svelte';
  import Hosts from './pages/Hosts.svelte';
  import AddModel from './pages/AddModel.svelte';
  import Settings from './pages/Settings.svelte';
  import UpdateBanner from './components/UpdateBanner.svelte';

  let currentPage = $state('library');
</script>

<Layout bind:currentPage>
  <UpdateBanner />
  {#if currentPage === 'library'}
    <Library onNavigate={(page) => currentPage = page} />
  {:else if currentPage === 'hosts'}
    <Hosts onBack={() => currentPage = 'library'} />
  {:else if currentPage === 'add'}
    <AddModel onBack={() => currentPage = 'library'} />
  {:else if currentPage === 'settings'}
    <Settings />
  {/if}
</Layout>
