<script lang="ts">
  import { resolve, asset } from '$app/paths';
  import PointCloudHero from '#lib/PointCloudHero.svelte';
  import SchwartzCircle from '#lib/SchwartzCircle.svelte';
  import AnimatedLogo from '#lib/AnimatedLogo.svelte';
  import { mdiArrowRight, mdiChevronDown, mdiDownload, mdiGithub, mdiOpenInNew } from '#lib/icons.ts';

  const bigFiveTraits = [
    'Openness',
    'Conscientiousness',
    'Extraversion',
    'Agreeableness',
    'Neuroticism'
  ];

  const bigFiveDescriptions: Record<string, string> = {
    'Openness': 'Curiosity, imagination, and exploration of new ideas.',
    'Conscientiousness': 'Organization, self-discipline, and dependability.',
    'Extraversion': 'Social energy, assertiveness, and enthusiasm.',
    'Agreeableness': 'Compassion, empathy, and trusting cooperation.',
    'Neuroticism': 'Emotional sensitivity, anxiety, and stress reactivity.'
  };

  let activeBigFive = $state<string | null>(null);

  const faqList = [
    {
      question: 'How long does the test take?',
      answer:
        'The test is designed to deliver initial career recommendations in as little as 5 minutes (around 5 to 15 questions). The test always shows the most optimal question based on your previous answers to quickly pinpoint what sets you apart. While a few answers are often enough to discover your top matches, you can keep answering questions for as long as you like to continuously refine the precision and confidence of your results.'
    },
    {
      question: 'Is this test truly free, and is my data private?',
      answer:
        'Yes, 100% free with zero catch. Unlike commercial career tests that make you answer dozens of questions only to lock your results behind paywalls or demand your email for marketing, personality2occupation never asks for your email, has no paywalls, and stores no cookies. The entire matching engine runs locally inside your browser, nothing is ever sent to or stored on any server.'
    },
    {
      question: 'How is this scientifically credible compared to tests like MBTI or 16Personalities?',
      answer:
        'Popular tests like MBTI or 16Personalities force people into rigid, arbitrary 4-letter personality boxes that academic psychologists have widely criticized for low reliability. In contrast, this project is grounded in the peer-reviewed Big Five personality framework and Shalom Schwartz\'s Theory of Basic Human Values. Rather than assigning you an imaginary archetype, we measure you across 24 continuous dimensions and mathematically compare your profile against empirical data from 111,472 working professionals across 2,108 real-world careers. And each of our >1,000 questions is judged across those dimensions using those same measurements based on Machine Learning.'
    },
    {
      question: 'What are the 8 sectors?',
      answer:
        'During your first few answers, the test reveals your probability alignment across 8 broad macroeconomic labor sectors before zeroing in on specific occupations.',
      sectors: [
        { name: 'Technology, Software & Engineering', color: '#00E5FF' },
        { name: 'Arts, Design & Entertainment', color: '#D500F9' },
        { name: 'Public, Law, Defense & Civil', color: '#FF1744' },
        { name: 'Trades, Construction & Extraction', color: '#A1887F' },
        { name: 'Education, Academia & Research', color: '#3D5AFE' },
        { name: 'Corporate, Finance & Commercial', color: '#FFD600' },
        { name: 'Healthcare, Medical & Wellness', color: '#00E676' },
        { name: 'Writing, Journalism & Media', color: '#FF9100' }
      ]
    },
    {
      question: 'What is the "Niche vs Market" slider?',
      answer:
        'A common flaw with career tests is recommending obscure dream jobs that have almost zero real-world openings. In this test, an interactive slider lets you balance pure psychological fit against labor market scale. You can tune the results toward enabling rare, highly tailored niche callings, or slide toward career fields with strong real-world job availability.'
    },
    {
      question: 'Can I save or share my results with someone else?',
      answer:
        'Yes. Clicking the Share button in the test creates a permanent, ultra-compact URL containing an encoded snapshot of just your responses. Because the engine is completely deterministic, anyone opening your link will see your exact career matches. They can also choose to continue the test from where you left off, without any data ever touching a database.'
    },
    {
      question: 'Why does the test match personality and values instead of technical skills?',
      answer:
        'Technical skills change rapidly, and in modern industries, specific tools and requirments can become obsolete within a few years. Humans can learn new skills, but core personality traits and intrinsic values remain remarkably stable across a lifetime. When your underlying temperament and values harmonize with the daily reality and culture of a profession, acquiring the required skills happens naturally.'
    },
    {
      question: 'Is this test for desktop or mobile?',
      answer:
        'The test works perfectly on all platforms, including mobile phones, tablets, and desktop computers. On desktop, keyboard shortcuts allow for even faster answering. Mobile users and people with slow internet can experience slight delays while loading the test.'
    }
  ];

  const structuredData = [
    {
      '@context': 'https://schema.org',
      '@type': 'WebApplication',
      'name': 'personality2occupation',
      'alternateName': 'p2o',
      'applicationCategory': 'EducationalApplication',
      'operatingSystem': 'All',
      'url': 'https://thereddeveloper.github.io/personality2occupation/',
      'description':
        'Free, open-source career orientation tool matching behavioral traits and core values to 2,108 occupations based on empirical data from 111,472 working professionals.',
      'offers': {
        '@type': 'Offer',
        'price': '0',
        'priceCurrency': 'USD'
      },
      'license': 'https://spdx.org/licenses/0BSD.html',
      'author': {
        '@type': 'Person',
        'name': 'TheRedDeveloper',
        'url': 'https://github.com/TheRedDeveloper'
      }
    },
    {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      'name': 'personality2occupation Empirical Career & Personality Dataset',
      'alternateName': 'p2o Dataset',
      'description':
        'Empirical psychometric dataset clustering 111,472 author profiles across 24 continuous personality dimensions (Big Five behavior + 19 Schwartz values) into 2,108 canonical occupations with means and sample variances.',
      'url': 'https://thereddeveloper.github.io/personality2occupation/',
      'keywords': [
        'career personality test',
        'free career test',
        'big five personality traits',
        'schwartz basic human values',
        'career orientation',
        'occupations dataset',
        'psychometrics'
      ],
      'license': 'https://spdx.org/licenses/0BSD.html',
      'creator': {
        '@type': 'Person',
        'name': 'TheRedDeveloper',
        'url': 'https://github.com/TheRedDeveloper'
      },
      'distribution': [
        {
          '@type': 'DataDownload',
          'encodingFormat': 'application/vnd.apache.parquet',
          'contentUrl': 'https://thereddeveloper.github.io/personality2occupation/data.parquet'
        },
        {
          '@type': 'DataDownload',
          'encodingFormat': 'application/vnd.apache.parquet',
          'contentUrl': 'https://thereddeveloper.github.io/personality2occupation/occupations_personality.parquet'
        }
      ]
    },
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': faqList.map((faq) => {
        let answerText = faq.answer;
        if (faq.sectors && faq.sectors.length > 0) {
          answerText += ' ' + faq.sectors.map((s) => s.name).join('; ');
        }
        return {
          '@type': 'Question',
          'name': faq.question,
          'acceptedAnswer': {
            '@type': 'Answer',
            'text': answerText
          }
        };
      })
    }
  ];
