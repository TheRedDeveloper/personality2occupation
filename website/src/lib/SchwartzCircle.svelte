<script lang="ts">
  let {
    values = undefined
  }: {
    values?: number[];
  } = $props();

  const DESCRIPTIONS: Record<string, { title: string; italic: string }> = {
    'self-direction-thought': {
      title: 'Self-direction: thought',
      italic: "Freedom to cultivate one's own ideas and abilities."
    },
    'self-direction-action': {
      title: 'Self-direction: action',
      italic: "Freedom to determine one's own actions."
    },
    'stimulation': {
      title: 'Stimulation',
      italic: 'Excitement, novelty, and change.'
    },
    'hedonism': {
      title: 'Hedonism',
      italic: 'Pleasure and sensuous gratification.'
    },
    'achievement': {
      title: 'Achievement',
      italic: 'Success according to social standards.'
    },
    'power-dominance': {
      title: 'Power: dominance',
      italic: 'Power through exercising control over people.'
    },
    'power-resources': {
      title: 'Power: resources',
      italic: 'Power through control of material and social resources.'
    },
    'face': {
      title: 'Face',
      italic: 'Security and power through maintaining one’s public image and avoiding humiliation.'
    },
    'security-personal': {
      title: 'Security: personal',
      italic: "Safety in one's immediate environment."
    },
    'security-societal': {
      title: 'Security: societal',
      italic: 'Safety and stability in the wider society.'
    },
    'tradition': {
      title: 'Tradition',
      italic: 'Maintaining and preserving cultural, family, or religious traditions.'
    },
    'conformity-rules': {
      title: 'Conformity: rules',
      italic: 'Compliance with rules, laws, and formal obligations.'
    },
    'conformity-interpersonal': {
      title: 'Conformity: interpersonal',
      italic: 'Avoidance of upsetting or harming other people.'
    },
    'humility': {
      title: 'Humility',
      italic: "Recognizing one's insignificance in the larger scheme of things."
    },
    'benevolence-caring': {
      title: 'Benevolence: caring',
      italic: 'Devotion to the welfare of in-group members.'
    },
    'benevolence-dependability': {
      title: 'Benevolence: dependability',
      italic: 'Being a reliable and trustworthy member of the in-group.'
    },
    'universalism-concern': {
      title: 'Universalism: concern',
      italic: 'Commitment to equality, justice, and protection for all people.'
    },
    'universalism-nature': {
      title: 'Universalism: nature',
      italic: 'Preservation of the natural environment.'
    },
    'universalism-tolerance': {
      title: 'Universalism: tolerance',
      italic: 'Acceptance and understanding of those who are different from oneself.'
    },
    'openness-to-change': {
      title: 'Openness to change',
      italic: 'Readiness for change and independence of thought, action, and feelings.'
    },
    'self-enhancement': {
      title: 'Self-enhancement',
      italic: "Pursuit of one's own interests, success, and dominance over others."
    },
    'conservation': {
      title: 'Conservation',
      italic: 'Preservation of the past, order, and resistance to change.'
    },
    'self-transcendence': {
      title: 'Self-transcendence',
      italic: 'Concern for the welfare and interests of others.'
    }
  };

  const CATEGORY_TO_INDEX: Record<string, number> = {
    'self-direction-thought': 0,
    'self-direction-action': 1,
    'stimulation': 2,
    'hedonism': 3,
    'achievement': 4,
    'power-dominance': 5,
    'power-resources': 6,
    'face': 7,
    'security-personal': 8,
    'security-societal': 9,
    'tradition': 10,
    'conformity-rules': 11,
    'conformity-interpersonal': 12,
    'humility': 13,
    'benevolence-caring': 14,
    'benevolence-dependability': 15,
    'universalism-concern': 16,
    'universalism-nature': 17,
    'universalism-tolerance': 18
  };

  const QUADRANT_CATEGORIES: Record<string, string[]> = {
    'openness-to-change': ['self-direction-thought', 'self-direction-action', 'stimulation', 'hedonism'],
    'self-enhancement': ['hedonism', 'achievement', 'power-dominance', 'power-resources', 'face'],
    'conservation': ['face', 'security-personal', 'security-societal', 'tradition', 'conformity-rules', 'conformity-interpersonal', 'humility'],
    'self-transcendence': ['humility', 'benevolence-caring', 'benevolence-dependability', 'universalism-concern', 'universalism-nature', 'universalism-tolerance']
  };

  const SLICES = [
    // Openness to change (warm amber)
    { id: 'self-direction-thought', quadrant: 'openness-to-change', color: '#fbbf24', x1: 0, y1: -160, x2: 51.95, y2: -151.33, sweep: 1 },
    { id: 'self-direction-action', quadrant: 'openness-to-change', color: '#fbbf24', x1: 51.95, y1: -151.33, x2: 98.27, y2: -126.26, sweep: 1 },
    { id: 'stimulation', quadrant: 'openness-to-change', color: '#fbbf24', x1: 98.27, y1: -126.26, x2: 133.95, y2: -87.51, sweep: 1 },

    // Hedonism: sits on the boundary between Openness to change and Self-enhancement
    // Openness to change half (warm amber)
    { id: 'hedonism', quadrant: 'openness-to-change', color: '#fbbf24', x1: 133.95, y1: -87.51, x2: 146.52, y2: -64.27, sweep: 1 },
    // Self-enhancement half (rose red)
    { id: 'hedonism', quadrant: 'self-enhancement', color: '#f43f5e', x1: 146.52, y1: -64.27, x2: 155.10, y2: -39.28, sweep: 1 },

    // Self-enhancement (rose red)
    { id: 'achievement', quadrant: 'self-enhancement', color: '#f43f5e', x1: 155.10, y1: -39.28, x2: 159.45, y2: 13.21, sweep: 1 },
    { id: 'power-dominance', quadrant: 'self-enhancement', color: '#f43f5e', x1: 159.45, y1: 13.21, x2: 146.52, y2: 64.27, sweep: 1 },
    { id: 'power-resources', quadrant: 'self-enhancement', color: '#f43f5e', x1: 146.42, y1: 64.27, x2: 117.72, y2: 108.37, sweep: 1 },

    // Face: sits on the boundary between Self-enhancement and Conservation
    // Self-enhancement half (rose red)
    { id: 'face', quadrant: 'self-enhancement', color: '#f43f5e', x1: 117.72, y1: 108.37, x2: 98.27, y2: 126.26, sweep: 1 },
    // Conservation half (emerald green)
    { id: 'face', quadrant: 'conservation', color: '#10b981', x1: 98.27, y1: 126.26, x2: 76.15, y2: 140.72, sweep: 1 },

    // Conservation (emerald green)
    { id: 'security-personal', quadrant: 'conservation', color: '#10b981', x1: 76.15, y1: 140.72, x2: 26.33, y2: 157.82, sweep: 1 },
    { id: 'security-societal', quadrant: 'conservation', color: '#10b981', x1: 26.33, y1: 157.82, x2: -26.33, y2: 157.82, sweep: 1 },
    { id: 'tradition', quadrant: 'conservation', color: '#10b981', x1: -76.15, y1: 140.72, x2: -26.33, y2: 157.82, sweep: 0 },
    { id: 'conformity-rules', quadrant: 'conservation', color: '#10b981', x1: -117.72, y1: 108.37, x2: -76.15, y2: 140.72, sweep: 0 },
    { id: 'conformity-interpersonal', quadrant: 'conservation', color: '#10b981', x1: -146.52, y1: 64.27, x2: -117.72, y2: 108.37, sweep: 0 },

    // Humility: sits on the boundary between Conservation and Self-transcendence
    // Conservation half (emerald green)
    { id: 'humility', quadrant: 'conservation', color: '#10b981', x1: -155.10, y1: 39.28, x2: -146.52, y2: 64.27, sweep: 0 },
    // Self-transcendence half (sky blue)
    { id: 'humility', quadrant: 'self-transcendence', color: '#38bdf8', x1: -159.45, y1: 13.21, x2: -155.10, y2: 39.28, sweep: 0 },

    // Self-transcendence (sky blue)
    { id: 'benevolence-caring', quadrant: 'self-transcendence', color: '#38bdf8', x1: -155.10, y1: -39.28, x2: -159.45, y2: 13.21, sweep: 0 },
    { id: 'benevolence-dependability', quadrant: 'self-transcendence', color: '#38bdf8', x1: -133.95, y1: -87.51, x2: -155.10, y2: -39.28, sweep: 0 },
    { id: 'universalism-concern', quadrant: 'self-transcendence', color: '#38bdf8', x1: -98.27, y1: -126.26, x2: -133.95, y2: -87.51, sweep: 0 },
    { id: 'universalism-nature', quadrant: 'self-transcendence', color: '#38bdf8', x1: -51.95, y1: -151.33, x2: -98.27, y2: -126.26, sweep: 0 },
    { id: 'universalism-tolerance', quadrant: 'self-transcendence', color: '#38bdf8', x1: 0, y1: -160, x2: -51.95, y2: -151.33, sweep: 0 }
  ];

  let activeCategory = $state<string | null>(null);

  function setActive(cat: string | null) {
    activeCategory = cat;
  }

  function handleClick(cat: string) {
    activeCategory = cat;
  }

  function getCategoryColor(catId: string): string {
    if (['self-direction-thought', 'self-direction-action', 'stimulation', 'openness-to-change'].includes(catId)) {
      return '#fbbf24'; // Openness to change (warm amber)
    }
    if (['achievement', 'power-dominance', 'power-resources', 'self-enhancement'].includes(catId)) {
      return '#f43f5e'; // Self-enhancement (rose red)
    }
    if (['security-personal', 'security-societal', 'tradition', 'conformity-rules', 'conformity-interpersonal', 'conservation'].includes(catId)) {
      return '#10b981'; // Conservation (emerald green)
    }
    return '#38bdf8'; // Self-transcendence (sky blue)
  }

  function getBadgeStyle(cat: string): string {
    if (cat === 'hedonism') {
      return 'background: linear-gradient(90deg, rgba(251, 191, 36, 0.22), rgba(244, 63, 94, 0.22)) padding-box, linear-gradient(90deg, rgba(251, 191, 36, 0.6), rgba(244, 63, 94, 0.6)) border-box; border: 1px solid transparent; color: #ffffff;';
    }
    if (cat === 'face') {
      return 'background: linear-gradient(90deg, rgba(244, 63, 94, 0.22), rgba(16, 185, 129, 0.22)) padding-box, linear-gradient(90deg, rgba(244, 63, 94, 0.6), rgba(16, 185, 129, 0.6)) border-box; border: 1px solid transparent; color: #ffffff;';
    }
    if (cat === 'humility') {
      return 'background: linear-gradient(90deg, rgba(16, 185, 129, 0.22), rgba(56, 189, 248, 0.22)) padding-box, linear-gradient(90deg, rgba(16, 185, 129, 0.6), rgba(56, 189, 248, 0.6)) border-box; border: 1px solid transparent; color: #ffffff;';
    }
    const color = getCategoryColor(cat);
    return `color: ${color}; background: ${color}1f; border: 1px solid ${color}40;`;
  }

  function getWedgePath(x1: number, y1: number, x2: number, y2: number, sweep: number, catId: string): string {
    if (!values) return '';
    const idx = CATEGORY_TO_INDEX[catId];
    if (idx === undefined || values[idx] === undefined) return '';
    const normVal = values[idx];
    const fraction = Math.max(0.06, Math.min(1.0, normVal));
    const r = (160 * fraction).toFixed(2);
    const sx = (x1 * fraction).toFixed(2);
    const sy = (y1 * fraction).toFixed(2);
    const ex = (x2 * fraction).toFixed(2);
    const ey = (y2 * fraction).toFixed(2);
    return `M 0,0 L ${sx},${sy} A ${r} ${r} 0 0 ${sweep} ${ex},${ey} z`;
  }

  function getCategoryPct(cat: string): number | null {
    if (!values) return null;
    const idx = CATEGORY_TO_INDEX[cat];
    if (idx !== undefined && values[idx] !== undefined) {
      return Math.round(values[idx] * 100);
    }
    const members = QUADRANT_CATEGORIES[cat];
    if (members) {
      let sum = 0;
      let count = 0;
      for (const m of members) {
        const mIdx = CATEGORY_TO_INDEX[m];
        if (mIdx !== undefined && values[mIdx] !== undefined) {
          sum += values[mIdx];
          count++;
        }
      }
      return count > 0 ? Math.round((sum / count) * 100) : null;
    }
    return null;
  }
