<script lang="ts">
  import { resolve, asset } from '$app/paths';
  import { page } from '$app/state';
  import { testEngine } from '#lib/testEngine.svelte.ts';
  import Modal from '#lib/Modal.svelte';
  import { mdiArrowRight } from '#lib/icons.ts';

  const isTestPage = $derived(page.url.pathname.includes('/test'));
  const mdiShareVariant = 'M18,16.08C17.24,16.08 16.56,16.38 16.04,16.85L8.91,12.7C8.96,12.47 9,12.24 9,12C9,11.76 8.96,11.53 8.91,11.3L15.96,7.19C16.5,7.69 17.21,8 18,8A3,3 0 0,0 21,5A3,3 0 0,0 18,2A3,3 0 0,0 15,5C15,5.24 15.04,5.47 15.09,5.7L8.04,9.81C7.5,9.31 6.79,9 6,9A3,3 0 0,0 3,12A3,3 0 0,0 6,15C6.79,15 7.5,14.69 8.04,14.19L15.16,18.34C15.11,18.55 15.08,18.77 15.08,19C15.08,20.61 16.39,21.91 18,21.91C19.61,21.91 20.92,20.61 20.92,19A2.92,2.92 0 0,0 18,16.08Z';
  const mdiPlay = 'M8,5.14V19.14L19,12.14L8,5.14Z';
</script>

