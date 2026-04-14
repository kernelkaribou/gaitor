<script>
  import Layout from './components/Layout.svelte';
  import Library from './pages/Library.svelte';
  import Hosts from './pages/Hosts.svelte';
  import AddModel from './pages/AddModel.svelte';
  import Settings from './pages/Settings.svelte';
  import UpdateBanner from './components/UpdateBanner.svelte';
  import { onMount, onDestroy } from 'svelte';

  const validPages = ['library', 'hosts', 'add', 'settings'];

  function pageFromHash() {
    const hash = location.hash.replace('#', '');
    return validPages.includes(hash) ? hash : 'library';
  }

  let currentPage = $state(pageFromHash());

  function navigate(page) {
    if (!validPages.includes(page)) page = 'library';
    currentPage = page;
    const target = '#' + page;
    if (location.hash !== target) {
      history.pushState(null, '', target);
    }
  }

  function onHashChange() {
    currentPage = pageFromHash();
  }

  onMount(() => {
    window.addEventListener('hashchange', onHashChange);
    if (!location.hash) history.replaceState(null, '', '#library');
  });
  onDestroy(() => {
    window.removeEventListener('hashchange', onHashChange);
  });
</script>

<Layout {currentPage} {navigate}>
  <UpdateBanner />
  {#if currentPage === 'library'}
    <Library onNavigate={navigate} />
  {:else if currentPage === 'hosts'}
    <Hosts onBack={() => navigate('library')} />
  {:else if currentPage === 'add'}
    <AddModel onBack={() => navigate('library')} />
  {:else if currentPage === 'settings'}
    <Settings />
  {/if}
</Layout>
