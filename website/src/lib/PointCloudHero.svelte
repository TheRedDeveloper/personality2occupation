<script lang="ts">
  import { onMount } from 'svelte';
  import { asset } from '$app/paths';
  import { mdiMagnify, mdiClose } from '#lib/icons.ts';

  const DIMENSION_NAMES = [
    'Openness',                   // 0
    'Conscientiousness',          // 1
    'Extraversion',               // 2
    'Agreeableness',              // 3
    'Neuroticism',                // 4
    'Self-direction: thought',    // 5
    'Self-direction: action',     // 6
    'Stimulation',                // 7
    'Hedonism',                   // 8
    'Achievement',                // 9
    'Power: dominance',           // 10
    'Power: resources',           // 11
    'Face',                       // 12
    'Security: personal',         // 13
    'Security: societal',         // 14
    'Tradition',                  // 15
    'Conformity: rules',          // 16
    'Conformity: interpersonal',   // 17
    'Humility',                   // 18
    'Benevolence: caring',        // 19
    'Benevolence: dependability', // 20
    'Universalism: concern',      // 21
    'Universalism: nature',       // 22
    'Universalism: tolerance'     // 23
  ];

  const SEGMENT_COLORS: Record<string, string> = {
    'Education, Academia & Scientific Research': '#3D5AFE',
    'Public Service, Law, Defense & Civil Operations': '#FF1744',
    'Creative Arts, Design & Entertainment': '#D500F9',
    'Healthcare, Clinical Practice & Wellness Services': '#00E676',
    'Corporate Strategy, Finance & Commercial Operations': '#FFD600',
    'Technology, Software & Engineering Design': '#00E5FF',
    'Skilled Trades, Construction & Extraction': '#A1887F',
    'Writing, Journalism, Publishing & Media': '#FF9100'
  };

  // High-accuracy rational approximation of inverse standard normal CDF (probit)
  function probit(p: number): number {
    if (p <= 0.0001) return -3.72;
    if (p >= 0.9999) return 3.72;

    const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];

    const p_low = 0.02425;
    const p_high = 1 - p_low;

    if (p < p_low) {
      const q = Math.sqrt(-2 * Math.log(p));
      return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
    } else if (p <= p_high) {
      const q = p - 0.5;
      const r = q * q;
      return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
    } else {
      const q = Math.sqrt(-2 * Math.log(1 - p));
      return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
    }
  }

  function quantileTransformToNormal(values: number[]): number[] {
    const n = values.length;
    const indices = Array.from({ length: n }, (_, i) => i).sort((a, b) => values[a] - values[b]);
    const out = new Array<number>(n);
    for (let r = 0; r < n; r++) {
      const p = (r + 0.5) / n;
      out[indices[r]] = probit(p);
    }
    return out;
  }

  function computeRadii(variances: number[], baseRadius: number = 1.8): number[] {
    let minV = Infinity, maxV = -Infinity;
    for (const v of variances) {
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
    const span = Math.max(maxV - minV, 1e-6);
    return variances.map(v => {
      const normV = (v - minV) / span;
      const scale = 0.5 + 1.5 * normV;
      return Number((baseRadius * scale).toFixed(2));
    });
  }

  // Animation & Layout configuration
  const PLOT_LEFT = 55;
  const PLOT_TOP = 25;
  const PLOT_SIZE = 440;
  const PLOT_RIGHT = PLOT_LEFT + PLOT_SIZE; // 495
  const PLOT_BOTTOM = PLOT_TOP + PLOT_SIZE; // 465
  const CENTER_X = PLOT_LEFT + PLOT_SIZE / 2; // 275
  const CENTER_Y = PLOT_TOP + PLOT_SIZE / 2;  // 245
  const PIXELS_PER_SD = PLOT_SIZE / 5.0; // 88.0 px per SD

  const TICKS = [-2, -1, 1, 2];

  interface PointRecord {
    t: string;
    c: string;
    o: number;
    coordsPx: number[]; // 24 precomputed pixel offsets (Z-score * PIXELS_PER_SD)
    radii: number[];    // 24 precomputed ellipse radii
    screenX: number;
    screenY: number;
    screenRx: number;
    screenRy: number;
  }

  let points = $state<PointRecord[]>([]);
  let pointsCount = 0;
  let loading = $state(true);
  let error = $state<string | null>(null);

  let containerEl: HTMLElement | null = null;
  let isScrolling = $state(false);

  // Search state
  let searchQuery = $state('');
  let trimmedQuery = $derived(searchQuery.trim().toLowerCase());
  let isSearching = $derived(trimmedQuery.length > 0);

  let matchingIndices = $derived.by(() => {
    if (!isSearching) return new Set<number>();
    const matches = new Set<number>();
    for (let i = 0; i < pointsCount; i++) {
      if (points[i].t.toLowerCase().includes(trimmedQuery)) {
        matches.add(i);
      }
    }
    return matches;
  });

  interface MatchItem {
    idx: number;
    pt: PointRecord;
  }

  let matchingList = $derived.by<MatchItem[]>(() => {
    if (!isSearching) return [];
    const list: MatchItem[] = [];
    for (const idx of matchingIndices) {
      if (points[idx]) {
        list.push({ idx, pt: points[idx] });
      }
    }
    return list;
  });

  let matchTextElements: Record<number, SVGTextElement> = {};

  // Active Dimensions on Screen
  let currentXDim = $state(3);  // Agreeableness initially
  let currentYDim = $state(13); // Security: personal initially

  // Current Transition State
  type AxisType = 'x' | 'y';
  let activeTransitionAxis = $state<AxisType>('y'); // 'y' = vertical rotation, 'x' = horizontal rotation
  let transitionFromDim = $state(13);
  let transitionToDim = $state(14);
  let isTransitioning = $state(false);

  let cosAngle = $state(1.0);
  let sinAngle = $state(0.0);

  // Hover state
  let hoveredPoint = $state<PointRecord | null>(null);
  let hoveredCx = $state(CENTER_X);
  let hoveredCy = $state(CENTER_Y);
  let hoveredRx = $state(1.8);
  let hoveredRy = $state(1.8);
  let mouseX = $state(0);
  let mouseY = $state(0);

  let ellipseElements: SVGEllipseElement[] = [];

  function formatTickLabel(k: number): string {
    if (k === 0) return '0';
    if (k > 0) return `+${k}σ`;
    return `${k}σ`;
  }

  function easeInOutCubic(t: number): number {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function getSvgCoords(clientX: number, clientY: number): { svgX: number; svgY: number; domX: number; domY: number } {
    if (!containerEl) return { svgX: 0, svgY: 0, domX: 0, domY: 0 };
    const rect = containerEl.getBoundingClientRect();
    const domX = clientX - rect.left;
    const domY = clientY - rect.top;
    // Map from rendered DOM pixels to SVG viewBox (0 0 520 520) coordinates
    const svgX = (domX / rect.width) * 520;
    const svgY = (domY / rect.height) * 520;
    return { svgX, svgY, domX, domY };
  }

  function updateHoveredFromSvgCoords(svgX: number, svgY: number, radiusSvg: number = 20) {
    let closest: PointRecord | null = null;
    let minD2 = radiusSvg * radiusSvg;
    for (let i = 0; i < pointsCount; i++) {
      const pt = points[i];
      const dx = pt.screenX - svgX;
      const dy = pt.screenY - svgY;
      const d2 = dx * dx + dy * dy;
      if (d2 < minD2) {
        minD2 = d2;
        closest = pt;
      }
    }
    hoveredPoint = closest;
    if (closest) {
      hoveredCx = closest.screenX;
      hoveredCy = closest.screenY;
      hoveredRx = closest.screenRx;
      hoveredRy = closest.screenRy;
    }
  }

  function handlePointerDown(e: PointerEvent) {
    const coords = getSvgCoords(e.clientX, e.clientY);
    mouseX = coords.domX;
    mouseY = coords.domY;
    updateHoveredFromSvgCoords(coords.svgX, coords.svgY, e.pointerType === 'touch' ? 28 : 18);
  }

  function handlePointerMove(e: PointerEvent) {
    const coords = getSvgCoords(e.clientX, e.clientY);
    mouseX = coords.domX;
    mouseY = coords.domY;
    updateHoveredFromSvgCoords(coords.svgX, coords.svgY, e.pointerType === 'touch' ? 28 : 18);
  }

  function handlePointerLeave() {
    hoveredPoint = null;
  }

  onMount(() => {
    let unmounted = false;
    let animFrameId: number;
    let isVisible = true;
    let scrollTimeout: any = null;

    // Detect mobile touch device
    const isMobileDevice =
      window.innerWidth < 840 ||
      'ontouchstart' in window ||
      (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);

    function onWindowScroll() {
      if (!isScrolling) isScrolling = true;
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        isScrolling = false;
      }, 100);
    }
    window.addEventListener('scroll', onWindowScroll, { passive: true });

    let observer: IntersectionObserver | null = null;
    if (containerEl && typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver(
        ([entry]) => {
          isVisible = entry.isIntersecting;
        },
        { rootMargin: '80px' }
      );
      observer.observe(containerEl);
    }

    // Sequence of seen axes
    // Initially Agreeableness (3) and Security: personal (13)
    let seenHistory: number[] = [3, 13];

    // Predefined sequence requested by the user:
    // 0: Security: personal (13) -> Security: societal (14)  [Vertical]
    // 1: Agreeableness (3) -> Stimulation (7)               [Horizontal]
    // 2: Security: societal (14) -> Openness (0)            [Vertical]
    // 3: Stimulation (7) -> Tradition (15)                  [Horizontal]
    // 4: Openness (0) -> Achievement (9)                    [Vertical]
    const PREDEFINED_QUEUE: { axis: AxisType; targetDim: number }[] = [
      { axis: 'y', targetDim: 14 },
      { axis: 'x', targetDim: 7 },
      { axis: 'y', targetDim: 0 },
      { axis: 'x', targetDim: 15 },
      { axis: 'y', targetDim: 9 }
    ];

    let predefinedIndex = 0;
    let lastRotatedAxis: AxisType = 'x'; // so next is 'y'

    function getNextTransition(currX: number, currY: number): { axis: AxisType; fromDim: number; toDim: number } {
      if (predefinedIndex < PREDEFINED_QUEUE.length) {
        const item = PREDEFINED_QUEUE[predefinedIndex++];
        const fromDim = item.axis === 'y' ? currY : currX;
        seenHistory.push(item.targetDim);
        lastRotatedAxis = item.axis;
        return { axis: item.axis, fromDim, toDim: item.targetDim };
      }

      // Dynamic continuation: alternate axis every time
      const nextAxis: AxisType = lastRotatedAxis === 'y' ? 'x' : 'y';
      lastRotatedAxis = nextAxis;

      const fromDim = nextAxis === 'y' ? currY : currX;
      const otherDim = nextAxis === 'y' ? currX : currY;

      // Pick from unseen dimensions
      const unseen: number[] = [];
      for (let i = 0; i < 24; i++) {
        if (!seenHistory.includes(i) && i !== otherDim) {
          unseen.push(i);
        }
      }

      let nextDim: number;
      if (unseen.length > 0) {
        // Pick random from unseen
        nextDim = unseen[Math.floor(Math.random() * unseen.length)];
        seenHistory.push(nextDim);
      } else {
        // All 24 dimensions have been seen!
        // "pick a random one from the 5 that haven't been seen in the longest time and put them on the end of the list again"
        const candidates = seenHistory.filter(d => d !== otherDim && d !== fromDim).slice(0, 5);
        nextDim = candidates[Math.floor(Math.random() * candidates.length)];
        seenHistory = seenHistory.filter(d => d !== nextDim);
        seenHistory.push(nextDim);
      }

      return { axis: nextAxis, fromDim, toDim: nextDim };
    }

    async function loadData() {
      try {
        const { parquetRead } = await import('hyparquet');

        const [parquetRes, segRes] = await Promise.all([
          fetch(asset('data.parquet')),
          fetch(asset('segment_to_clusters.json'))
        ]);

        if (!parquetRes.ok) throw new Error(`data.parquet HTTP ${parquetRes.status}`);
        if (!segRes.ok) throw new Error(`segment_to_clusters.json HTTP ${segRes.status}`);

        const [parquetBuffer, segmentData] = await Promise.all([
          parquetRes.arrayBuffer(),
          segRes.json()
        ]);

        if (unmounted) return;

        const clusterToSegment = new Map<string, string>();
        for (const [segment, clusters] of Object.entries(segmentData as Record<string, string[]>)) {
          for (const cluster of clusters) {
            clusterToSegment.set(cluster, segment);
          }
        }

        await parquetRead({
          file: parquetBuffer,
          rowFormat: 'object',
          onComplete: (rows: any[]) => {
            if (unmounted) return;

            const n = rows.length;

            function computeDim(d: number) {
              const normZ = quantileTransformToNormal(rows.map(r => r.mean[d]));
              const radii = computeRadii(rows.map(r => r.variance[d]));
              const px = normZ.map(z => z * PIXELS_PER_SD);
              return { px, radii };
            }

            const allCoordsPx: number[][] = new Array(24);
            const allRadii: number[][] = new Array(24);

            // Compute only the initial 2 visible dimensions immediately (Dim 3 & Dim 13)
            const d3 = computeDim(3);
            allCoordsPx[3] = d3.px;
            allRadii[3] = d3.radii;

            const d13 = computeDim(13);
            allCoordsPx[13] = d13.px;
            allRadii[13] = d13.radii;

            // Calculate sample count opacities
            const sampleCounts = rows.map(r => Number(r.sample_count));
            let minUsers = Infinity;
            for (const sc of sampleCounts) {
              if (sc < minUsers) minUsers = sc;
            }

            const opacities = sampleCounts.map(sc => {
              const satVal = 1 - Math.exp(-Math.max(sc - minUsers, 0) / 20.0);
              return Number((0.15 + (1.0 - 0.15) * satVal).toFixed(2));
            });

            // Build PointRecords
            const parsedPoints: PointRecord[] = rows.map((r, i) => {
              const title = r.canonical_occupation;
              const segment = clusterToSegment.get(title) || 'Unassigned';
              const color = SEGMENT_COLORS[segment] || '#888888';

              const coordsPxForPoint = new Array<number>(24);
              const radiiForPoint = new Array<number>(24);
              coordsPxForPoint[3] = allCoordsPx[3][i];
              coordsPxForPoint[13] = allCoordsPx[13][i];
              radiiForPoint[3] = allRadii[3][i];
              radiiForPoint[13] = allRadii[13][i];

              const initialSx = CENTER_X + coordsPxForPoint[3];
              const initialSy = CENTER_Y - coordsPxForPoint[13];

              return {
                t: title,
                c: color,
                o: opacities[i],
                coordsPx: coordsPxForPoint,
                radii: radiiForPoint,
                screenX: initialSx,
                screenY: initialSy,
                screenRx: radiiForPoint[3],
                screenRy: radiiForPoint[13]
              };
            });

            parsedPoints.sort((a, b) => a.o - b.o);
            points = parsedPoints;
            pointsCount = points.length;
            loading = false;

            // Compute remaining dimensions asynchronously during the initial 2-second hold
            const computeRemaining = () => {
              if (unmounted) return;
              for (let d = 0; d < 24; d++) {
                if (d === 3 || d === 13) continue;
                const res = computeDim(d);
                allCoordsPx[d] = res.px;
                allRadii[d] = res.radii;
                for (let i = 0; i < n; i++) {
                  parsedPoints[i].coordsPx[d] = res.px[i];
                  parsedPoints[i].radii[d] = res.radii[i];
                }
              }
            };

            if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
              (window as any).requestIdleCallback(computeRemaining);
            } else {
              setTimeout(computeRemaining, 50);
            }

            startAnimationLoop();
          }
        });
      } catch (err: any) {
        if (!unmounted) {
          error = err.message || 'Error processing career data';
          loading = false;
        }
      }
    }

    function startAnimationLoop() {
      const HOLD_MS = 2800; // Hold time at rest
      const ROT_MS = 2000;  // Rotation transition time

      let currentStep: { axis: AxisType; fromDim: number; toDim: number } | null = null;
      let phaseStartTime = performance.now();
      let state: 'holding' | 'rotating' = 'holding';
      let lastFrameTime = 0;

      function renderFrame(now: number) {
        if (unmounted) return;

        if (!isVisible) {
          animFrameId = requestAnimationFrame(renderFrame);
          return;
        }

        const targetInterval = isMobileDevice
          ? (isScrolling ? 50 : 33.3)
          : 16.6;

        if (now - lastFrameTime < targetInterval) {
          animFrameId = requestAnimationFrame(renderFrame);
          return;
        }
        lastFrameTime = now;

        const elapsed = now - phaseStartTime;

        if (state === 'holding') {
          if (elapsed >= HOLD_MS) {
            // Initiate next rotation
            currentStep = getNextTransition(currentXDim, currentYDim);
            activeTransitionAxis = currentStep.axis;
            transitionFromDim = currentStep.fromDim;
            transitionToDim = currentStep.toDim;
            isTransitioning = true;
            state = 'rotating';
            phaseStartTime = now;
          }
          animFrameId = requestAnimationFrame(renderFrame);
          return;
        }

        // state === 'rotating'
        let t = Math.min(elapsed / ROT_MS, 1.0);
        let progress = easeInOutCubic(t);

        const theta = progress * (Math.PI / 2);
        const cos = Math.cos(theta);
        const sin = Math.sin(theta);

        cosAngle = cos;
        sinAngle = sin;

        if (!currentStep) return;

        const isYRotation = currentStep.axis === 'y'; // Vertical rotation around X
        const fromD = currentStep.fromDim;
        const toD = currentStep.toDim;

        // Update each dot's screen position and radii
        for (let i = 0; i < pointsCount; i++) {
          const pt = points[i];
          const el = ellipseElements[i];

          if (isYRotation) {
            // Vertical rotation: X is static, Y moves from fromD to toD
            const staticX = CENTER_X + pt.coordsPx[currentXDim];
            const yProj = pt.coordsPx[fromD] * cos + pt.coordsPx[toD] * sin;
            const screenY = CENTER_Y - yProj;
            const rx = pt.radii[currentXDim];
            const ry = pt.radii[fromD] * (1 - progress) + pt.radii[toD] * progress;

            pt.screenX = staticX;
            pt.screenY = screenY;
            pt.screenRx = rx;
            pt.screenRy = ry;

            if (el) {
              if (el.cy && el.cy.baseVal) {
                el.cy.baseVal.value = screenY;
                el.ry.baseVal.value = ry;
              } else {
                el.setAttribute('cy', screenY.toFixed(1));
                el.setAttribute('ry', ry.toFixed(1));
              }
            }
          } else {
            // Horizontal rotation: Y is static, X moves from fromD to toD
            const xProj = pt.coordsPx[fromD] * cos + pt.coordsPx[toD] * sin;
            const screenX = CENTER_X + xProj;
            const staticY = CENTER_Y - pt.coordsPx[currentYDim];
            const rx = pt.radii[fromD] * (1 - progress) + pt.radii[toD] * progress;
            const ry = pt.radii[currentYDim];

            pt.screenX = screenX;
            pt.screenY = staticY;
            pt.screenRx = rx;
            pt.screenRy = ry;

            if (el) {
              if (el.cx && el.cx.baseVal) {
                el.cx.baseVal.value = screenX;
                el.rx.baseVal.value = rx;
              } else {
                el.setAttribute('cx', screenX.toFixed(1));
                el.setAttribute('rx', rx.toFixed(1));
              }
            }
          }
        }

        // Keep match labels positioned during animation
        if (isSearching) {
          for (const idx of matchingIndices) {
            const txtEl = matchTextElements[idx];
            if (txtEl) {
              const pt = points[idx];
              txtEl.setAttribute('x', pt.screenX.toFixed(1));
              txtEl.setAttribute('y', (pt.screenY - pt.screenRy - 4).toFixed(1));
            }
          }
        }

        // If hovered point active, update its position
        if (hoveredPoint) {
          hoveredCx = hoveredPoint.screenX;
          hoveredCy = hoveredPoint.screenY;
          hoveredRx = hoveredPoint.screenRx;
          hoveredRy = hoveredPoint.screenRy;
        }

        if (t >= 1.0) {
          // Transition complete!
          if (isYRotation) {
            currentYDim = toD;
          } else {
            currentXDim = toD;
          }
          isTransitioning = false;
          cosAngle = 1.0;
          sinAngle = 0.0;
          state = 'holding';
          phaseStartTime = now;
        }

        animFrameId = requestAnimationFrame(renderFrame);
      }

      animFrameId = requestAnimationFrame(renderFrame);
    }

    loadData();

    return () => {
      unmounted = true;
      if (animFrameId) cancelAnimationFrame(animFrameId);
      if (scrollTimeout) clearTimeout(scrollTimeout);
      window.removeEventListener('scroll', onWindowScroll);
      if (observer) observer.disconnect();
    };
  });