<nav class="navbar">
  <div class="nav-container">
    <!-- Left-aligned group: Logo + Badges -->
    <div class="nav-left">
      <a href={resolve('/')} class="brand-link" aria-label="personality2occupation">
        <img src={asset('logo.svg')} alt="p2o" class="brand-logo" width="32" height="32" />
      </a>

      {#if isTestPage && testEngine.isLoaded}
        {#if testEngine.isViewingSharedResult}
          <span class="shared-badge">
            <svg viewBox="0 0 24 24" class="shared-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiShareVariant} />
            </svg>
            <span>{testEngine.answeredCount} Answers</span>
          </span>
          <div class="convergence-badge" title="Bayesian psychometric parameter convergence">
            <span class="convergence-label">Convergence</span>
            <span class="convergence-val">{testEngine.confidence}%</span>
          </div>
        {:else}
          <span class="q-badge">Question {testEngine.answeredCount + 1}</span>
          <div class="convergence-badge" title="Bayesian psychometric parameter convergence">
            <span class="convergence-label">Convergence</span>
            <span class="convergence-val">{testEngine.confidence}%</span>
          </div>
        {/if}
      {/if}
    </div>

    <!-- Right-aligned group: Action buttons -->
    <div class="nav-right">
      {#if isTestPage && testEngine.isLoaded}
        {#if testEngine.isViewingSharedResult}
          <!-- On a shared result: show Continue button in place of undo/redo/reset -->
          <button
            type="button"
            class="nav-btn-continue"
            onclick={() => testEngine.handleContinueShared()}
            title="Continue testing from this psychometric result"
          >
            <svg viewBox="0 0 24 24" class="nav-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiPlay} />
            </svg>
            <span>Continue</span>
          </button>
        {:else}
          <button
            type="button"
            class="nav-action-btn"
            onclick={() => testEngine.undo()}
            disabled={!testEngine.canUndo}
            title="Undo last response (Backspace or Ctrl+Z)"
          >
            <svg viewBox="0 0 24 24" class="nav-icon" aria-hidden="true">
              <path fill="currentColor" d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z" />
            </svg>
            <span class="action-label">Undo</span>
          </button>

          <button
            type="button"
            class="nav-action-btn"
            onclick={() => testEngine.redo()}
            disabled={!testEngine.canRedo}
            title="Redo response (Ctrl+Y or Ctrl+Shift+Z)"
          >
            <svg viewBox="0 0 24 24" class="nav-icon" aria-hidden="true">
              <path fill="currentColor" d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z" />
            </svg>
            <span class="action-label">Redo</span>
          </button>

          <button
            type="button"
            class="nav-action-btn btn-reset"
            onclick={() => testEngine.openResetModal()}
            disabled={testEngine.answeredCount === 0}
            title="Reset test"
          >
            <svg viewBox="0 0 24 24" class="nav-icon" aria-hidden="true">
              <path fill="currentColor" d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
            </svg>
            <span class="action-label">Reset</span>
          </button>

          <!-- Blue Share Button -->
          <button
            type="button"
            class="nav-action-btn btn-share"
            onclick={() => testEngine.openShareModal()}
            disabled={testEngine.answeredCount === 0}
            title="Share permanent result URL"
          >
            <svg viewBox="0 0 24 24" class="nav-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiShareVariant} />
            </svg>
            <span class="action-label">Share</span>
          </button>
        {/if}
      {:else if !isTestPage}
        <a href={resolve('/test')} class="btn-test">
          <span>Test</span>
          <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
            <path fill="currentColor" d={mdiArrowRight} />
          </svg>
        </a>
      {/if}
    </div>
  </div>

  {#if isTestPage && testEngine.isLoaded}
    <div class="nav-progress-track" aria-hidden="true">
      <div
        class="nav-progress-fill"
        style="width: {testEngine.confidence}%"
      ></div>
    </div>
  {/if}
</nav>

<!-- In-App Confirmation & Share Dialogs -->
<Modal />

<style>
  .navbar {
    position: sticky;
    top: 0;
    z-index: 100;
    width: 100%;
    background: #000000;
    border-bottom: 1px solid #1a1a1a;
  }

  .nav-container {
    max-width: 1360px;
    margin: 0 auto;
    padding: 0.65rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
  }

  /* Left-aligned group: Logo + Badges */
  .nav-left {
    display: flex;
    align-items: center;
    gap: 1rem;
    min-width: 0;
  }

  .brand-link {
    display: flex;
    align-items: center;
    text-decoration: none;
    color: #ffffff;
    flex-shrink: 0;
  }

  .brand-logo {
    display: block;
    width: 32px;
    height: 32px;
  }

  .q-badge {
    font-size: 0.85rem;
    font-weight: 600;
    color: #ffffff;
    background-color: #171717;
    border: 1px solid #2d2d2d;
    padding: 0.22rem 0.65rem;
    border-radius: 4px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .shared-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #60a5fa;
    background-color: #0f172a;
    border: 1px solid #1e3a5f;
    padding: 0.22rem 0.65rem;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .shared-icon {
    width: 13px;
    height: 13px;
    display: block;
  }

  .convergence-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    color: #888888;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .convergence-val {
    font-weight: 600;
    color: #10b981;
    font-variant-numeric: tabular-nums;
  }

  /* Right-aligned group: Action Buttons */
  .nav-right {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-left: auto;
    flex-shrink: 0;
  }

  .nav-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: #0e0e0e;
    border: 1px solid #242424;
    color: #cccccc;
    padding: 0.32rem 0.65rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .nav-action-btn:hover:not(:disabled) {
    background-color: #1a1a1a;
    border-color: #444444;
    color: #ffffff;
  }

  .nav-action-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Blue Share Button */
  .btn-share {
    background: #0b1526;
    border-color: #1d3356;
    color: #60a5fa;
  }

  .btn-share:hover:not(:disabled) {
    background-color: #1d4ed8;
    border-color: #3b82f6;
    color: #ffffff;
  }

  /* Continue button for shared result */
  .nav-btn-continue {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #ffffff;
    border: 1px solid #ffffff;
    color: #000000;
    padding: 0.35rem 0.85rem;
    border-radius: 4px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .nav-btn-continue:hover {
    background: #e2e8f0;
    border-color: #e2e8f0;
    transform: translateY(-1px);
  }

  .nav-icon {
    width: 14px;
    height: 14px;
    display: block;
  }

  /* Progress Hairline */
  .nav-progress-track {
    width: 100%;
    height: 2px;
    background-color: #111111;
    overflow: hidden;
  }

  .nav-progress-fill {
    height: 100%;
    background-color: #10b981;
    transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Homepage Test Button */
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

  @media (max-width: 680px) {
    .nav-container {
      padding: 0.5rem 1rem;
      gap: 0.75rem;
    }

    .nav-left {
      gap: 0.6rem;
    }

    .convergence-label {
      display: none;
    }

    .action-label {
      display: none;
    }

    .nav-action-btn {
      padding: 0.35rem 0.5rem;
    }
  }
</style>
