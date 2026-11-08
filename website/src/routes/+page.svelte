<script lang="ts">
  import { resolve } from '$app/paths';
</script>

<svelte:head>
  <title>Personality to Occupation | Free, Data-Driven Career Matching</title>
  <meta
    name="description"
    content="Discover empirical career and occupation matches based on personality trait data and statistical analysis."
  />
</svelte:head>

<main>
  <header>
    <h1>Personality to Occupation</h1>
    <p class="tagline">
      A transparent, data-driven career personality test matched against empirical occupation data.
    </p>
  </header>

  <section class="actions">
    <a href={resolve('/test')} class="btn-primary">Take Personality Test</a>
  </section>

  <section class="overview">
    <h2>Data-Driven Career Exploration</h2>
    <p>
      Explore personality distributions across occupations and visualize empirical career pathways with interactive graphs.
    </p>
  </section>
</main>

<style>
  main {
    max-width: 900px;
    margin: 0 auto;
    padding: 3rem 1.5rem;
    text-align: center;
  }

  header h1 {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
  }

  .tagline {
    font-size: 1.25rem;
    color: #4b5563;
    margin-bottom: 2rem;
  }

  .actions {
    margin: 2rem 0;
  }

  .btn-primary {
    display: inline-block;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    font-weight: 600;
    color: #ffffff;
    background-color: #3b82f6;
    border-radius: 0.5rem;
    text-decoration: none;
    transition: background-color 0.15s ease-in-out;
  }

  .btn-primary:hover {
    background-color: #2563eb;
  }

  .overview {
    margin-top: 3rem;
    text-align: left;
  }
</style>
