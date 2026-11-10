<script lang="ts">
  import { testEngine } from '#lib/testEngine.svelte.ts';
  import { mdiClose } from '#lib/icons.ts';

  let copied = $state(false);

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape' && testEngine.modal) {
      if (testEngine.modal.onCancel) {
        testEngine.modal.onCancel();
      } else {
        testEngine.closeModal();
      }
    }
  }

  function copyShareUrl() {
    if (testEngine.modal?.shareUrl && typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(testEngine.modal.shareUrl).then(() => {
        copied = true;
        setTimeout(() => {
          testEngine.closeModal();
          copied = false;
        }, 400);
      });
    }
  }
</script>

<svelte:window onkeydown={onKeyDown} />

{#if testEngine.modal}
  <!-- Backdrop -->
  <div
    class="modal-backdrop"
    onclick={() => {
      if (testEngine.modal?.onCancel) {
        testEngine.modal.onCancel();
      } else {
        testEngine.closeModal();
      }
    }}
    role="presentation"
  >
    <!-- Modal Card (clicks inside do not propagate) -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="modal-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="modal-header">
        <h2 id="modal-title" class="modal-title">{testEngine.modal.title}</h2>
        <button
          type="button"
          class="btn-close"
          onclick={() => {
            if (testEngine.modal?.onCancel) {
              testEngine.modal.onCancel();
            } else {
              testEngine.closeModal();
            }
          }}
          aria-label="Close dialog"
        >
          <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
            <path fill="currentColor" d={mdiClose} />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <p class="modal-message">{testEngine.modal.message}</p>

        {#if testEngine.modal.warning}
          <p class="modal-warning">{testEngine.modal.warning}</p>
        {/if}

        {#if testEngine.modal.shareUrl}
          <div class="share-box">
            <input
              type="text"
              readonly
              class="share-input"
              value={testEngine.modal.shareUrl}
              onclick={(e) => (e.target as HTMLInputElement).select()}
            />
            <button type="button" class="btn-copy" onclick={copyShareUrl}>
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        {/if}
      </div>

      <!-- Only render footer buttons for confirmation dialogs (not for share dialog) -->
      {#if testEngine.modal.type !== 'share' && (testEngine.modal.cancelText || testEngine.modal.confirmText)}
        <div class="modal-footer">
          {#if testEngine.modal.cancelText}
            <button
              type="button"
              class="btn-secondary"
              onclick={() => {
                if (testEngine.modal?.onCancel) {
                  testEngine.modal.onCancel();
                } else {
                  testEngine.closeModal();
                }
              }}
            >
              {testEngine.modal.cancelText}
            </button>
          {/if}

          {#if testEngine.modal.confirmText}
            <button
              type="button"
              class="btn-primary"
              class:destructive={testEngine.modal.confirmDestructive}
              onclick={() => {
                if (testEngine.modal?.onConfirm) {
                  testEngine.modal.onConfirm();
                } else {
                  testEngine.closeModal();
                }
              }}
            >
              {testEngine.modal.confirmText}
            </button>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background-color: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    animation: fadeIn 0.15s ease-out;
  }

  .modal-card {
    background-color: #111111;
    border: 1px solid #262626;
    border-radius: 8px;
    width: 100%;
    max-width: 440px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
    display: flex;
    flex-direction: column;
    animation: scaleIn 0.15s ease-out;
    overflow: hidden;
  }

  .modal-header {
    padding: 1.25rem 1.5rem 0.6rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .modal-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ffffff;
    margin: 0;
  }

  .btn-close {
    background: transparent;
    border: none;
    color: #777777;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s ease;
  }

  .btn-close:hover {
    color: #ffffff;
  }

  .modal-body {
    padding: 0.5rem 1.5rem 1.5rem;
  }

  .modal-message {
    font-size: 0.9rem;
    color: #aaaaaa;
    line-height: 1.5;
    margin: 0;
  }

  .modal-warning {
    color: #ef4444;
    font-size: 0.88rem;
    font-weight: 600;
    margin: 0.75rem 0 0;
  }

  .share-box {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .share-input {
    flex: 1;
    background-color: #0c0c0c;
    border: 1px solid #2d2d2d;
    border-radius: 4px;
    color: #ededed;
    padding: 0.55rem 0.75rem;
    font-size: 0.85rem;
    font-family: inherit;
  }

  .share-input:focus {
    outline: none;
    border-color: #3b82f6;
  }

  .btn-copy {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
    border: none;
    border-radius: 4px;
    padding: 0 1.1rem;
    font-size: 0.85rem;
    cursor: pointer;
    transition: background-color 0.15s ease;
    white-space: nowrap;
  }

  .btn-copy:hover {
    background-color: #1d4ed8;
  }

  /* Symmetrical, equal-width dialog buttons */
  .modal-footer {
    padding: 0.9rem 1.5rem;
    background-color: #0d0d0d;
    border-top: 1px solid #1c1c1c;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid #282828;
    color: #cccccc;
    padding: 0.55rem 1rem;
    border-radius: 4px;
    font-size: 0.88rem;
    font-weight: 500;
    cursor: pointer;
    text-align: center;
    transition: all 0.15s ease;
  }

  .btn-secondary:hover {
    background-color: #1a1a1a;
    border-color: #444444;
    color: #ffffff;
  }

  .btn-primary {
    background-color: #ffffff;
    color: #000000;
    font-weight: 600;
    border: none;
    padding: 0.55rem 1rem;
    border-radius: 4px;
    font-size: 0.88rem;
    cursor: pointer;
    text-align: center;
    transition: all 0.15s ease;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-primary.destructive {
    background-color: #e11d48;
    color: #ffffff;
  }

  .btn-primary.destructive:hover {
    background-color: #f43f5e;
  }

  .icon {
    width: 18px;
    height: 18px;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes scaleIn {
    from { transform: scale(0.96); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }
</style>