</script>

<div class="circle-wrapper">
  <svg
    viewBox="-182 -182 364 364"
    class="continuum-svg"
    role="region"
    aria-label="Schwartz human values circle"
    onmouseleave={() => setActive(null)}
  >
    <!-- Backlights (highlighted wedges) -->
    <g class="backlights">
      <path
        data-category="openness-to-change"
        d="M 0,0 L 0,-180 A 180 180 0 0 1 164.84 -72.31 z"
        class:highlighted={activeCategory === 'openness-to-change'}
      />
      <path
        data-category="self-enhancement"
        d="M 0,0 L 164.84,-72.31 A 180 180 0 0 1 110.56 142.05 z"
        class:highlighted={activeCategory === 'self-enhancement'}
      />
      <path
        data-category="conservation"
        d="M 0,0 L 110.56,142.05 A 180 180 0 0 1 -174.49 44.19 z"
        class:highlighted={activeCategory === 'conservation'}
      />
      <path
        data-category="self-transcendence"
        d="M 0,0 L -174.49,44.19 A 180 180 0 0 1 0,-180 z"
        class:highlighted={activeCategory === 'self-transcendence'}
      />

      <path
        data-category="self-direction-thought"
        d="M 0,0 L 0,-160 A 160 160 0 0 1 51.95 -151.33 z"
        class:highlighted={activeCategory === 'self-direction-thought'}
      />
      <path
        data-category="self-direction-action"
        d="M 0,0 L 51.95,-151.33 A 160 160 0 0 1 98.27 -126.26 z"
        class:highlighted={activeCategory === 'self-direction-action'}
      />
      <path
        data-category="stimulation"
        d="M 0,0 L 98.27,-126.26 A 160 160 0 0 1 133.95 -87.51 z"
        class:highlighted={activeCategory === 'stimulation'}
      />
      <path
        data-category="hedonism"
        d="M 0,0 L 133.95,-87.51 A 160 160 0 0 1 155.10 -39.28 z"
        class:highlighted={activeCategory === 'hedonism'}
      />
      <path
        data-category="achievement"
        d="M 0,0 L 155.10,-39.28 A 160 160 0 0 1 159.45 13.21 z"
        class:highlighted={activeCategory === 'achievement'}
      />
      <path
        data-category="power-dominance"
        d="M 0,0 L 159.45,13.21 A 160 160 0 0 1 146.52 64.27 z"
        class:highlighted={activeCategory === 'power-dominance'}
      />
      <path
        data-category="power-resources"
        d="M 0,0 L 146.42,64.27 A 160 160 0 0 1 117.72 108.37 z"
        class:highlighted={activeCategory === 'power-resources'}
      />
      <path
        data-category="face"
        d="M 0,0 L 117.72,108.37 A 160 160 0 0 1 76.15 140.72 z"
        class:highlighted={activeCategory === 'face'}
      />
      <path
        data-category="security-personal"
        d="M 0,0 L 76.15,140.72 A 160 160 0 0 1 26.33 157.82 z"
        class:highlighted={activeCategory === 'security-personal'}
      />
      <path
        data-category="security-societal"
        d="M 0,0 L 26.33,157.82 A 160 160 0 0 1 -26.33 157.82 z"
        class:highlighted={activeCategory === 'security-societal'}
      />
      <path
        data-category="tradition"
        d="M 0,0 L -76.15,140.72 A 160 160 0 0 0 -26.33 157.82 z"
        class:highlighted={activeCategory === 'tradition'}
      />
      <path
        data-category="conformity-rules"
        d="M 0,0 L -117.72,108.37 A 160 160 0 0 0 -76.15 140.72 z"
        class:highlighted={activeCategory === 'conformity-rules'}
      />
      <path
        data-category="conformity-interpersonal"
        d="M 0,0 L -146.52,64.27 A 160 160 0 0 0 -117.72 108.37 z"
        class:highlighted={activeCategory === 'conformity-interpersonal'}
      />
      <path
        data-category="humility"
        d="M 0,0 L -159.45,13.21 A 160 160 0 0 0 -146.52 64.27 z"
        class:highlighted={activeCategory === 'humility'}
      />
      <path
        data-category="benevolence-caring"
        d="M 0,0 L -155.10,-39.28 A 160 160 0 0 0 -159.45 13.21 z"
        class:highlighted={activeCategory === 'benevolence-caring'}
      />
      <path
        data-category="benevolence-dependability"
        d="M 0,0 L -133.95,-87.51 A 160 160 0 0 0 -155.10 -39.28 z"
        class:highlighted={activeCategory === 'benevolence-dependability'}
      />
      <path
        data-category="universalism-concern"
        d="M 0,0 L -98.27,-126.26 A 160 160 0 0 0 -133.95 -87.51 z"
        class:highlighted={activeCategory === 'universalism-concern'}
      />
      <path
        data-category="universalism-nature"
        d="M 0,0 L -51.95,-151.33 A 160 160 0 0 0 -98.27 -126.26 z"
        class:highlighted={activeCategory === 'universalism-nature'}
      />
      <path
        data-category="universalism-tolerance"
        d="M 0,0 L 0,-160 A 160 160 0 0 0 -51.95 -151.33 z"
        class:highlighted={activeCategory === 'universalism-tolerance'}
      />
    </g>

    <!-- Proportional Value Fill Bars (rendered when values prop is provided) -->
    {#if values && values.length >= 19}
      <g class="filled-bars">
        {#each SLICES as s}
          <path
            d={getWedgePath(s.x1, s.y1, s.x2, s.y2, s.sweep, s.id)}
            style="fill: {s.color}; stroke: {s.color};"
            class="fill-wedge"
            class:active-wedge={activeCategory === s.id || activeCategory === s.quadrant}
          />
        {/each}
      </g>
    {/if}

    <!-- Labels -->
    <g class="labels">
      <!-- Outer curved quadrant labels -->
      <path id="pathOpennessToChange" d="M 0,-166 A 166 166 0 0 1 166 0" fill="none" />
      <text text-anchor="middle" class="quadrant-text">
        <textPath href="#pathOpennessToChange" startOffset="96.06">Openness to change</textPath>
      </text>

      <path id="pathSelfEnhancement" d="M 108.10,138.89 A 176 176 0 0 0 156.82 -79.90" fill="none" />
      <text text-anchor="middle" class="quadrant-text">
        <textPath href="#pathSelfEnhancement" startOffset="116.40">Self-enhancement</textPath>
      </text>

      <path id="pathConservation" d="M -170.61,43.21 A 176 176 0 0 0 124.45 124.45" fill="none" />
      <text text-anchor="middle" class="quadrant-text">
        <textPath href="#pathConservation" startOffset="174.61">Conservation</textPath>
      </text>

      <path id="pathSelfTranscendence" d="M -160.92,40.75 A 166 166 0 0 1 0 -166" fill="none" />
      <text text-anchor="middle" class="quadrant-text">
        <textPath href="#pathSelfTranscendence" startOffset="150.95">Self-transcendence</textPath>
      </text>

      <!-- Inner curved value group prefixes -->
      <path id="pathSelfDirection" d="M 0,-146 A 146 146 0 0 1 0 146" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathSelfDirection" startOffset="48.28">Self-direction:</textPath>
      </text>

      <path id="pathPower" d="M 114.77,105.66 A 156 156 0 0 0 156 0" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathPower" startOffset="51.59">Power:</textPath>
      </text>

      <path id="pathSecurity" d="M -25.68,153.87 A 156 156 0 0 0 156 0" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathSecurity" startOffset="51.59">Security:</textPath>
      </text>

      <path id="pathConformity" d="M -142.86,62.66 A 156 156 0 0 0 156 0" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathConformity" startOffset="51.59">Conformity:</textPath>
      </text>

      <path id="pathBenevolence" d="M -145.50,12.06 A 146 146 0 0 1 0 -146" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathBenevolence" startOffset="48.28">Benevolence:</textPath>
      </text>

      <path id="pathUniversalism" d="M -122.23,-79.85 A 146 146 0 0 1 0 -146" fill="none" />
      <text text-anchor="middle" class="label-text">
        <textPath href="#pathUniversalism" startOffset="72.42">Universalism:</textPath>
      </text>

      <!-- Radial slice value labels -->
      <text transform="translate(134 5) rotate(-80.53 -134 -5)" text-anchor="end" class="label-text">thought</text>
      <text transform="translate(134 5) rotate(-61.58 -134 -5)" text-anchor="end" class="label-text">action</text>
      <text transform="translate(155 5) rotate(-42.63 -155 -5)" text-anchor="end" class="label-text">Stimulation</text>
      <text transform="translate(155 5) rotate(-23.68 -155 -5)" text-anchor="end" class="label-text">Hedonism</text>
      <text transform="translate(155 5) rotate(-4.74 -155 -5)" text-anchor="end" class="label-text">Achievement</text>
      <text transform="translate(134 5) rotate(14.21 -134 -5)" text-anchor="end" class="label-text">dominance</text>
      <text transform="translate(134 5) rotate(33.16 -134 -5)" text-anchor="end" class="label-text">resources</text>
      <text transform="translate(155 5) rotate(52.11 -155 -5)" text-anchor="end" class="label-text">Face</text>
      <text transform="translate(134 5) rotate(71.05 -134 -5)" text-anchor="end" class="label-text">personal</text>
      <text transform="translate(-134 5) rotate(-90 134 -5)" text-anchor="start" class="label-text">societal</text>
      <text transform="translate(-155 5) rotate(-71.05 155 -5)" text-anchor="start" class="label-text">Tradition</text>
      <text transform="translate(-134 5) rotate(-52.11 134 -5)" text-anchor="start" class="label-text">rules</text>
      <text transform="translate(-134 5) rotate(-33.16 134 -5)" text-anchor="start" class="label-text">interpersonal</text>
      <text transform="translate(-155 5) rotate(-14.21 155 -5)" text-anchor="start" class="label-text">Humility</text>
      <text transform="translate(-134 5) rotate(4.74 134 -5)" text-anchor="start" class="label-text">caring</text>
      <text transform="translate(-134 5) rotate(23.68 134 -5)" text-anchor="start" class="label-text">dependability</text>
      <text transform="translate(-134 5) rotate(42.63 134 -5)" text-anchor="start" class="label-text">concern</text>
      <text transform="translate(-134 5) rotate(61.58 134 -5)" text-anchor="start" class="label-text">nature</text>
      <text transform="translate(-134 5) rotate(80.53 134 -5)" text-anchor="start" class="label-text">tolerance</text>
    </g>

    <!-- Outlines -->
    <g class="outline">
      <circle cx="0" cy="0" r="160" fill="none" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="0" y2="-160" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="46.11" y2="-134.31" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="98.27" y2="-126.26" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="133.95" y2="-87.51" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="155.10" y2="-39.28" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="159.45" y2="13.21" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="130.04" y2="57.04" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="117.72" y2="108.37" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="76.15" y2="140.72" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="23.37" y2="140.06" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-26.34" y2="157.82" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-76.15" y2="140.72" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-104.47" y2="96.17" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-146.52" y2="64.27" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-159.45" y2="13.21" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-137.65" y2="-34.86" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-133.94" y2="-87.51" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-87.22" y2="-112.06" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="0" x2="-46.11" y2="-134.31" stroke="#333333" stroke-width="1" />

      <circle cx="0" cy="0" r="180" fill="none" stroke="#333333" stroke-width="1" />
      <line x1="0" y1="-160" x2="0" y2="-180" stroke="#333333" stroke-width="1" />
      <line x1="146.52" y1="-64.27" x2="164.84" y2="-72.30" stroke="#333333" stroke-width="1" />
      <line x1="98.27" y1="126.26" x2="110.56" y2="142.05" stroke="#333333" stroke-width="1" />
      <line x1="-155.10" y1="39.28" x2="-174.49" y2="44.19" stroke="#333333" stroke-width="1" />
    </g>

    <!-- Invisible Interaction Layer -->
    <g class="interaction">
      <!-- Outer 4 quadrants -->
      <path
        d="M 0,0 L 0,-180 A 180 180 0 0 1 164.84 -72.31 z"
        role="button"
        tabindex="0"
        aria-label="Openness to change"
        onmouseenter={() => setActive('openness-to-change')}
        onclick={() => handleClick('openness-to-change')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('openness-to-change')}
      />
      <path
        d="M 0,0 L 164.84,-72.31 A 180 180 0 0 1 110.56 142.05 z"
        role="button"
        tabindex="0"
        aria-label="Self-enhancement"
        onmouseenter={() => setActive('self-enhancement')}
        onclick={() => handleClick('self-enhancement')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('self-enhancement')}
      />
      <path
        d="M 0,0 L 110.56,142.05 A 180 180 0 0 1 -174.49 44.19 z"
        role="button"
        tabindex="0"
        aria-label="Conservation"
        onmouseenter={() => setActive('conservation')}
        onclick={() => handleClick('conservation')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('conservation')}
      />
      <path
        d="M 0,0 L -174.49,44.19 A 180 180 0 0 1 0,-180 z"
        role="button"
        tabindex="0"
        aria-label="Self-transcendence"
        onmouseenter={() => setActive('self-transcendence')}
        onclick={() => handleClick('self-transcendence')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('self-transcendence')}
      />

      <!-- Inner 19 values -->
      <path
        d="M 0,0 L 0,-160 A 160 160 0 0 1 51.95 -151.33 z"
        role="button"
        tabindex="0"
        aria-label="Self-direction: thought"
        onmouseenter={() => setActive('self-direction-thought')}
        onclick={() => handleClick('self-direction-thought')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('self-direction-thought')}
      />
      <path
        d="M 0,0 L 51.95,-151.33 A 160 160 0 0 1 98.27 -126.26 z"
        role="button"
        tabindex="0"
        aria-label="Self-direction: action"
        onmouseenter={() => setActive('self-direction-action')}
        onclick={() => handleClick('self-direction-action')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('self-direction-action')}
      />
      <path
        d="M 0,0 L 98.27,-126.26 A 160 160 0 0 1 133.95 -87.51 z"
        role="button"
        tabindex="0"
        aria-label="Stimulation"
        onmouseenter={() => setActive('stimulation')}
        onclick={() => handleClick('stimulation')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('stimulation')}
      />
      <path
        d="M 0,0 L 133.95,-87.51 A 160 160 0 0 1 155.10 -39.28 z"
        role="button"
        tabindex="0"
        aria-label="Hedonism"
        onmouseenter={() => setActive('hedonism')}
        onclick={() => handleClick('hedonism')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('hedonism')}
      />
      <path
        d="M 0,0 L 155.10,-39.28 A 160 160 0 0 1 159.45 13.21 z"
        role="button"
        tabindex="0"
        aria-label="Achievement"
        onmouseenter={() => setActive('achievement')}
        onclick={() => handleClick('achievement')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('achievement')}
      />
      <path
        d="M 0,0 L 159.45,13.21 A 160 160 0 0 1 146.52 64.27 z"
        role="button"
        tabindex="0"
        aria-label="Power: dominance"
        onmouseenter={() => setActive('power-dominance')}
        onclick={() => handleClick('power-dominance')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('power-dominance')}
      />
      <path
        d="M 0,0 L 146.42,64.27 A 160 160 0 0 1 117.72 108.37 z"
        role="button"
        tabindex="0"
        aria-label="Power: resources"
        onmouseenter={() => setActive('power-resources')}
        onclick={() => handleClick('power-resources')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('power-resources')}
      />
      <path
        d="M 0,0 L 117.72,108.37 A 160 160 0 0 1 76.15 140.72 z"
        role="button"
        tabindex="0"
        aria-label="Face"
        onmouseenter={() => setActive('face')}
        onclick={() => handleClick('face')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('face')}
      />
      <path
        d="M 0,0 L 76.15,140.72 A 160 160 0 0 1 26.33 157.82 z"
        role="button"
        tabindex="0"
        aria-label="Security: personal"
        onmouseenter={() => setActive('security-personal')}
        onclick={() => handleClick('security-personal')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('security-personal')}
      />
      <path
        d="M 0,0 L 26.33,157.82 A 160 160 0 0 1 -26.33 157.82 z"
        role="button"
        tabindex="0"
        aria-label="Security: societal"
        onmouseenter={() => setActive('security-societal')}
        onclick={() => handleClick('security-societal')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('security-societal')}
      />
      <path
        d="M 0,0 L -76.15,140.72 A 160 160 0 0 0 -26.33 157.82 z"
        role="button"
        tabindex="0"
        aria-label="Tradition"
        onmouseenter={() => setActive('tradition')}
        onclick={() => handleClick('tradition')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('tradition')}
      />
      <path
        d="M 0,0 L -117.72,108.37 A 160 160 0 0 0 -76.15 140.72 z"
        role="button"
        tabindex="0"
        aria-label="Conformity: rules"
        onmouseenter={() => setActive('conformity-rules')}
        onclick={() => handleClick('conformity-rules')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('conformity-rules')}
      />
      <path
        d="M 0,0 L -146.52,64.27 A 160 160 0 0 0 -117.72 108.37 z"
        role="button"
        tabindex="0"
        aria-label="Conformity: interpersonal"
        onmouseenter={() => setActive('conformity-interpersonal')}
        onclick={() => handleClick('conformity-interpersonal')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('conformity-interpersonal')}
      />
      <path
        d="M 0,0 L -159.45,13.21 A 160 160 0 0 0 -146.52 64.27 z"
        role="button"
        tabindex="0"
        aria-label="Humility"
        onmouseenter={() => setActive('humility')}
        onclick={() => handleClick('humility')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('humility')}
      />
      <path
        d="M 0,0 L -155.10,-39.28 A 160 160 0 0 0 -159.45 13.21 z"
        role="button"
        tabindex="0"
        aria-label="Benevolence: caring"
        onmouseenter={() => setActive('benevolence-caring')}
        onclick={() => handleClick('benevolence-caring')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('benevolence-caring')}
      />
      <path
        d="M 0,0 L -133.95,-87.51 A 160 160 0 0 0 -155.10 -39.28 z"
        role="button"
        tabindex="0"
        aria-label="Benevolence: dependability"
        onmouseenter={() => setActive('benevolence-dependability')}
        onclick={() => handleClick('benevolence-dependability')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('benevolence-dependability')}
      />
      <path
        d="M 0,0 L -98.27,-126.26 A 160 160 0 0 0 -133.95 -87.51 z"
        role="button"
        tabindex="0"
        aria-label="Universalism: concern"
        onmouseenter={() => setActive('universalism-concern')}
        onclick={() => handleClick('universalism-concern')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('universalism-concern')}
      />
      <path
        d="M 0,0 L -51.95,-151.33 A 160 160 0 0 0 -98.27 -126.26 z"
        role="button"
        tabindex="0"
        aria-label="Universalism: nature"
        onmouseenter={() => setActive('universalism-nature')}
        onclick={() => handleClick('universalism-nature')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('universalism-nature')}
      />
      <path
        d="M 0,0 L 0,-160 A 160 160 0 0 0 -51.95 -151.33 z"
        role="button"
        tabindex="0"
        aria-label="Universalism: tolerance"
        onmouseenter={() => setActive('universalism-tolerance')}
        onclick={() => handleClick('universalism-tolerance')}
        onkeydown={(e) => e.key === 'Enter' && handleClick('universalism-tolerance')}
      />
    </g>
  </svg>

  <!-- Value Description Caption under the SVG -->
  <div class="caption-container">
    {#if activeCategory && DESCRIPTIONS[activeCategory]}
      <div class="caption-header">
        <span class="caption-title">{DESCRIPTIONS[activeCategory].title}</span>
        {#if getCategoryPct(activeCategory) !== null}
          <span
            class="caption-pct"
            style={getBadgeStyle(activeCategory)}
          >
            {getCategoryPct(activeCategory)}%
          </span>
        {/if}
      </div>
      <div class="caption-desc">{DESCRIPTIONS[activeCategory].italic}</div>
    {:else}
      <div class="caption-placeholder">
        <span class="desktop-instruction">Hover any value to see its meaning</span>
        <span class="mobile-instruction">Tap any value to see its meaning</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .circle-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    max-width: 480px;
    margin: 0 auto;
    user-select: none;
  }

  .continuum-svg {
    width: 100%;
    height: auto;
    max-width: 460px;
    display: block;
  }

  .backlights path {
    fill: transparent;
    transition: fill 0.15s ease;
  }

  .backlights path.highlighted {
    fill: rgba(255, 255, 255, 0.12);
  }

  .filled-bars {
    pointer-events: none;
  }

  .fill-wedge {
    opacity: 0.7;
    stroke: none;
    transition: opacity 0.15s ease;
  }

  .fill-wedge.active-wedge {
    opacity: 1;
    stroke: none;
  }

  .quadrant-text {
    font-size: 9px;
    font-weight: 600;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
    fill: #bbbbbb;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .label-text {
    font-size: 8.5px;
    font-weight: 500;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
    fill: #ffffff;
  }

  .interaction path {
    fill: transparent;
    cursor: pointer;
  }

  .interaction path:focus {
    outline: none;
  }

  /* Description Box */
  .caption-container {
    min-height: 4.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0.75rem 1rem 0;
    width: 100%;
  }

  .caption-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
    flex-wrap: wrap;
  }

  .caption-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #ffffff;
  }

  .caption-pct {
    font-size: 0.8rem;
    font-weight: 700;
    padding: 0.08rem 0.45rem;
    border-radius: 9999px;
    font-variant-numeric: tabular-nums;
  }

  .caption-desc {
    font-size: 0.9rem;
    color: #d0d0d0;
    line-height: 1.5;
  }

  .caption-placeholder {
    font-size: 0.85rem;
    color: #999999;
  }

  .mobile-instruction {
    display: none;
  }

  .desktop-instruction {
    display: inline;
  }

  @media (max-width: 768px), (hover: none) {
    .desktop-instruction {
      display: none;
    }
    .mobile-instruction {
      display: inline;
    }
  }
</style>
