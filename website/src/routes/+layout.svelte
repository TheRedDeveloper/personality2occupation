<script lang="ts">
  import '../app.css';
  import NavBar from '#lib/NavBar.svelte';

  let { children } = $props();
</script>

<div class="layout">
  <NavBar />
  <div class="page-content">
    {@render children()}
  </div>
</div>

<style>
  .layout {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .page-content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