</script>

<div class="hero-plot-wrapper">
  <div
    bind:this={containerEl}
    class="plot-container"
    class:is-scrolling={isScrolling}
    onpointerdown={handlePointerDown}
    onpointermove={handlePointerMove}
    onpointerleave={handlePointerLeave}
    role="region"
    aria-label="Career scatterplot map"
  >
    {#if loading}
      <div class="plot-loading">
        <img src={asset('loading.svg')} alt="Loading" class="loading-icon" width="48" height="48" />
      </div>
    {:else if error}
      <div class="plot-error">Failed to load dataset: {error}</div>
    {:else}
      <svg viewBox="0 0 520 520" class="scatterplot-svg" aria-label="Career compass scatterplot">
        <defs>
          <clipPath id="plot-clip">
            <rect
              x={PLOT_LEFT}
              y={PLOT_TOP}
              width={PLOT_SIZE}
              height={PLOT_SIZE}
            />
          </clipPath>
        </defs>

      <!-- Plot background area -->
      <rect
        x={PLOT_LEFT}
        y={PLOT_TOP}
        width={PLOT_SIZE}
        height={PLOT_SIZE}
        fill="#05070a"
      />

      <!-- ==================== VERTICAL GRID LINES (X-AXIS) ==================== -->
      {#if !isTransitioning || activeTransitionAxis === 'y'}
        <!-- Static Vertical Grid lines when X is invariant -->
        {#each TICKS as k}
          {@const xPos = (CENTER_X + k * PIXELS_PER_SD).toFixed(1)}
          <line
            x1={xPos}
            y1={PLOT_TOP}
            x2={xPos}
            y2={PLOT_BOTTOM}
            stroke="#161d2a"
            stroke-width="1"
          />
        {/each}
      {:else}
        <!-- Contracting Vertical Grid lines (X fromDim -> center) -->
        {#each TICKS as k}
          {@const xPos = (CENTER_X + k * cosAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (cosAngle * cosAngle).toFixed(2)}
          <line
            x1={xPos}
            y1={PLOT_TOP}
            x2={xPos}
            y2={PLOT_BOTTOM}
            stroke="#161d2a"
            stroke-width="1"
            opacity={op}
          />
        {/each}
        <!-- Expanding Vertical Grid lines (X toDim center -> outward) -->
        {#each TICKS as k}
          {@const xPos = (CENTER_X + k * sinAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (sinAngle * sinAngle).toFixed(2)}
          <line
            x1={xPos}
            y1={PLOT_TOP}
            x2={xPos}
            y2={PLOT_BOTTOM}
            stroke="#161d2a"
            stroke-width="1"
            opacity={op}
          />
        {/each}
      {/if}

      <!-- ==================== HORIZONTAL GRID LINES (Y-AXIS) ==================== -->
      {#if !isTransitioning || activeTransitionAxis === 'x'}
        <!-- Static Horizontal Grid lines when Y is invariant -->
        {#each TICKS as k}
          {@const yPos = (CENTER_Y - k * PIXELS_PER_SD).toFixed(1)}
          <line
            x1={PLOT_LEFT}
            y1={yPos}
            x2={PLOT_RIGHT}
            y2={yPos}
            stroke="#161d2a"
            stroke-width="1"
          />
        {/each}
      {:else}
        <!-- Contracting Horizontal Grid lines (Y fromDim -> center) -->
        {#each TICKS as k}
          {@const yPos = (CENTER_Y - k * cosAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (cosAngle * cosAngle).toFixed(2)}
          <line
            x1={PLOT_LEFT}
            y1={yPos}
            x2={PLOT_RIGHT}
            y2={yPos}
            stroke="#161d2a"
            stroke-width="1"
            opacity={op}
          />
        {/each}
        <!-- Expanding Horizontal Grid lines (Y toDim center -> outward) -->
        {#each TICKS as k}
          {@const yPos = (CENTER_Y - k * sinAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (sinAngle * sinAngle).toFixed(2)}
          <line
            x1={PLOT_LEFT}
            y1={yPos}
            x2={PLOT_RIGHT}
            y2={yPos}
            stroke="#161d2a"
            stroke-width="1"
            opacity={op}
          />
        {/each}
      {/if}

      <!-- Center Zero lines (Population Mean, 0 SD - always invariant at center) -->
      <line
        x1={CENTER_X}
        y1={PLOT_TOP}
        x2={CENTER_X}
        y2={PLOT_BOTTOM}
        stroke="#333f52"
        stroke-width="1.5"
      />
      <line
        x1={PLOT_LEFT}
        y1={CENTER_Y}
        x2={PLOT_RIGHT}
        y2={CENTER_Y}
        stroke="#333f52"
        stroke-width="1.5"
      />

      <!-- Outer border frame -->
      <rect
        x={PLOT_LEFT}
        y={PLOT_TOP}
        width={PLOT_SIZE}
        height={PLOT_SIZE}
        fill="none"
        stroke="#242c3b"
        stroke-width="1"
      />

      <!-- ==================== X-AXIS TICKS & LABELS ==================== -->
      {#if !isTransitioning || activeTransitionAxis === 'y'}
        <!-- Static X Ticks -->
        {#each [-2, -1, 0, 1, 2] as k}
          {@const xPos = (CENTER_X + k * PIXELS_PER_SD).toFixed(1)}
          <line
            x1={xPos}
            y1={PLOT_BOTTOM}
            x2={xPos}
            y2={PLOT_BOTTOM + 5}
            stroke="#475569"
            stroke-width="1"
          />
          <text
            x={xPos}
            y={PLOT_BOTTOM + 16}
            fill="#78889b"
            font-size="10"
            font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
            text-anchor="middle"
          >
            {formatTickLabel(k)}
          </text>
        {/each}
        <!-- Static X Title -->
        <text
          x={CENTER_X}
          y={PLOT_BOTTOM + 38}
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
        >
          {DIMENSION_NAMES[currentXDim]}
        </text>
      {:else}
        <!-- Contracting X Ticks (fromDim) -->
        {#each TICKS as k}
          {@const xPos = (CENTER_X + k * cosAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (cosAngle * cosAngle).toFixed(2)}
          {#if cosAngle > 0.05}
            <line
              x1={xPos}
              y1={PLOT_BOTTOM}
              x2={xPos}
              y2={PLOT_BOTTOM + 5}
              stroke="#475569"
              stroke-width="1"
              opacity={op}
            />
            <text
              x={xPos}
              y={PLOT_BOTTOM + 16}
              fill="#78889b"
              font-size="10"
              font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
              text-anchor="middle"
              opacity={op}
            >
              {formatTickLabel(k)}
            </text>
          {/if}
        {/each}
        <!-- Expanding X Ticks (toDim) -->
        {#each TICKS as k}
          {@const xPos = (CENTER_X + k * sinAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (sinAngle * sinAngle).toFixed(2)}
          {#if sinAngle > 0.05}
            <line
              x1={xPos}
              y1={PLOT_BOTTOM}
              x2={xPos}
              y2={PLOT_BOTTOM + 5}
              stroke="#475569"
              stroke-width="1"
              opacity={op}
            />
            <text
              x={xPos}
              y={PLOT_BOTTOM + 16}
              fill="#78889b"
              font-size="10"
              font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
              text-anchor="middle"
              opacity={op}
            >
              {formatTickLabel(k)}
            </text>
          {/if}
        {/each}
        <!-- Fixed Center Tick (0 SD) on X-axis -->
        <line
          x1={CENTER_X}
          y1={PLOT_BOTTOM}
          x2={CENTER_X}
          y2={PLOT_BOTTOM + 5}
          stroke="#475569"
          stroke-width="1"
        />
        <text
          x={CENTER_X}
          y={PLOT_BOTTOM + 16}
          fill="#78889b"
          font-size="10"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
        >
          0
        </text>
        <!-- X-axis Title Crossfade -->
        <text
          x={CENTER_X}
          y={PLOT_BOTTOM + 38}
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
          opacity={(cosAngle * cosAngle).toFixed(2)}
        >
          {DIMENSION_NAMES[transitionFromDim]}
        </text>
        <text
          x={CENTER_X}
          y={PLOT_BOTTOM + 38}
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
          opacity={(sinAngle * sinAngle).toFixed(2)}
        >
          {DIMENSION_NAMES[transitionToDim]}
        </text>
      {/if}

      <!-- ==================== Y-AXIS TICKS & LABELS ==================== -->
      {#if !isTransitioning || activeTransitionAxis === 'x'}
        <!-- Static Y Ticks -->
        {#each [-2, -1, 0, 1, 2] as k}
          {@const yPos = (CENTER_Y - k * PIXELS_PER_SD).toFixed(1)}
          <line
            x1={PLOT_LEFT - 5}
            y1={yPos}
            x2={PLOT_LEFT}
            y2={yPos}
            stroke="#475569"
            stroke-width="1"
          />
          <text
            x={PLOT_LEFT - 8}
            y={yPos}
            fill="#78889b"
            font-size="10"
            font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
            text-anchor="end"
            dominant-baseline="central"
          >
            {formatTickLabel(k)}
          </text>
        {/each}
        <!-- Static Y Title -->
        <text
          x={-CENTER_Y}
          y="16"
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
          transform="rotate(-90)"
        >
          {DIMENSION_NAMES[currentYDim]}
        </text>
      {:else}
        <!-- Contracting Y Ticks (fromDim) -->
        {#each TICKS as k}
          {@const yPos = (CENTER_Y - k * cosAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (cosAngle * cosAngle).toFixed(2)}
          {#if cosAngle > 0.05}
            <line
              x1={PLOT_LEFT - 5}
              y1={yPos}
              x2={PLOT_LEFT}
              y2={yPos}
              stroke="#475569"
              stroke-width="1"
              opacity={op}
            />
            <text
              x={PLOT_LEFT - 8}
              y={yPos}
              fill="#78889b"
              font-size="10"
              font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
              text-anchor="end"
              dominant-baseline="central"
              opacity={op}
            >
              {formatTickLabel(k)}
            </text>
          {/if}
        {/each}
        <!-- Expanding Y Ticks (toDim) -->
        {#each TICKS as k}
          {@const yPos = (CENTER_Y - k * sinAngle * PIXELS_PER_SD).toFixed(1)}
          {@const op = (sinAngle * sinAngle).toFixed(2)}
          {#if sinAngle > 0.05}
            <line
              x1={PLOT_LEFT - 5}
              y1={yPos}
              x2={PLOT_LEFT}
              y2={yPos}
              stroke="#475569"
              stroke-width="1"
              opacity={op}
            />
            <text
              x={PLOT_LEFT - 8}
              y={yPos}
              fill="#78889b"
              font-size="10"
              font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
              text-anchor="end"
              dominant-baseline="central"
              opacity={op}
            >
              {formatTickLabel(k)}
            </text>
          {/if}
        {/each}
        <!-- Fixed Center Tick (0 SD) on Y-axis -->
        <line
          x1={PLOT_LEFT - 5}
          y1={CENTER_Y}
          x2={PLOT_LEFT}
          y2={CENTER_Y}
          stroke="#475569"
          stroke-width="1"
        />
        <text
          x={PLOT_LEFT - 8}
          y={CENTER_Y}
          fill="#78889b"
          font-size="10"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="end"
          dominant-baseline="central"
        >
          0
        </text>
        <!-- Y-axis Title Crossfade -->
        <text
          x={-CENTER_Y}
          y="16"
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
          transform="rotate(-90)"
          opacity={(cosAngle * cosAngle).toFixed(2)}
        >
          {DIMENSION_NAMES[transitionFromDim]}
        </text>
        <text
          x={-CENTER_Y}
          y="16"
          fill="#e6edf3"
          font-size="13"
          font-weight="500"
          font-family="'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
          text-anchor="middle"
          transform="rotate(-90)"
          opacity={(sinAngle * sinAngle).toFixed(2)}
        >
          {DIMENSION_NAMES[transitionToDim]}
        </text>
      {/if}

      <!-- 2,108 Data Points dynamically transformed in 3D orthographic projection -->
      <g clip-path="url(#plot-clip)">
        {#each points as pt, i}
          {@const isMatch = isSearching ? matchingIndices.has(i) : false}
          <ellipse
            bind:this={ellipseElements[i]}
            cx={pt.screenX.toFixed(1)}
            cy={pt.screenY.toFixed(1)}
            rx={pt.screenRx}
            ry={pt.screenRy}
            fill={pt.c}
            opacity={pt === hoveredPoint ? 1 : pt.o}
            stroke={isMatch || pt === hoveredPoint ? '#ffffff' : 'rgba(255, 255, 255, 0.35)'}
            stroke-width={isMatch || pt === hoveredPoint ? 1.8 : 0.35}
            class="scatter-dot"
            role="graphics-symbol"
            aria-label={pt.t}
          />
        {/each}

        <!-- Active Hovered Dot rendered on top with crisp white outline -->
        {#if hoveredPoint}
          <ellipse
            cx={hoveredCx.toFixed(1)}
            cy={hoveredCy.toFixed(1)}
            rx={hoveredRx}
            ry={hoveredRy}
            fill={hoveredPoint.c}
            opacity="1"
            stroke="#ffffff"
            stroke-width="2.2"
            pointer-events="none"
          />
        {/if}

        <!-- Labels on all found dots when searching -->
        {#if isSearching}
          {#each matchingList as item (item.idx)}
            <text
              bind:this={matchTextElements[item.idx]}
              x={item.pt.screenX.toFixed(1)}
              y={(item.pt.screenY - item.pt.screenRy - 4).toFixed(1)}
              text-anchor="middle"
              class="match-label-text"
            >
              {item.pt.t}
            </text>
          {/each}
        {/if}
      </g>
    </svg>

    <!-- Tooltip: centered above cursor / touch, showing only occupation name -->
    {#if hoveredPoint}
      <div
        class="plot-tooltip"
        style="left: {mouseX}px; top: {mouseY}px;"
      >
        {hoveredPoint.t}
      </div>
    {/if}
  {/if}
  </div>

  <!-- Search Bar under the SVG -->
  <div class="plot-search-bar">
    <div class="search-input-box">
      <svg viewBox="0 0 24 24" class="search-icon" aria-hidden="true">
        <path fill="currentColor" d={mdiMagnify} />
      </svg>
      <input
        type="text"
        bind:value={searchQuery}
        class="search-input"
        aria-label="Search occupations"
        title="Search occupations"
        spellcheck="false"
        autocomplete="off"
        onkeydown={(e) => {
          if (e.key === 'Escape') {
            searchQuery = '';
            hoveredPoint = null;
          }
        }}
      />
      {#if searchQuery}
        <button
          type="button"
          class="search-clear-btn"
          onclick={() => {
            searchQuery = '';
            hoveredPoint = null;
          }}
          aria-label="Clear search"
        >
          <svg viewBox="0 0 24 24" class="clear-icon" aria-hidden="true">
            <path fill="currentColor" d={mdiClose} />
          </svg>
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .hero-plot-wrapper {
    width: 100%;
    max-width: 540px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .plot-search-bar {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-top: 0.15rem;
  }

  @media (min-width: 841px) {
    .plot-search-bar {
      /* Shift right to align with the axis origin (CENTER_X = 275/520) rather than the SVG center (260/520) */
      transform: translateX(calc(100% * 15 / 520));
    }
  }

  .search-input-box {
    width: 100%;
    max-width: 250px;
    height: 28px;
    position: relative;
    display: flex;
    align-items: center;
    background: #080808;
    border: 1px solid #1c1c1c;
    border-radius: 14px;
    transition: border-color 0.15s ease;
  }

  .search-input-box:focus-within {
    border-color: #404040;
  }

  .search-icon {
    width: 13px;
    height: 13px;
    color: #666666;
    margin-left: 9px;
    flex-shrink: 0;
  }

  .search-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #ededed;
    font-family: inherit;
    font-size: 0.76rem;
    padding: 0 6px;
    outline: none;
    min-width: 0;
  }

  .search-clear-btn {
    background: transparent;
    border: none;
    color: #666666;
    cursor: pointer;
    padding: 2px 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s ease;
  }

  .search-clear-btn:hover {
    color: #cccccc;
  }

  .clear-icon {
    width: 12px;
    height: 12px;
  }

  .match-label-text {
    font-size: 9.5px;
    font-weight: 500;
    fill: #ffffff;
    stroke: #05070a;
    stroke-width: 2.5px;
    paint-order: stroke fill;
    stroke-linejoin: round;
    pointer-events: none;
    user-select: none;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
  }

  .plot-container {
    width: 100%;
    max-width: 540px;
    aspect-ratio: 1 / 1;
    margin: 0 auto;
    background: #000000;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    user-select: none;
    -webkit-user-select: none;
    touch-action: none !important; /* Prevents mobile scroll on SVG drag */
    contain: layout paint;
    transform: translateZ(0);
    will-change: transform;
    cursor: crosshair;
  }

  .scatterplot-svg {
    width: 100%;
    height: 100%;
    display: block;
    background: #000000;
    contain: paint;
    transform: translateZ(0);
    touch-action: none !important;
  }

  .scatter-dot {
    pointer-events: none; /* Proximity detection on container handles hit testing efficiently */
  }

  .plot-tooltip {
    position: absolute;
    transform: translate(-50%, -100%);
    margin-top: -14px;
    background: rgba(18, 22, 28, 0.95);
    backdrop-filter: blur(4px);
    border: 1px solid #384252;
    color: #ffffff;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 4px 8px;
    border-radius: 4px;
    pointer-events: none;
    white-space: nowrap;
    z-index: 50;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.7);
    line-height: 1.2;
    letter-spacing: 0.01em;
  }

  .plot-loading,
  .plot-error {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: #999999;
    font-size: 0.9rem;
  }

  .loading-icon {
    display: block;
    width: 48px;
    height: 48px;
  }
</style>
