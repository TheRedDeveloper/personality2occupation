<script lang="ts">
  import '../app.css';

  let { children } = $props();
</script>

<div class="layout">
  {@render children()}
</div>

<style>
  .layout {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
</style>