</script>

<svelte:head>
  <title>personality2occupation (p2o) | Free Career Personality Test</title>
  <meta
    name="description"
    content="Free, open-source career orientation tool matching personality traits and values to 2,108 occupations based on empirical data from 111,472 professionals."
  />
  <link rel="canonical" href="https://thereddeveloper.github.io/personality2occupation/" />

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://thereddeveloper.github.io/personality2occupation/" />
  <meta property="og:title" content="personality2occupation (p2o) | Free Career Personality Test" />
  <meta
    property="og:description"
    content="Free, open-source career orientation tool matching personality traits and values to 2,108 occupations based on empirical data from 111,472 professionals."
  />
  <meta property="og:image" content="https://thereddeveloper.github.io/personality2occupation/og-image.png" />
  <meta property="og:site_name" content="personality2occupation" />
  <meta property="og:locale" content="en_US" />

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:url" content="https://thereddeveloper.github.io/personality2occupation/" />
  <meta name="twitter:title" content="personality2occupation (p2o) | Free Career Personality Test" />
  <meta
    name="twitter:description"
    content="Free, open-source career orientation tool matching personality traits and values to 2,108 occupations based on empirical data from 111,472 professionals."
  />
  <meta name="twitter:image" content="https://thereddeveloper.github.io/personality2occupation/og-image.png" />

  <!-- Structured Data (JSON-LD) -->
  {@html `<script type="application/ld+json">${JSON.stringify(structuredData)}</script>`}
