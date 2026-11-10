<script lang="ts">
  import { onMount } from 'svelte';
  import { asset } from '$app/paths';
  import { testEngine } from '#lib/testEngine.svelte.ts';
  import { DIMENSIONS } from '#lib/dimensions.ts';

  const engine = testEngine;

  onMount(() => {
    engine.init();

    function onKeyDown(e: KeyboardEvent) {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (['1', '2', '3', '4', '5'].includes(e.key)) {
        e.preventDefault();
        engine.answer(Number(e.key));
      } else if (e.ctrlKey && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          engine.redo();
        } else {
          engine.undo();
        }
      } else if (e.ctrlKey && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        engine.redo();
      } else if (e.key === 'Backspace') {
        e.preventDefault();
        engine.undo();
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  });

  const LIKERT_OPTIONS = [
    { value: 1, label: 'Strongly Disagree' },
    { value: 2, label: 'Disagree' },
    { value: 3, label: 'Neutral' },
    { value: 4, label: 'Agree' },
    { value: 5, label: 'Strongly Agree' }
  ];

  function formatTitle(str: string): string {
    return str.replace(/\b\w/g, l => l.toUpperCase());
  }

  let visibleJobCount = $state(20);
  let lastAnsweredCount = $state(0);

  const LADDER = [50, 100, 200, 500, 1000, Infinity];

  function showMore() {
    const next = LADDER.find((step) => step > visibleJobCount);
    if (next !== undefined) {
      if (next === Infinity || next >= engine.topJobs.length) {
        visibleJobCount = engine.topJobs.length;
      } else {
        visibleJobCount = next;
      }
    }
  }

  $effect(() => {
    // Whenever answeredCount changes (new answer, undo, redo, reset), reset to 20
    if (engine.answeredCount !== lastAnsweredCount) {
      lastAnsweredCount = engine.answeredCount;
      visibleJobCount = 20;
    }
  });
</script>

<svelte:head>
  <title>Empirical Career Personality Test | personality2occupation (p2o)</title>
  <meta
    name="description"
    content="Take the free empirical career orientation test matching your Big Five traits and Schwartz values to 2,108 canonical occupations based on deep neural profiles."
  />
  <link rel="canonical" href="https://thereddeveloper.github.io/personality2occupation/test/" />
</svelte:head>

<div class="test-page">
  <main class="test-body">
    {#if engine.isLoading}
      <div class="state-container">
        <img src={asset('loading.svg')} alt="Loading" class="loading-spinner" />
        <p class="loading-desc">{engine.loadingMessage}</p>
      </div>
    {:else if engine.loadError}
      <div class="state-container error">
        <h2>Failed to Load Questionnaire</h2>
        <p>{engine.loadError}</p>
        <button type="button" class="btn-retry" onclick={() => engine.init()}>Retry Loading</button>
      </div>
    {:else}
      <!-- 1. Active Question Prompt (Only shown when taking test, NOT when inspecting shared result) -->
      {#if engine.currentQuestion && !engine.isViewingSharedResult}
        <section class="question-section" aria-label="Current Question">
          <div class="statement-wrapper">
            <h1 class="statement-prompt">
              I {engine.currentQuestion.text}.
            </h1>

            <!-- 5-Point Circular Likert Component -->
            <div class="likert-container" role="group" aria-label="Likert Scale Choices">
              {#each LIKERT_OPTIONS as opt}
                <button
                  type="button"
                  class="likert-choice opt-{opt.value}"
                  onclick={() => engine.answer(opt.value)}
                  aria-label="{opt.label} ({opt.value})"
                >
                  <div class="likert-circle">
                    <span>{opt.value}</span>
                  </div>
                  <span class="likert-label">{opt.label}</span>
                </button>
              {/each}
            </div>

            <div class="desktop-shortcut-hint">
              <span>Press <kbd>1</kbd> through <kbd>5</kbd> on your keyboard</span>
            </div>
          </div>
        </section>
      {/if}

      <!-- 2. Dynamic Results Area: Sectors (Questions 1 to 4) -> Career Matches (Q6+) -->
      {#if engine.answeredCount >= 1 && engine.answeredCount < 5}
        <!-- Stage 1: Macroeconomic Sectors (Shown during initial calibration, questions 1-4) -->
        <section class="sectors-stage" aria-label="Macroeconomic Sectors">
          <div class="sectors-list">
            {#each engine.sectorScores as sec}
              <div class="sector-row">
                <div class="sector-meta">
                  <span class="sector-pct" style="color: {sec.color};">{sec.percentage.toFixed(1)}%</span>
                  <span class="sector-name">{sec.name}</span>
                </div>
                <div class="sector-track">
                  <div
                    class="sector-fill"
                    style="width: {Math.max(1, sec.percentage)}%; background-color: {sec.color};"
                  ></div>
                </div>
              </div>
            {/each}
          </div>
        </section>
      {:else if engine.answeredCount >= 5}
        <!-- Stage 2: Specific Career Matches Unlocked -->
        <section class="careers-stage" aria-label="Career Recommendations">
          <div class="careers-header">
            <h2 class="careers-title">Career Matches</h2>

            <!-- Clean Minimalist Prior Slider -->
            <div class="prior-control" title="Adjust Bayesian prior weighting between niche callings and labor market scale">
              <span class="slider-end">Niche</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                class="prior-slider"
                value={engine.alpha}
                oninput={(e) => engine.setAlpha(Number((e.target as HTMLInputElement).value))}
                aria-label="Prior Weighting Slider"
              />
              <span class="slider-end">Market</span>
            </div>
          </div>

          <!-- Vertical Single-Line Job List -->
          <div class="jobs-list">
            {#each engine.topJobs.slice(0, visibleJobCount) as job}
              <article class="job-card">
                <span class="job-rank">#{job.rank}</span>
                <span class="job-title">{formatTitle(job.title)}</span>
                <span class="job-count">{job.sampleCount.toLocaleString()} profiles</span>
                <span class="job-fit">{job.matchScore}% Fit</span>
              </article>
            {/each}
          </div>

          {#if visibleJobCount < engine.topJobs.length}
            <div class="show-more-wrapper">
              <button
                type="button"
                class="btn-show-more"
                onclick={showMore}
              >
                Show More
              </button>
            </div>
          {/if}
        </section>

        <!-- 3. Openly Visible 24D Coordinates (Unlocks with Career Matches, without redundant title/divider) -->
        <section class="traits-stage" aria-label="24D Personality and Value Coordinates">
          <div class="traits-columns">
            <!-- Big Five Behavior -->
            <div class="trait-block">
              <h3 class="trait-group-heading">Big Five Behavioral Traits</h3>
              <div class="trait-rows">
                {#each DIMENSIONS.slice(0, 5) as dim}
                  <div class="trait-row">
                    <span class="t-name" title={dim.description}>{dim.name}</span>
                    <div class="t-track">
                      <div
                        class="t-fill"
                        style="width: {(engine.userVector[dim.index] * 100).toFixed(0)}%"
                      ></div>
                    </div>
                    <span class="t-val">{(engine.userVector[dim.index] * 100).toFixed(0)}%</span>
                  </div>
                {/each}
              </div>
            </div>

            <!-- Schwartz Values -->
            <div class="trait-block">
              <h3 class="trait-group-heading">Top Personal Values (Schwartz)</h3>
              <div class="trait-rows">
                {#each DIMENSIONS.slice(5) as dim}
                  {#if engine.userVector[dim.index] > 0.08}
                    <div class="trait-row">
                      <span class="t-name" title={dim.description}>{dim.name}</span>
                      <div class="t-track">
                        <div
                          class="t-fill value-fill"
                          style="width: {Math.min(100, engine.userVector[dim.index] * 400).toFixed(0)}%"
                        ></div>
                      </div>
                      <span class="t-val">{(engine.userVector[dim.index] * 100).toFixed(1)}%</span>
                    </div>
                  {/if}
                {/each}
              </div>
            </div>
          </div>
        </section>
      {/if}
    {/if}
  </main>
</div>

<style>
  .test-page {
    flex: 1;
    min-height: calc(100vh - 56px);
    min-height: calc(100dvh - 56px);
    background-color: #000000;
    color: #ededed;
    display: flex;
    flex-direction: column;
  }

  .test-body {
    flex: 1;
    max-width: 1100px;
    width: 100%;
    margin: 0 auto;
    padding: 2.5rem 1.5rem 6rem;
    display: flex;
    flex-direction: column;
    gap: 2.75rem;
  }

  /* Question Section */
  .question-section {
    width: 100%;
  }

  .statement-wrapper {
    background-color: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 8px;
    padding: 3rem 2rem 2.25rem;
    text-align: center;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
  }

  .statement-prompt {
    font-size: 1.85rem;
    font-weight: 600;
    line-height: 1.35;
    color: #ffffff;
    margin: 0 0 2.5rem;
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
    letter-spacing: -0.015em;
  }

  /* Circular Likert Scale */
  .likert-container {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    max-width: 860px;
    margin: 0 auto;
    gap: 0.75rem;
  }

  .likert-choice {
    flex: 1;
    background: transparent;
    border: none;
    padding: 0.5rem 0.25rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    transition: transform 0.15s ease;
  }

  .likert-choice:active {
    transform: scale(0.95);
  }

  .likert-circle {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.15rem;
    font-weight: 700;
    transition: all 0.15s ease;
  }

  .likert-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #888888;
    text-align: center;
    line-height: 1.25;
    transition: color 0.15s ease;
  }

  /* Semantic Colors for Likert Circles */
  .opt-1 .likert-circle {
    border: 2px solid #ef4444;
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
  }
  .opt-1:hover .likert-circle {
    background: #ef4444;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.45);
  }
  .opt-1:hover .likert-label {
    color: #fca5a5;
  }

  .opt-2 .likert-circle {
    border: 2px solid #f87171;
    color: #f87171;
    background: rgba(248, 113, 113, 0.08);
  }
  .opt-2:hover .likert-circle {
    background: #f87171;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(248, 113, 113, 0.45);
  }
  .opt-2:hover .likert-label {
    color: #fecdd3;
  }

  .opt-3 .likert-circle {
    border: 2px solid #94a3b8;
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.08);
  }
  .opt-3:hover .likert-circle {
    background: #94a3b8;
    color: #000000;
    box-shadow: 0 0 16px rgba(148, 163, 184, 0.35);
  }
  .opt-3:hover .likert-label {
    color: #e2e8f0;
  }

  .opt-4 .likert-circle {
    border: 2px solid #34d399;
    color: #34d399;
    background: rgba(52, 211, 153, 0.08);
  }
  .opt-4:hover .likert-circle {
    background: #34d399;
    color: #000000;
    box-shadow: 0 0 16px rgba(52, 211, 153, 0.45);
  }
  .opt-4:hover .likert-label {
    color: #a7f3d0;
  }

  .opt-5 .likert-circle {
    border: 2px solid #10b981;
    color: #10b981;
    background: rgba(16, 185, 129, 0.12);
  }
  .opt-5:hover .likert-circle {
    background: #10b981;
    color: #000000;
    box-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
  }
  .opt-5:hover .likert-label {
    color: #6ee7b7;
  }

  /* Desktop-only keyboard shortcut tip */
  .desktop-shortcut-hint {
    display: none;
    margin-top: 1.5rem;
    font-size: 0.78rem;
    color: #666666;
  }

  .desktop-shortcut-hint kbd {
    background-color: #1c1c1c;
    border: 1px solid #333333;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    color: #aaaaaa;
    font-family: inherit;
    font-size: 0.75rem;
  }

  @media (hover: hover) and (pointer: fine) {
    .desktop-shortcut-hint {
      display: block;
    }
  }

  /* Stage 1: Macroeconomic Sectors (Questions 1 to 4) */
  .sectors-stage {
    background-color: #0c0c0c;
    border: 1px solid #1c1c1c;
    border-radius: 8px;
    padding: 1.5rem;
  }

  .sectors-list {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  .sector-row {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .sector-meta {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-size: 0.8rem;
  }

  .sector-pct {
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    min-width: 2rem;
  }

  .sector-name {
    color: #d1d5db;
    font-weight: 500;
    font-size: 0.8rem;
  }

  .sector-track {
    width: 100%;
    height: 5px;
    background-color: #191919;
    border-radius: 3px;
    overflow: hidden;
  }

  .sector-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Stage 2: Career Matches (Questions 5+) */
  .careers-stage {
    width: 100%;
  }

  .careers-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.25rem;
    gap: 1.5rem;
    flex-wrap: wrap;
  }

  .careers-title {
    font-size: 1.35rem;
    font-weight: 600;
    color: #ffffff;
    margin: 0;
  }

  /* Prior Slider - 50% wider on desktop (180px), full-width on mobile */
  .prior-control {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    background-color: #111111;
    border: 1px solid #222222;
    border-radius: 6px;
    padding: 0.45rem 1rem;
  }

  .slider-end {
    font-size: 0.72rem;
    color: #777777;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .prior-slider {
    -webkit-appearance: none;
    appearance: none;
    width: 180px;
    height: 4px;
    background: #333333;
    border-radius: 2px;
    outline: none;
    cursor: pointer;
    margin: 0;
    padding: 0;
  }

  /* WebKit Track & Thumb */
  .prior-slider::-webkit-slider-runnable-track {
    width: 100%;
    height: 4px;
    background: #333333;
    border-radius: 2px;
    border: none;
  }

  .prior-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ffffff;
    cursor: pointer;
    margin-top: -5px;
    border: none;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
    transition: transform 0.1s ease;
  }

  .prior-slider::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }

  /* Firefox Track & Thumb */
  .prior-slider::-moz-range-track {
    width: 100%;
    height: 4px;
    background: #333333;
    border-radius: 2px;
    border: none;
  }

  .prior-slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ffffff;
    cursor: pointer;
    border: none;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
    transition: transform 0.1s ease;
  }

  .prior-slider::-moz-range-thumb:hover {
    transform: scale(1.15);
  }

  /* Single-Desktop-Line Job List */
  .jobs-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: 100%;
  }

  .job-card {
    background-color: #0e0e0e;
    border: 1px solid #1c1c1c;
    border-radius: 6px;
    padding: 0.75rem 1.15rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    width: 100%;
    box-sizing: border-box;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .job-card:hover {
    border-color: #333333;
    background-color: #121212;
  }

  .job-rank {
    font-size: 0.95rem;
    font-weight: 700;
    color: #666666;
    min-width: 2.2rem;
    flex-shrink: 0;
  }

  .job-title {
    font-size: 0.98rem;
    font-weight: 600;
    color: #ffffff;
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .job-count {
    font-size: 0.82rem;
    color: #777777;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .job-fit {
    font-size: 1.05rem;
    font-weight: 700;
    color: #10b981;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    min-width: 5rem;
    text-align: right;
    flex-shrink: 0;
  }

  .show-more-wrapper {
    display: flex;
    justify-content: center;
    margin-top: 1.25rem;
  }

  .btn-show-more {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.65rem 1.85rem;
    border-radius: 9999px;
    background-color: #141414;
    border: 1px solid #282828;
    color: #ffffff;
    font-size: 0.86rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-show-more:hover {
    background-color: #1e1e1e;
    border-color: #444444;
  }

  .btn-show-more:active {
    transform: scale(0.97);
  }

  /* Stage 3: 24D Traits Section (No redundant title, no divider) */
  .traits-stage {
    width: 100%;
  }

  .traits-columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
    background-color: #0c0c0c;
    border: 1px solid #1c1c1c;
    border-radius: 8px;
    padding: 1.75rem;
  }

  .trait-group-heading {
    font-size: 0.85rem;
    font-weight: 600;
    color: #cccccc;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 0 0 0.85rem;
  }

  .trait-rows {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .trait-row {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-size: 0.8rem;
  }

  .t-name {
    width: 130px;
    color: #cccccc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
  }

  .t-track {
    flex: 1;
    height: 4px;
    background-color: #1f1f1f;
    border-radius: 2px;
    overflow: hidden;
  }

  .t-fill {
    height: 100%;
    background-color: #ffffff;
  }

  .value-fill {
    background-color: #3b82f6;
  }

  .t-val {
    width: 38px;
    text-align: right;
    color: #888888;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  /* States */
  .state-container {
    text-align: center;
    padding: 2rem 1.5rem;
    max-width: 480px;
    margin: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transform: translateY(-1.75rem);
  }

  .loading-spinner {
    width: 48px;
    height: 48px;
    margin-bottom: 1.25rem;
  }

  .loading-desc {
    color: #888888;
    font-size: 0.95rem;
    line-height: 1.5;
    margin: 0;
  }

  .btn-retry {
    background-color: #ffffff;
    color: #000000;
    font-weight: 600;
    border: none;
    border-radius: 4px;
    padding: 0.6rem 1.25rem;
    cursor: pointer;
    font-size: 0.9rem;
    margin-top: 1rem;
    transition: opacity 0.15s ease;
  }

  .btn-retry:hover {
    opacity: 0.9;
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .traits-columns {
      grid-template-columns: 1fr;
      gap: 1.75rem;
      padding: 1.25rem;
    }

    .likert-container {
      gap: 0.35rem;
    }

    .likert-circle {
      width: 44px;
      height: 44px;
      font-size: 1rem;
    }

    .likert-label {
      font-size: 0.72rem;
    }
  }

  @media (max-width: 680px) {
    .careers-header {
      flex-direction: column;
      align-items: stretch;
      gap: 0.85rem;
    }

    .prior-control {
      width: 100%;
      box-sizing: border-box;
      justify-content: space-between;
    }

    .prior-slider {
      flex: 1;
      width: auto;
    }
  }

  @media (max-width: 540px) {
    .statement-wrapper {
      padding: 2rem 1rem 1.75rem;
    }

    .statement-prompt {
      font-size: 1.35rem;
      margin-bottom: 1.75rem;
    }

    .likert-circle {
      width: 40px;
      height: 40px;
      font-size: 0.95rem;
    }

    .likert-label {
      font-size: 0.68rem;
    }

    .job-card {
      padding: 0.7rem 0.85rem;
      gap: 0.65rem;
    }

    .job-title {
      font-size: 0.9rem;
    }

    .job-count {
      display: none;
    }

    .job-fit {
      font-size: 0.95rem;
      min-width: 4rem;
    }
  }
</style>
