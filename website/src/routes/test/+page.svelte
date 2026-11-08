<script lang="ts">
  import { resolve } from '$app/paths';
</script>

<svelte:head>
  <title>Career Personality Test | Personality to Occupation</title>
  <meta
    name="description"
    content="Take our free interactive career personality test to discover occupations aligned with your traits."
  />
</svelte:head>

<main>
  <nav>
    <a href={resolve('/')}>← Back to Home</a>
  </nav>

  <h1>Career Personality Test</h1>
  <p>Interactive questionnaire backbone ready for implementation.</p>
</main>

<style>
  main {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
  }

  nav {
    margin-bottom: 2rem;
  }

  nav a {
    color: #3b82f6;
    text-decoration: none;
  }

  nav a:hover {
    text-decoration: underline;
  }
</style>