</svelte:head>

<main class="page-container">
  <!-- Hero Section -->
  <section class="hero-section">
    <div class="hero-left">
      <div class="hero-logo-box">
        <AnimatedLogo width="130" height="130" />
      </div>
      <h1 class="hero-title">personality2occupation</h1>
      <p class="hero-desc">
        A free and open-source career orientation tool that matches your behavioral traits and core values to
        2,108 occupations based on empirical data from 111,472 working professionals.
      </p>
      <div class="hero-actions">
        <a href={resolve('/test')} class="btn-primary">
          <span>Take 5min test</span>
          <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
            <path fill="currentColor" d={mdiArrowRight} />
          </svg>
        </a>
      </div>
    </div>

    <div class="hero-right">
      <PointCloudHero />
    </div>
  </section>

  <!-- How It Works & Data Source -->
  <section class="section">
    <h2>How It Works</h2>
    <div class="prose">
      <p>
        Most online career tests lure you in with unvalidated archetypes, lock your results behind paywalls,
        and harvest your personal data. This project is completely free, 100% private, and built on empirical
        distributions observed directly from real people in their actual jobs.
      </p>
      <p>
        The dataset aggregates over 192 million words from 111,472 anonymized author profiles across Reddit,
        Bluesky, and Blogger, scored across 24 dimensions.
      </p>
      <p>
        These profiles were clustered into 2,108 canonical occupations with at least 10 observations each, 261
        occupations have over 100 observations. For every occupation, the dataset tracks both the mean and variance.
      </p>
      <p>
        The test is adjusted on the fly, to quickly predict the most fitting occupations based on the likelyhood of
        each occupation under the observed test scores.
      </p>
    </div>
  </section>

  <!-- The 24 Dimensions -->
  <section class="section">
    <h2>The 24 Dimensions</h2>

    <div class="dimensions-split">
      <!-- Big Five column -->
      <div class="dimension-col">
        <h3>Behavior (Big Five)</h3>
        <p class="big5-lead">
          The Big Five is the gold standard and top metric used in scientific psychology and behavioral research.
        </p>
        <ul class="big5-list">
          {#each bigFiveTraits as trait}
            <li
              class:active={activeBigFive === trait}
              onmouseenter={() => (activeBigFive = trait)}
              onmouseleave={() => (activeBigFive = null)}
              onpointerdown={() => (activeBigFive = trait)}
            >
              {trait}
            </li>
          {/each}
        </ul>
        <div class="big5-caption-container">
          {#if activeBigFive && bigFiveDescriptions[activeBigFive]}
            <div class="big5-caption-desc">{bigFiveDescriptions[activeBigFive]}</div>
          {:else}
            <div class="big5-caption-placeholder">Hover or tap any trait to see its meaning</div>
          {/if}
        </div>
      </div>

      <!-- Schwartz circle column -->
      <div class="dimension-col">
        <h3>Values (Schwartz)</h3>
        <SchwartzCircle />
      </div>
    </div>
  </section>

  <!-- Why Personality Instead of Skills -->
  <section class="section">
    <h2>Why Personality Instead of Skills</h2>
    <blockquote class="quote-block">
      <p>“Specialization is for insects.”</p>
      <cite>Robert A. Heinlein</cite>
    </blockquote>

    <div class="prose">
      <p>
        I got sick of skill-based career tests. Humans can build virtually any skill, and specific technical skills
        change rapidly or become obsolete.
      </p>
      <p>
        What remains remarkably stable over a career is a person's traits and values.
        When your values and traits align with the culture of your chosen field, picking up skills is natural.
      </p>
    </div>
  </section>

  <!-- Compute & Open Source (Merged Section) -->
  <section class="section">
    <h2>Compute & Open Source</h2>
    <div class="prose">
      <p>
        I assembled this entire dataset locally using 90 hours of compute on my personal workstation powered by an
        NVIDIA RTX 3060 12GB and an AMD Ryzen 9 5900X PC.
      </p>
      <p>
        Processing 111,472 author profiles across 192 million words required substantial batched transformer inference
        for Big Five trait scoring and Schwartz value classification, and required 30h of local LLM work to extract
        jobs from candidate posts/bios. Keeping the pipeline local and open guarantees complete transparency and
        independence from closed proprietary APIs.
      </p>
      <p>
        Everything here is released under the Zero-Clause BSD (0BSD) license on
        <a
          href="https://github.com/TheRedDeveloper/personality2occupation"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-link"
        >
          <span>GitHub</span>
          <svg viewBox="0 0 24 24" class="icon-inline" aria-hidden="true">
            <path fill="currentColor" d={mdiOpenInNew} />
          </svg>
        </a>.
        This is public domain equivalent: you can freely use, modify, distribute, or commercially integrate these
        datasets without restrictions, fees, or required attribution.
      </p>
    </div>

    <!-- Downloads List -->
    <div class="downloads-list">
      <div class="download-item">
        <div class="download-info">
          <div class="download-name">
            <span>occupations</span>
            <svg viewBox="0 0 24 24" class="icon-arrow" aria-hidden="true">
              <path fill="currentColor" d={mdiArrowRight} />
            </svg>
            <span>text</span>
          </div>
          <div class="download-file">occupations_text.parquet (~893 MB)</div>
          <div class="download-desc">111,472 anonymized author profiles with over 192M words of raw text.</div>
        </div>
        <div class="download-buttons">
          <a
            href="https://github.com/TheRedDeveloper/personality2occupation/releases"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-action"
          >
            <svg viewBox="0 0 24 24" class="btn-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiGithub} />
            </svg>
            <span>GitHub Releases</span>
          </a>
        </div>
      </div>

      <div class="download-item">
        <div class="download-info">
          <div class="download-name">
            <span>occupations</span>
            <svg viewBox="0 0 24 24" class="icon-arrow" aria-hidden="true">
              <path fill="currentColor" d={mdiArrowRight} />
            </svg>
            <span>personality</span>
          </div>
          <div class="download-file">occupations_personality.parquet (~6.1 MB)</div>
          <div class="download-desc">111,472 anonymized users with continuous 24D personality vectors.</div>
        </div>
        <div class="download-buttons">
          <a
            href={asset('occupations_personality.parquet')}
            download="occupations_personality.parquet"
            class="btn-action"
          >
            <svg viewBox="0 0 24 24" class="btn-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiDownload} />
            </svg>
            <span>Download</span>
          </a>
        </div>
      </div>

      <div class="download-item">
        <div class="download-info">
          <div class="download-name">
            <span>occupation</span>
            <svg viewBox="0 0 24 24" class="icon-arrow" aria-hidden="true">
              <path fill="currentColor" d={mdiArrowRight} />
            </svg>
            <span>personality + variance</span>
          </div>
          <div class="download-file">data.parquet (~629 KB)</div>
          <div class="download-desc">2,108 canonical occupations with 24D means and sample variances.</div>
        </div>
        <div class="download-buttons">
          <a
            href={asset('data.parquet')}
            download="data.parquet"
            class="btn-action"
          >
            <svg viewBox="0 0 24 24" class="btn-icon" aria-hidden="true">
              <path fill="currentColor" d={mdiDownload} />
            </svg>
            <span>Download</span>
          </a>
        </div>
      </div>
    </div>
  </section>

  <!-- Frequently Asked Questions -->
  <section class="section faq-section">
    <h2>Frequently Asked Questions</h2>
    <div class="faq-list">
      {#each faqList as faq}
        <details class="faq-item">
          <summary class="faq-summary">
            <span class="faq-question">{faq.question}</span>
            <svg viewBox="0 0 24 24" class="icon-chevron" aria-hidden="true">
              <path fill="currentColor" d={mdiChevronDown} />
            </svg>
          </summary>
          <div class="faq-answer">
            <p>{faq.answer}</p>
            {#if faq.sectors}
              <div class="faq-sectors-grid">
                {#each faq.sectors as sec}
                  <div class="faq-sector-item">
                    <span class="faq-sector-dot" style="background-color: {sec.color};"></span>
                    <span>{sec.name}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </details>
      {/each}
    </div>
  </section>

  <!-- Footer -->
  <footer class="footer">
    <p>
      Zero-BSD License ·
      <a
        href="https://github.com/TheRedDeveloper/personality2occupation"
        target="_blank"
        rel="noopener noreferrer"
        class="footer-link"
      >
        <span>GitHub</span>
        <svg viewBox="0 0 24 24" class="icon-inline" aria-hidden="true">
          <path fill="currentColor" d={mdiOpenInNew} />
        </svg>
      </a>
    </p>
  </footer>
</main>

<style>
  .page-container {
    max-width: 1360px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
    color: #ededed;
    background-color: #000000;
  }

  @media (max-width: 480px) {
    .page-container {
      padding: 1.5rem 1rem 3rem;
    }
  }

  /* Hero Section */
  .hero-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: clamp(1.5rem, 3vw, 2.5rem);
    align-items: center;
    padding: 1.5rem 0 3.5rem;
  }

  @media (max-width: 840px) {
    .hero-section {
      grid-template-columns: 1fr;
      gap: 2rem;
      padding: 1rem 0 2.5rem;
    }
  }

  .hero-left {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    container-type: inline-size;
    width: 100%;
  }

  @keyframes heroFadeIn {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .hero-logo-box {
    display: block;
    width: 130px;
    height: 130px;
    margin-bottom: 0.65rem;
    animation: heroFadeIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) backwards;
  }

  .hero-title {
    font-family: 'Original Surfer', cursive, sans-serif;
    font-size: clamp(1.2rem, 3.8vw, 2.25rem);
    font-size: clamp(1.2rem, 7.2cqw, 2.25rem);
    font-weight: 400;
    letter-spacing: -0.01em;
    margin: 0 0 1rem;
    color: #ffffff;
    line-height: 1.15;
    white-space: nowrap;
    animation: heroFadeIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) 0.08s backwards;
  }

  .hero-desc {
    font-size: 1.05rem;
    line-height: 1.6;
    color: #999999;
    margin: 0 0 1.5rem;
    animation: heroFadeIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) 0.16s backwards;
  }

  .hero-actions {
    display: flex;
    gap: 1rem;
    animation: heroFadeIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) 0.24s backwards;
  }

  .hero-right {
    display: flex;
    justify-content: center;
    align-items: center;
    animation: heroFadeIn 0.55s cubic-bezier(0.16, 1, 0.3, 1) 0.12s backwards;
  }

  @media (prefers-reduced-motion: reduce) {
    .hero-logo-box,
    .hero-title,
    .hero-desc,
    .hero-actions,
    .hero-right {
      animation: none !important;
      opacity: 1 !important;
      transform: none !important;
    }
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #ffffff;
    color: #000000;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.6rem 1.25rem;
    border-radius: 6px;
    text-decoration: none;
    transition: background 0.15s ease;
  }

  .btn-primary:hover {
    background: #d4d4d4;
  }

  .icon {
    width: 16px;
    height: 16px;
    display: block;
  }

  /* General Content Sections */
  .section {
    padding: 3.25rem 0;
  }

  .section h2 {
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    margin: 0 0 1rem;
  }

  .prose p {
    font-size: 1rem;
    line-height: 1.65;
    color: #a3a3a3;
    margin: 0 0 1rem;
  }

  .prose p:last-child {
    margin-bottom: 0;
  }

  .inline-link {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    color: #ffffff;
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .inline-link:hover {
    color: #cccccc;
  }

  /* 24 Dimensions Split Layout */
  .dimensions-split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    align-items: flex-start;
  }

  @media (max-width: 768px) {
    .dimensions-split {
      grid-template-columns: 1fr;
      gap: 2rem;
    }
  }

  .dimension-col h3 {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ffffff;
    margin: 0 0 1rem;
  }

  .big5-lead {
    font-size: 0.95rem;
    line-height: 1.6;
    color: #a3a3a3;
    margin-bottom: 1.25rem;
  }

  .big5-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 1px solid #222222;
    border-radius: 8px;
    overflow: hidden;
    background: #0d0d0d;
  }

  .big5-list li {
    font-size: 0.95rem;
    font-weight: 500;
    color: #cccccc;
    padding: 0.65rem 0.95rem;
    background: transparent;
    border: none;
    border-bottom: 1px solid #1c1c1c;
    border-radius: 0;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
    user-select: none;
  }

  .big5-list li:last-child {
    border-bottom: none;
  }

  .big5-list li:hover,
  .big5-list li.active {
    color: #ffffff;
    background: #1a1a1a;
  }

  .big5-caption-container {
    min-height: 4rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 1.25rem 0.25rem 0;
  }

  .big5-caption-desc {
    font-size: 0.9rem;
    color: #d0d0d0;
    line-height: 1.5;
  }

  .big5-caption-placeholder {
    font-size: 0.85rem;
    color: #999999;
  }

  /* Quote */
  .quote-block {
    margin: 0 0 1.5rem;
    padding: 1.15rem 1.5rem;
    border-left: 2px solid #333333;
    background: #0a0a0a;
  }

  .quote-block p {
    font-size: 1.02rem;
    line-height: 1.65;
    color: #cccccc;
    font-style: italic;
    margin: 0 0 0.65rem;
  }

  .quote-block cite {
    display: block;
    font-size: 0.88rem;
    color: #999999;
    font-style: normal;
  }

  /* Downloads List */
  .downloads-list {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin-top: 1.75rem;
  }

  .download-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 1.15rem 1.4rem;
    background: #0d0d0d;
    border: 1px solid #222222;
    border-radius: 6px;
  }

  @media (max-width: 600px) {
    .download-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }
  }

  .download-name {
    font-size: 1rem;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 0.2rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .icon-arrow {
    width: 15px;
    height: 15px;
    display: inline-block;
    color: #888888;
  }

  .download-file {
    font-size: 0.8rem;
    font-family: ui-monospace, monospace;
    color: #9e9e9e;
    margin-bottom: 0.35rem;
  }

  .download-desc {
    font-size: 0.88rem;
    color: #a3a3a3;
  }

  .btn-action {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.88rem;
    font-weight: 500;
    padding: 0.45rem 0.95rem;
    border-radius: 6px;
    text-decoration: none;
    white-space: nowrap;
    background: #171717;
    border: 1px solid #333333;
    color: #ffffff;
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .btn-action:hover {
    background: #262626;
    border-color: #555555;
  }

  .btn-icon {
    width: 16px;
    height: 16px;
    display: block;
  }

  /* FAQ Section */
  .faq-section {
    margin-top: 1rem;
  }

  .faq-list {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  details.faq-item {
    background-color: #0c0c0c;
    border: 1px solid #1a1a1a;
    border-radius: 8px;
    transition: border-color 0.15s ease, background-color 0.15s ease;
    overflow: hidden;
  }

  details.faq-item:hover {
    border-color: #2a2a2a;
    background-color: #0f0f0f;
  }

  details.faq-item[open] {
    border-color: #2e2e2e;
    background-color: #0d0d0d;
  }

  summary.faq-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.15rem 1.4rem;
    cursor: pointer;
    list-style: none;
    user-select: none;
    gap: 1rem;
  }

  summary.faq-summary::-webkit-details-marker {
    display: none;
  }

  .faq-question {
    font-size: 1.02rem;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.4;
  }

  .icon-chevron {
    width: 20px;
    height: 20px;
    color: #777777;
    flex-shrink: 0;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), color 0.15s ease;
  }

  details.faq-item[open] .icon-chevron {
    transform: rotate(180deg);
    color: #ffffff;
  }

  .faq-answer {
    padding: 0 1.4rem 1.25rem 1.4rem;
    color: #a3a3a3;
    font-size: 0.95rem;
    line-height: 1.65;
  }

  .faq-answer p {
    margin: 0;
  }

  .faq-sectors-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.65rem 1rem;
    margin-top: 1rem;
    padding-top: 0.9rem;
    border-top: 1px solid #1a1a1a;
  }

  .faq-sector-item {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.85rem;
    color: #d4d4d4;
  }

  .faq-sector-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* Footer */
  .footer {
    padding: 2.5rem 0 1rem;
    font-size: 0.85rem;
    color: #888888;
    text-align: center;
  }

  .footer-link {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    color: #a3a3a3;
    text-decoration: underline;
    text-underline-offset: 3px;
    transition: color 0.15s ease;
  }

  .footer-link:hover {
    color: #ffffff;
  }

  .icon-inline {
    width: 13px;
    height: 13px;
    display: inline-block;
  }
</style>
