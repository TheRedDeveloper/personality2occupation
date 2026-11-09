<script lang="ts">
  import { resolve } from '$app/paths';
</script>

<svelte:head>
  <title>Free Career Personality Test | personality2occupation (p2o)</title>
  <meta
    name="description"
    content="Take our free interactive career personality test to discover occupations empirically aligned with your Big Five traits and Schwartz values."
  />
  <link rel="canonical" href="https://thereddeveloper.github.io/personality2occupation/test" />

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://thereddeveloper.github.io/personality2occupation/test" />
  <meta property="og:title" content="Free Career Personality Test | personality2occupation (p2o)" />
  <meta
    property="og:description"
    content="Take our free interactive career personality test to discover occupations empirically aligned with your Big Five traits and Schwartz values."
  />
  <meta property="og:image" content="https://thereddeveloper.github.io/personality2occupation/og-image.png" />
  <meta property="og:site_name" content="personality2occupation" />
  <meta property="og:locale" content="en_US" />

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:url" content="https://thereddeveloper.github.io/personality2occupation/test" />
  <meta name="twitter:title" content="Free Career Personality Test | personality2occupation (p2o)" />
  <meta
    name="twitter:description"
    content="Take our free interactive career personality test to discover occupations empirically aligned with your Big Five traits and Schwartz values."
  />
  <meta name="twitter:image" content="https://thereddeveloper.github.io/personality2occupation/og-image.png" />
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
