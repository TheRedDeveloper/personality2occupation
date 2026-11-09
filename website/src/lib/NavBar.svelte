<script lang="ts">
  import { resolve, asset } from '$app/paths';
  import { mdiArrowRight } from '#lib/icons.ts';
</script>

<nav class="navbar">
  <div class="nav-container">
    <a href={resolve('/')} class="brand-link" aria-label="personality2occupation">
      <img src={asset('logo.svg')} alt="p2o" class="brand-logo" width="32" height="32" />
    </a>

    <div class="nav-actions">
      <a href={resolve('/test')} class="btn-test">
        <span>Test</span>
        <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
          <path fill="currentColor" d={mdiArrowRight} />
        </svg>
      </a>
    </div>
  </div>
</nav>

<style>
  .navbar {
    position: sticky;
    top: 0;
    z-index: 100;
    width: 100%;
    background: #000000;
  }

  .nav-container {
    max-width: 1360px;
    margin: 0 auto;
    padding: 0.75rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .brand-link {
    display: flex;
    align-items: center;
    text-decoration: none;
    color: #ffffff;
  }

  .brand-logo {
    display: block;
    width: 32px;
    height: 32px;
  }

  .btn-test {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: #ffffff;
    background: #171717;
    border: 1px solid #333333;
    font-size: 0.9rem;
    font-weight: 500;
    padding: 0.4rem 0.85rem;
    border-radius: 6px;
    text-decoration: none;
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .btn-test:hover {
    background: #262626;
    border-color: #555555;
  }

  .icon {
    width: 16px;
    height: 16px;
    display: block;
  }
</style>
