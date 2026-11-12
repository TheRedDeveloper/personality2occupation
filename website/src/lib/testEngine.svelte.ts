/**
 * Computerized Adaptive Testing (CAT) Engine for personality2occupation.
 *
 * Implements:
 * 1. Client-side loading of question_gradient.parquet (1,141 calibrated questions)
 *    and data.parquet (2,108 canonical occupations with 24D means & variances).
 * 2. 24D personality estimation using robust sensitivity gradients.
 * 3. Uncertainty tracking per dimension using Bayesian information accumulation.
 * 4. Maximum Information Gain question selection based on career candidate divergence.
 * 5. Gaussian log-likelihood matching across 2,108 canonical occupations.
 * 6. Dual-mode Bayesian prior slider (alpha in [0.0, 1.0]) for pure alignment vs labor market demand.
 * 7. Macroeconomic sector probability aggregation (8 balanced sectors).
 * 8. Full state persistence (localStorage) and complete Undo/Redo history stacks.
 * 9. Smooth Bayesian variance reduction convergence metric.
 * 10. Ultra-compact 3-bit deterministic Base64URL sharing (`test?r=`) and safe Continue confirmation.
 */

import { asset } from '$app/paths';
import sectorsData from './sectors.json';

export interface QuestionRecord {
  id: number;
  text: string;
  gradient: number[];    // Centered gradient for v2
  rawGradient: number[]; // Raw OLS gradient for v1 replay
}

export interface OccupationRecord {
  title: string;
  sampleCount: number;
  mean: number[];
  variance: number[];
  regVariance: number[];   // Bayesian shrunk variance (N0 = 50 for V5 matching)
  regVarianceV4?: number[]; // Preserved Bayesian shrunk variance (N0 = 25 for V4 replay)
  normPrior: number;       // Normalized prior bonus for market demand
  axis1?: number;          // Schwartz Circumplex Axis 1: Self-Transcendence vs Self-Enhancement
  axis2?: number;          // Schwartz Circumplex Axis 2: Openness to Change vs Conservation
  sectorIndex: number;
  sectorName: string;
}

export interface SectorScore {
  name: string;
  color: string;
  percentage: number;
  rawProbability: number;
}

export interface JobMatch {
  rank: number;
  title: string;
  matchScore: number;
  rawFit: number;
  sampleCount: number;
  sectorName: string;
  sectorColor: string;
}

export interface AnswerHistoryItem {
  question: QuestionRecord;
  choice: number; // 1 to 5
  k: number;      // -1.0 to +1.0
}

export interface ModalConfig {
  isOpen: boolean;
  type: 'reset' | 'overwrite_shared' | 'share';
  title: string;
  message: string;
  warning?: string;
  confirmText?: string;
  confirmDestructive?: boolean;
  cancelText?: string;
  shareUrl?: string;
  onConfirm?: () => void;
  onCancel?: () => void;
}

export const SECTOR_DISPLAY_NAMES: Record<string, string> = {
  'Education, Academia & Scientific Research': 'Education, Academia & Research',
  'Public Service, Law, Defense & Civil Operations': 'Public, Law, Defense & Civil',
  'Creative Arts, Design & Entertainment': 'Arts, Design & Entertainment',
  'Healthcare, Clinical Practice & Wellness Services': 'Healthcare, Medical & Wellness',
  'Corporate Strategy, Finance & Commercial Operations': 'Corporate, Finance & Commercial',
  'Technology, Software & Engineering Design': 'Technology, Software & Engineering',
  'Skilled Trades, Construction & Extraction': 'Trades, Construction & Extraction',
  'Writing, Journalism, Publishing & Media': 'Writing, Journalism & Media'
};

export const SECTOR_COLORS: Record<string, string> = {
  'Education, Academia & Scientific Research': '#3D5AFE',
  'Education, Academia & Research': '#3D5AFE',
  'Public Service, Law, Defense & Civil Operations': '#FF1744',
  'Public, Law, Defense & Civil': '#FF1744',
  'Creative Arts, Design & Entertainment': '#D500F9',
  'Arts, Design & Entertainment': '#D500F9',
  'Healthcare, Clinical Practice & Wellness Services': '#00E676',
  'Healthcare, Medical & Wellness': '#00E676',
  'Corporate Strategy, Finance & Commercial Operations': '#FFD600',
  'Corporate, Finance & Commercial': '#FFD600',
  'Technology, Software & Engineering Design': '#00E5FF',
  'Technology, Software & Engineering': '#00E5FF',
  'Skilled Trades, Construction & Extraction': '#A1887F',
  'Trades, Construction & Extraction': '#A1887F',
  'Writing, Journalism, Publishing & Media': '#FF9100',
  'Writing, Journalism & Media': '#FF9100'
};

const DIM = 24;
export const K_CHOICES: Record<number, number> = {
  1: -1.0, // Strongly Disagree
  2: -0.5, // Disagree
  3:  0.0, // Neutral
  4:  0.5, // Agree
  5:  1.0  // Strongly Agree
};

const STORAGE_KEY = 'p2o_test_state_v1';

export interface DecodedResult {
  version: 1 | 2 | 3 | 4 | 5;
  choices: number[];
}

/**
 * Standard Normal Cumulative Distribution Function (CDF).
 * Maps a z-score to its percentile (0.0 to 1.0), with z = 0 mapping to 0.50 (50%).
 */
export function normalCdf(z: number): number {
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const sign = z < 0 ? -1 : 1;
  const x = Math.abs(z) / Math.SQRT2;
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return 0.5 * (1.0 + sign * y);
}

/**
 * Ultra-compact 3-bit deterministic Base64URL encoding.
 * Since the test question selection is 100% deterministic given prior choices,
 * we only need to encode the 3-bit Likert choice (1..5 -> 0..4) for each step!
 *
 * Byte 0: format version (1 for v1 legacy, 2 for v2, 3 for v3 CAT, 4 for v4 IRT, 5 for modern v5 Circumplex CAT)
 * Byte 1: question count (N)
 * Bytes 2+: bitstream of 3-bit choices (N * 3 bits packed MSB-first)
 *
 * Size: 5 questions = 6 chars, 9 questions = 8 chars, 30 questions = 19 chars!
 */
export function encodeResultChoices(history: AnswerHistoryItem[], version: 1 | 2 | 3 | 4 | 5 = 5): string {
  const count = history.length;
  if (count === 0) return '';

  const totalBits = count * 3;
  const payloadBytes = Math.ceil(totalBits / 8);
  const bytes = new Uint8Array(2 + payloadBytes);

  bytes[0] = version; // format version (1, 2, 3, 4, or 5)
  bytes[1] = Math.min(255, count);

  let bitOffset = 0;
  for (let i = 0; i < count; i++) {
    const val = Math.max(0, Math.min(4, history[i].choice - 1)) & 0x07;
    for (let b = 2; b >= 0; b--) {
      const bit = (val >> b) & 1;
      const byteIdx = 2 + Math.floor(bitOffset / 8);
      const bitInByte = 7 - (bitOffset % 8);
      if (bit) {
        bytes[byteIdx] |= (1 << bitInByte);
      }
      bitOffset++;
    }
  }

  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export function decodeResultChoices(encoded: string): DecodedResult | null {
  try {
    let base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    if (bytes.length < 2) return null;
    const version = bytes[0];
    if (version !== 1 && version !== 2 && version !== 3 && version !== 4 && version !== 5) return null;

    const count = bytes[1];
    if (count === 0) return { version: version as 1 | 2 | 3 | 4 | 5, choices: [] };

    const expectedPayload = Math.ceil((count * 3) / 8);
    if (bytes.length < 2 + expectedPayload) return null;

    const choices: number[] = [];
    let bitOffset = 0;
    for (let i = 0; i < count; i++) {
      let choiceVal = 0;
      for (let b = 0; b < 3; b++) {
        const byteIdx = 2 + Math.floor(bitOffset / 8);
        const bitInByte = 7 - (bitOffset % 8);
        const bit = (bytes[byteIdx] >> bitInByte) & 1;
        choiceVal = (choiceVal << 1) | bit;
        bitOffset++;
      }
      choices.push(choiceVal + 1); // convert 0..4 back to 1..5
    }

    return { version: version as 1 | 2 | 3 | 4 | 5, choices };
  } catch (e) {
    console.warn('Failed to decode shared choices:', e);
    return null;
  }
}

export class TestEngine {
  // Loading & Readiness
  isLoaded = $state(false);
  isLoading = $state(false);
  loadingMessage = $state('Loading 1,141 neural question gradients and 2,108 canonical career distributions...');
  loadError = $state<string | null>(null);

  // Engine Version (1 for legacy replay, 2 for v2 replay, 3 for v3 CAT, 4 for v4 IRT, 5 for modern v5 Circumplex CAT)
  testVersion = $state<1 | 2 | 3 | 4 | 5>(5);

  // Core Data
  questions: QuestionRecord[] = [];
  occupations: OccupationRecord[] = [];
  popMean = new Float32Array(DIM);
  popStd = new Float32Array(DIM);
  meanWithinVar = new Float32Array(DIM);
  gradMaxV1 = new Float32Array(DIM);
  gradMaxV2 = new Float32Array(DIM);
  totalWorkers = 0;
  private topCandidatesV5: OccupationRecord[] = [];

  // Adaptive User State
  userVector = $state<number[]>(new Array(DIM).fill(0.5));
  userUncertainty = $state<number[]>(new Array(DIM).fill(1.0));
  answeredHistory = $state<AnswerHistoryItem[]>([]);
  redoStack = $state<AnswerHistoryItem[]>([]);
  askedQuestionIds = $state<Set<number>>(new Set());

  // Current Question
  currentQuestion = $state<QuestionRecord | null>(null);

  // Bayesian Prior Dial
  alpha = $state(0.5); // 0.0 = Pure Psychological Alignment, 1.0 = Labor Market Reality

  // Results & Outputs
  sectorScores = $state<SectorScore[]>([]);
  topJobs = $state<JobMatch[]>([]);
  confidence = $state(0); // 0 to 100%

  // Modal Dialog State
  modal = $state<ModalConfig | null>(null);

  // Shared Result State
  isViewingSharedResult = $state(false);

  // Derived Helpers
  answeredCount = $derived(this.answeredHistory.length);
  canUndo = $derived(this.answeredHistory.length > 0 && !this.isViewingSharedResult);
  canRedo = $derived(this.redoStack.length > 0 && !this.isViewingSharedResult);
  normalizedUserVector = $derived.by(() => {
    const res = new Array<number>(DIM);
    for (let d = 0; d < DIM; d++) {
      const z = (this.userVector[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
      res[d] = Math.max(0.01, Math.min(0.99, normalCdf(z)));
    }
    return res;
  });

  async init() {
    if (this.isLoaded || this.isLoading) return;
    this.isLoading = true;
    this.loadingMessage = 'Loading 1,141 neural question gradients and 2,108 canonical career distributions...';
    this.loadError = null;

    try {
      const { parquetRead } = await import('hyparquet');

      const [questionsRes, dataRes] = await Promise.all([
        fetch(asset('question_gradient.parquet')),
        fetch(asset('data.parquet'))
      ]);

      if (!questionsRes.ok) throw new Error(`question_gradient.parquet HTTP ${questionsRes.status}`);
      if (!dataRes.ok) throw new Error(`data.parquet HTTP ${dataRes.status}`);

      const [qBuf, dBuf] = await Promise.all([
        questionsRes.arrayBuffer(),
        dataRes.arrayBuffer()
      ]);

      let rawQuestions: any[] = [];
      let rawOccupations: any[] = [];

      await parquetRead({
        file: qBuf,
        rowFormat: 'object',
        onComplete: (rows) => { rawQuestions = rows; }
      });

      await parquetRead({
        file: dBuf,
        rowFormat: 'object',
        onComplete: (rows) => { rawOccupations = rows; }
      });

      // Compute Mean Template Gradient across all 1,141 questions to center v2 gradients
      const meanGrad = new Float32Array(DIM);
      for (const r of rawQuestions) {
        const g = r.gradient;
        for (let d = 0; d < DIM; d++) meanGrad[d] += g[d];
      }
      for (let d = 0; d < DIM; d++) meanGrad[d] /= rawQuestions.length;

      this.questions = rawQuestions.map(r => {
        const rawG = Array.from(r.gradient) as number[];
        const centG = rawG.map((val, d) => val - meanGrad[d]);
        return {
          id: Number(r.id),
          text: String(r.text),
          gradient: centG,       // Centered for v2
          rawGradient: rawG      // Raw for v1 deterministic replay
        };
      });

      const sectorNames = sectorsData.sectors as string[];
      const sectorMap = sectorsData.mapping as Record<string, number>;

      this.occupations = rawOccupations.map(r => {
        const title = String(r.canonical_occupation);
        const sIdx = sectorMap[title] ?? 0;
        return {
          title,
          sampleCount: Number(r.sample_count),
          mean: Array.from(r.mean),
          variance: Array.from(r.variance),
          regVariance: [],
          normPrior: 0,
          sectorIndex: sIdx,
          sectorName: sectorNames[sIdx] ?? 'Other'
        };
      });

      const nJobs = this.occupations.length;
      this.totalWorkers = this.occupations.reduce((sum, r) => sum + r.sampleCount, 0);

      // Compute Population Means & Standard Deviations
      for (let d = 0; d < DIM; d++) {
        let sum = 0;
        for (let j = 0; j < nJobs; j++) sum += this.occupations[j].mean[d];
        this.popMean[d] = sum / nJobs;

        let ssq = 0;
        for (let j = 0; j < nJobs; j++) {
          const diff = this.occupations[j].mean[d] - this.popMean[d];
          ssq += diff * diff;
        }
        this.popStd[d] = Math.sqrt(ssq / nJobs);
      }

      // Compute Grand Mean of Within-Job Variances across all 2,108 occupations
      const meanWithinVar = new Float32Array(DIM);
      for (const occ of this.occupations) {
        for (let d = 0; d < DIM; d++) meanWithinVar[d] += occ.variance[d];
      }
      for (let d = 0; d < DIM; d++) meanWithinVar[d] /= nJobs;
      this.meanWithinVar = meanWithinVar;

      // Empirical Bayes Variance Shrinkage toward grand mean of within-job variances
      // N0_V4 = 25 preserved for deterministic V4 IRT question selection
      // N0_V5 = 50 for V5 Domain-Normalized Z-Score Matching
      const N0_V4 = 25;
      const N0_V5 = 50;
      let minSampleCount = Infinity;
      let maxSampleCount = -Infinity;
      for (const occ of this.occupations) {
        if (occ.sampleCount < minSampleCount) minSampleCount = occ.sampleCount;
        if (occ.sampleCount > maxSampleCount) maxSampleCount = occ.sampleCount;
      }
      const logMin = Math.log(Math.max(1, minSampleCount));
      const logMax = Math.log(Math.max(2, maxSampleCount));
      const logSpan = logMax - logMin || 1.0;

      for (const occ of this.occupations) {
        const N = occ.sampleCount;
        const regVarV4 = new Array(DIM);
        const regVarV5 = new Array(DIM);
        for (let d = 0; d < DIM; d++) {
          regVarV4[d] = (N * occ.variance[d] + N0_V4 * this.meanWithinVar[d]) / (N + N0_V4);
          regVarV5[d] = (N * occ.variance[d] + N0_V5 * this.meanWithinVar[d]) / (N + N0_V5);
        }
        occ.regVariance = regVarV5;
        occ.regVarianceV4 = regVarV4;
        occ.normPrior = ((Math.log(Math.max(1, N)) - logMin) / logSpan) * 12.0;

        // Schwartz Circumplex Macro-Axes:
        // Theoretical foundation (Schwartz 1992, 2012; SchwartzCircle):
        // Boundary values straddle adjacent quadrants:
        // - Humility (18): shared by Self-Transcendence (18..23) and Conservation (12..18)
        // - Face (12): shared by Self-Enhancement (8..12) and Conservation (12..18)
        // - Hedonism (8): shared by Openness to Change (5..8) and Self-Enhancement (8..12)
        //
        // Axis 1: Self-Transcendence (18..23, 6 values) minus Self-Enhancement (8..12, 5 values)
        // Axis 2: Openness to Change (5..8, 4 values) minus Conservation (12..18, 7 values)
        let jTrans = 0, jEnh = 0, jOpen = 0, jCons = 0;
        for (let d = 18; d <= 23; d++) jTrans += (occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
        jTrans /= 6;
        for (let d = 8; d <= 12; d++) jEnh += (occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
        jEnh /= 5;
        occ.axis1 = jTrans - jEnh;

        for (let d = 5; d <= 8; d++) jOpen += (occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
        jOpen /= 4;
        for (let d = 12; d <= 18; d++) jCons += (occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
        jCons /= 7;
        occ.axis2 = jOpen - jCons;
      }

      // Compute Max Gradient per Dimension for both v1 and v2 normalization
      for (let d = 0; d < DIM; d++) {
        let maxV1 = 0;
        let maxV2 = 0;
        for (const q of this.questions) {
          maxV1 = Math.max(maxV1, Math.abs(q.rawGradient[d]));
          maxV2 = Math.max(maxV2, Math.abs(q.gradient[d]));
        }
        this.gradMaxV1[d] = Math.max(maxV1, 0.01);
        this.gradMaxV2[d] = Math.max(maxV2, 0.01);
      }

      // Check URL for shared result parameter `?r=`
      let sharedParam: string | null = null;
      if (typeof window !== 'undefined') {
        const sp = new URLSearchParams(window.location.search);
        sharedParam = sp.get('r');
      }

      if (sharedParam) {
        const decoded = decodeResultChoices(sharedParam);
        if (decoded && decoded.choices.length > 0) {
          this.loadingMessage = 'Calculating career matches from shared responses...';
          // Yield to let the browser repaint the calculating message
          await new Promise((resolve) => setTimeout(resolve, 20));

          // Reconstruct the exact psychometric test sequence deterministically
          await this.reconstructFromChoices(decoded.choices, decoded.version);
          this.isViewingSharedResult = true;
          // Note: We do NOT touch or overwrite localStorage when viewing a shared link!
          this.isLoaded = true;
          return;
        }
      }

      // Standard restoration from localStorage
      const restored = this.restoreFromStorage();
      if (!restored) {
        this.reset();
      }

      this.isLoaded = true;
    } catch (err: any) {
      console.error('Failed to initialize TestEngine:', err);
      this.loadError = err.message || 'Failed to load test data';
    } finally {
      this.isLoading = false;
    }
  }

  /**
   * Deterministically replay test choices using adaptive question selection.
   * If version === 1, uses the exact legacy V1 question sequence.
   * If version === 2, uses the V2 marginal variance reduction sequence.
   * If version === 3, uses the V3 candidate disambiguation sequence.
   * If version === 4, uses the V4 IRT candidate sequence.
   * If version === 5, uses the modern V5 Circumplex CAT candidate sequence.
   */
  private async reconstructFromChoices(choices: number[], version: 1 | 2 | 3 | 4 | 5) {
    this.answeredHistory = [];
    this.redoStack = [];
    this.alpha = 0.5;
    this.testVersion = version;

    if (version === 1) {
      // Replay using the exact deterministic V1 question selection trajectory
      let curQ: QuestionRecord | null = this.questions[0] ?? null;
      const v1Asked = new Set<number>();
      let v1Vector = Array.from(this.popMean);
      let v1Uncertainty = new Array(DIM).fill(1.0);

      for (let i = 0; i < choices.length; i++) {
        if (!curQ) break;
        const choice = choices[i];
        const k = K_CHOICES[choice] ?? 0.0;
        v1Asked.add(curQ.id);
        this.answeredHistory.push({ question: curQ, choice, k });

        // V1 intermediate state update
        const nextVector = Array.from(this.popMean);
        const info = new Float32Array(DIM).fill(1.0);
        for (const item of this.answeredHistory) {
          for (let d = 0; d < DIM; d++) {
            const normW = item.question.rawGradient[d] / this.gradMaxV1[d];
            const shift = item.k * normW * this.popStd[d] * 1.85;
            nextVector[d] = Math.max(0.0, Math.min(1.0, nextVector[d] + shift));
            info[d] += 0.35 * Math.abs(normW);
          }
        }
        for (let d = 0; d < DIM; d++) {
          v1Uncertainty[d] = 1.0 / Math.sqrt(info[d]);
        }
        v1Vector = nextVector;

        // V1 likelihoods for candidate divergence
        const nJobs = this.occupations.length;
        const ll = new Float32Array(nJobs);
        let maxLL = -Infinity;
        for (let j = 0; j < nJobs; j++) {
          const occ = this.occupations[j];
          let val = 0;
          for (let d = 0; d < DIM; d++) {
            const totalVar = occ.variance[d] + (v1Uncertainty[d] ** 2) * (this.popStd[d] ** 2);
            const diff = v1Vector[d] - occ.mean[d];
            val += -0.5 * ((diff * diff) / totalVar + Math.log(totalVar));
          }
          ll[j] = val;
          if (val > maxLL) maxLL = val;
        }

        const scoredJobs = this.occupations.map((occ, j) => {
          const logPrior = Math.log(occ.sampleCount / (this.totalWorkers || 1));
          return { title: occ.title, mean: occ.mean, totalScore: ll[j] + this.alpha * logPrior };
        });
        scoredJobs.sort((a, b) => b.totalScore - a.totalScore);
        const topCandidates = scoredJobs.slice(0, 30);

        const candidateDivergence = new Float32Array(DIM);
        if (topCandidates.length > 1) {
          for (let d = 0; d < DIM; d++) {
            let sum = 0;
            for (const c of topCandidates) sum += c.mean[d];
            const avg = sum / topCandidates.length;
            let ssq = 0;
            for (const c of topCandidates) {
              const diff = c.mean[d] - avg;
              ssq += diff * diff;
            }
            candidateDivergence[d] = Math.sqrt(ssq / topCandidates.length);
          }
        }

        // V1 question selection
        let bestQ: QuestionRecord | null = null;
        let maxGain = -Infinity;
        for (const q of this.questions) {
          if (v1Asked.has(q.id)) continue;
          let gain = 0;
          for (let d = 0; d < DIM; d++) {
            const normW = Math.abs(q.rawGradient[d]) / this.gradMaxV1[d];
            const divergenceWeight = candidateDivergence[d] + 0.04;
            const uncertaintyWeight = v1Uncertainty[d];
            gain += divergenceWeight * uncertaintyWeight * normW;
          }
          if (gain > maxGain) {
            maxGain = gain;
            bestQ = q;
          }
        }
        curQ = bestQ;

        // Yield periodically so the spinner stays smooth during large replays
        if (i > 0 && i % 25 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
      }

      this.currentQuestion = curQ;
      // Recompute final state with V2 precision weighting and career matches
      this.recomputeState();
    } else {
      // V2 Replay
      this.recomputeState();
      for (let i = 0; i < choices.length; i++) {
        const choice = choices[i];
        if (!this.currentQuestion) break;
        const k = K_CHOICES[choice] ?? 0.0;
        this.answeredHistory.push({
          question: this.currentQuestion,
          choice,
          k
        });
        this.recomputeState();

        if (i > 0 && i % 25 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
      }
    }
  }

  reset() {
    this.answeredHistory = [];
    this.redoStack = [];
    this.alpha = 0.5;
    this.testVersion = 5; // Always reset to modern v5 engine
    this.isViewingSharedResult = false;
    this.recomputeState();
    this.clearStorage();
    this.cleanUrlParams();
  }

  setAlpha(newAlpha: number) {
    this.alpha = Math.max(0.0, Math.min(1.0, newAlpha));
    this.recalculateMatches();
    if (!this.isViewingSharedResult) {
      this.saveToStorage();
    }
  }

  answer(choice: number) {
    if (!this.currentQuestion) return;
    const k = K_CHOICES[choice] ?? 0.0;
    const q = this.currentQuestion;

    this.answeredHistory.push({ question: q, choice, k });
    this.redoStack = [];
    this.isViewingSharedResult = false;

    this.recomputeState();
    this.saveToStorage();
    this.cleanUrlParams();
  }

  undo() {
    if (this.answeredHistory.length === 0 || this.isViewingSharedResult) return;
    const undone = this.answeredHistory.pop()!;
    this.redoStack.push(undone);

    this.recomputeState();
    this.saveToStorage();
    this.cleanUrlParams();
  }

  redo() {
    if (this.redoStack.length === 0 || this.isViewingSharedResult) return;
    const redone = this.redoStack.pop()!;
    this.answeredHistory.push(redone);

    this.recomputeState();
    this.saveToStorage();
    this.cleanUrlParams();
  }

  // --- Modal Dialog Actions ---

  openResetModal() {
    if (this.answeredCount === 0) return;
    this.modal = {
      isOpen: true,
      type: 'reset',
      title: 'Reset Test Progress?',
      message: 'Are you sure you want to reset your answers and restart from Question 1?',
      warning: 'All current progress will be lost.',
      confirmText: 'Reset Test',
      confirmDestructive: true,
      cancelText: 'Cancel',
      onConfirm: () => {
        this.reset();
        this.closeModal();
      },
      onCancel: () => {
        this.closeModal();
      }
    };
  }

  openShareModal() {
    const url = this.getShareUrl();
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(url).catch(() => {});
    }

    this.modal = {
      isOpen: true,
      type: 'share',
      title: 'Share',
      message: 'Share your results:',
      shareUrl: url,
      onConfirm: () => {
        this.closeModal();
      },
      onCancel: () => {
        this.closeModal();
      }
    };
  }

  closeModal() {
    this.modal = null;
  }

  getShareUrl(): string {
    if (typeof window === 'undefined') return '';
    const encoded = encodeResultChoices(this.answeredHistory, this.testVersion);
    const origin = window.location.origin;
    const path = window.location.pathname;
    return `${origin}${path}?r=${encoded}`;
  }

  // --- Shared Result "Continue" Workflow ---

  handleContinueShared() {
    const stored = this.readStorage();
    const hasStoredAnswers = stored !== null && stored.history.length > 0;

    if (hasStoredAnswers) {
      // User has an existing test saved on this device; ask for confirmation
      this.modal = {
        isOpen: true,
        type: 'overwrite_shared',
        title: 'Overwrite Saved Test?',
        message: 'You already have an in-progress test saved in this browser.',
        warning: 'Continuing from this shared result will overwrite your saved test.',
        confirmText: 'Overwrite',
        confirmDestructive: true,
        cancelText: 'Cancel',
        onConfirm: () => {
          this.isViewingSharedResult = false;
          this.saveToStorage();
          this.cleanUrlParams();
          this.closeModal();
        },
        onCancel: () => {
          this.closeModal();
        }
      };
    } else {
      // No conflicting saved test: adopt shared test immediately
      this.isViewingSharedResult = false;
      this.saveToStorage();
      this.cleanUrlParams();
    }
  }

  private cleanUrlParams() {
    if (typeof window !== 'undefined' && window.history && window.location.search) {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, '', cleanUrl);
    }
  }

  private recomputeState() {
    const nextAsked = new Set<number>();
    for (const item of this.answeredHistory) {
      nextAsked.add(item.question.id);
    }
    this.askedQuestionIds = nextAsked;

    // V2: Principled Bayesian Precision Weighting
    const nextVector = new Array(DIM);
    const nextUncertainty = new Array(DIM);
    const traitPrecision = new Float32Array(DIM).fill(1.0); // Prior precision = 1.0

    // V4 IRT Information Scaling - Prevents signal dilution over many questions
    const devSum = new Float32Array(DIM);

    for (const item of this.answeredHistory) {
      for (let d = 0; d < DIM; d++) {
        const normW = item.question.gradient[d] / this.gradMaxV2[d];
        const absW = Math.abs(normW);
        if (absW > 0.10) {
          const weight = absW * absW * 2.5;
          const shift = item.k * Math.sign(normW) * this.popStd[d] * 2.2;
          devSum[d] += weight * shift;
          traitPrecision[d] += weight;
        }
      }
    }

    const power = 0.55;
    const refFactor = Math.pow(4.5, 1.0 - power);
    for (let d = 0; d < DIM; d++) {
      const divisor = Math.pow(traitPrecision[d], power) * refFactor;
      nextVector[d] = Math.max(0.0, Math.min(1.0, this.popMean[d] + devSum[d] / divisor));
      nextUncertainty[d] = 1.0 / Math.sqrt(traitPrecision[d]);
    }

    this.userVector = nextVector;
    this.userUncertainty = nextUncertainty;

    this.recalculateMatches();
    this.pickNextQuestion();
  }

  private saveToStorage() {
    if (typeof window === 'undefined') return;
    try {
      const payload = {
        version: this.testVersion,
        history: this.answeredHistory.map(h => ({ qId: h.question.id, choice: h.choice, k: h.k })),
        redo: this.redoStack.map(r => ({ qId: r.question.id, choice: r.choice, k: r.k })),
        alpha: this.alpha
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('Failed to save test state to localStorage:', e);
    }
  }

  private clearStorage() {
    if (typeof window === 'undefined') return;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  private readStorage(): { version: 1 | 2 | 3 | 4 | 5; history: AnswerHistoryItem[]; alpha: number } | null {
    if (typeof window === 'undefined') return null;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || !Array.isArray(data.history)) return null;

      const qMap = new Map<number, QuestionRecord>();
      for (const q of this.questions) qMap.set(q.id, q);

      const history: AnswerHistoryItem[] = [];
      for (const item of data.history) {
        const q = qMap.get(item.qId);
        if (q) {
          history.push({ question: q, choice: item.choice, k: item.k });
        }
      }

      const version: 1 | 2 | 3 | 4 | 5 = (data.version === 1 || data.version === 2 || data.version === 3 || data.version === 4 || data.version === 5)
        ? data.version
        : 5;
      const alpha = typeof data.alpha === 'number' ? Math.max(0, Math.min(1, data.alpha)) : 0.5;
      return { version, history, alpha };
    } catch (e) {
      return null;
    }
  }

  private restoreFromStorage(): boolean {
    const data = this.readStorage();
    if (!data) return false;

    this.testVersion = data.version;
    this.answeredHistory = data.history;
    this.redoStack = [];
    this.alpha = data.alpha;
    this.recomputeState();
    return true;
  }

  private pickNextQuestion() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    if (this.testVersion === 1) {
      this.pickNextQuestionV1();
    } else if (this.testVersion === 2) {
      this.pickNextQuestionV2();
    } else if (this.testVersion === 3) {
      this.pickNextQuestionV3();
    } else if (this.testVersion === 4) {
      this.pickNextQuestionV4();
    } else {
      this.pickNextQuestionV5();
    }
  }

  private pickNextQuestionV1() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    if (this.answeredHistory.length === 0) {
      this.currentQuestion = this.questions[0];
      return;
    }

    // Reconstruct pure V1 state to ensure 100% deterministic CAT replay
    const nextVector = Array.from(this.popMean);
    const info = new Float32Array(DIM).fill(1.0);
    for (const item of this.answeredHistory) {
      for (let d = 0; d < DIM; d++) {
        const normW = item.question.rawGradient[d] / this.gradMaxV1[d];
        const shift = item.k * normW * this.popStd[d] * 1.85;
        nextVector[d] = Math.max(0.0, Math.min(1.0, nextVector[d] + shift));
        info[d] += 0.35 * Math.abs(normW);
      }
    }
    const v1Uncertainty = new Float32Array(DIM);
    for (let d = 0; d < DIM; d++) {
      v1Uncertainty[d] = 1.0 / Math.sqrt(info[d]);
    }
    const v1Vector = nextVector;

    const nJobs = this.occupations.length;
    const ll = new Float32Array(nJobs);
    for (let j = 0; j < nJobs; j++) {
      const occ = this.occupations[j];
      let val = 0;
      for (let d = 0; d < DIM; d++) {
        const totalVar = occ.variance[d] + (v1Uncertainty[d] ** 2) * (this.popStd[d] ** 2);
        const diff = v1Vector[d] - occ.mean[d];
        val += -0.5 * ((diff * diff) / totalVar + Math.log(totalVar));
      }
      ll[j] = val;
    }

    const scoredJobs = this.occupations.map((occ, j) => {
      const logPrior = Math.log(occ.sampleCount / (this.totalWorkers || 1));
      return { title: occ.title, mean: occ.mean, totalScore: ll[j] + this.alpha * logPrior };
    });
    scoredJobs.sort((a, b) => b.totalScore - a.totalScore);
    const topCandidates = scoredJobs.slice(0, 30);

    const candidateDivergence = new Float32Array(DIM);
    if (topCandidates.length > 1) {
      for (let d = 0; d < DIM; d++) {
        let sum = 0;
        for (const c of topCandidates) sum += c.mean[d];
        const avg = sum / topCandidates.length;
        let ssq = 0;
        for (const c of topCandidates) {
          const diff = c.mean[d] - avg;
          ssq += diff * diff;
        }
        candidateDivergence[d] = Math.sqrt(ssq / topCandidates.length);
      }
    }

    let bestQuestion: QuestionRecord | null = null;
    let maxGain = -Infinity;

    for (const q of this.questions) {
      if (this.askedQuestionIds.has(q.id)) continue;

      let gain = 0;
      for (let d = 0; d < DIM; d++) {
        const normW = Math.abs(q.rawGradient[d]) / this.gradMaxV1[d];
        const divergenceWeight = candidateDivergence[d] + 0.04;
        const uncertaintyWeight = v1Uncertainty[d];
        gain += divergenceWeight * uncertaintyWeight * normW;
      }

      if (gain > maxGain) {
        maxGain = gain;
        bestQuestion = q;
      }
    }

    this.currentQuestion = bestQuestion;
  }

  private pickNextQuestionV2() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    // Initial Anchor Question
    if (this.answeredHistory.length === 0) {
      this.currentQuestion = this.questions[0];
      return;
    }

    // Identify candidate divergence across top 20 candidate occupations
    const topCandidates = this.topJobs.slice(0, 20);
    const candidateDivRatio = new Float32Array(DIM);

    if (topCandidates.length > 1) {
      for (let d = 0; d < DIM; d++) {
        let sum = 0;
        const candidateOccs: OccupationRecord[] = [];
        for (const c of topCandidates) {
          const occ = this.occupations.find(o => o.title === c.title);
          if (occ) {
            candidateOccs.push(occ);
            sum += occ.mean[d];
          }
        }
        if (candidateOccs.length > 1) {
          const avg = sum / candidateOccs.length;
          let ssq = 0;
          for (const occ of candidateOccs) {
            const diff = occ.mean[d] - avg;
            ssq += diff * diff;
          }
          const candidateStd = Math.sqrt(ssq / candidateOccs.length);
          candidateDivRatio[d] = candidateStd / (this.popStd[d] || 0.01);
        }
      }
    }

    let bestQuestion: QuestionRecord | null = null;
    let maxGain = -Infinity;

    for (const q of this.questions) {
      if (this.askedQuestionIds.has(q.id)) continue;

      let gain = 0;
      for (let d = 0; d < DIM; d++) {
        const normW = Math.abs(q.gradient[d]) / this.gradMaxV2[d];
        const curPrec = 1.0 / (this.userUncertainty[d] ** 2);
        // Marginal variance reduction DeltaVar = normW / (curPrec * (curPrec + normW))
        const deltaVar = normW / (curPrec * (curPrec + normW));

        // Candidate Divergence Ratio:
        // Early questions (< 4): focus on broad coverage
        // Later questions (>= 4): focus on career candidate divergence
        const careerWeight = this.answeredHistory.length < 4 ? 0.3 : (candidateDivRatio[d] * 2.0);
        const foundationalBonus = d < 5 ? 1.25 : 1.0;
        gain += deltaVar * (1.0 + careerWeight) * foundationalBonus;
      }

      if (gain > maxGain) {
        maxGain = gain;
        bestQuestion = q;
      }
    }

    this.currentQuestion = bestQuestion;
  }

  private pickNextQuestionV3() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    // Initial Anchor Question
    if (this.answeredHistory.length === 0) {
      this.currentQuestion = this.questions[0];
      return;
    }

    // Identify candidate divergence across top 20 candidate occupations
    const topCandidates = this.topJobs.slice(0, 20);
    const candidateDivRatio = new Float32Array(DIM);

    if (topCandidates.length > 1) {
      const topOccs: OccupationRecord[] = [];
      for (const c of topCandidates) {
        const occ = this.occupations.find(o => o.title === c.title);
        if (occ) topOccs.push(occ);
      }

      if (topOccs.length > 1) {
        for (let d = 0; d < DIM; d++) {
          let sum = 0;
          for (const occ of topOccs) sum += occ.mean[d];
          const avg = sum / topOccs.length;
          let ssq = 0;
          for (const occ of topOccs) {
            const diff = occ.mean[d] - avg;
            ssq += diff * diff;
          }
          const candidateStd = Math.sqrt(ssq / topOccs.length);
          candidateDivRatio[d] = candidateStd / (this.popStd[d] || 0.01);
        }
      }
    }

    let bestQuestion: QuestionRecord | null = null;
    let maxGain = -Infinity;

    for (const q of this.questions) {
      if (this.askedQuestionIds.has(q.id)) continue;

      let gain = 0;
      for (let d = 0; d < DIM; d++) {
        const normW = Math.abs(q.gradient[d]) / this.gradMaxV2[d];
        // V3 Noise Floor: questions below 0.10 provide no Bayesian evidence
        if (normW <= 0.10) continue;

        // V3 Quadratic Evidence Precision: directly aligns with Bayesian updater
        const dPrec = normW * normW * 2.5;
        const curPrec = 1.0 / (this.userUncertainty[d] ** 2);
        const deltaVar = dPrec / (curPrec * (curPrec + dPrec));

        // Candidate Disambiguation Weight:
        // Early questions (< 4): foundational trait anchoring
        // Later questions (>= 4): discriminate between active candidate occupations
        const careerWeight = this.answeredHistory.length < 4 ? 0.25 : (candidateDivRatio[d] * 2.5);
        const foundationalBonus = d < 5 ? 1.2 : 1.0;
        gain += deltaVar * (1.0 + careerWeight) * foundationalBonus;
      }

      if (gain > maxGain) {
        maxGain = gain;
        bestQuestion = q;
      }
    }

    this.currentQuestion = bestQuestion;
  }

  /**
   * Dedicated candidate divergence extractor for 100% deterministic V4 test replay.
   * Replicates the exact V4 ranking and candidate slicing logic from snapshot:
   * uses N0 = 25 regVarianceV4, all 24 dimensions RMS distance, scoredJobs sorted
   * by totalScore = rawFit + alpha * occ.normPrior, and extracts the top 25 by rawFit.
   */
  private getCandidateDivergenceV4(): Float32Array {
    const candidateDivRatio = new Float32Array(DIM);
    const nJobs = this.occupations.length;
    if (nJobs === 0) return candidateDivRatio;

    const scoredJobs: { occ: OccupationRecord; totalScore: number; rawFit: number }[] = new Array(nJobs);

    for (let j = 0; j < nJobs; j++) {
      const occ = this.occupations[j];
      let sumWeightedD2 = 0;
      let specialistTerm = 0;
      let totalInfo = 0;

      for (let d = 0; d < DIM; d++) {
        const infoD = Math.max(0, 1.0 - (this.userUncertainty[d] ** 2));
        totalInfo += infoD;

        const regVar = occ.regVarianceV4 ? occ.regVarianceV4[d] : occ.regVariance[d];
        const userVar = (this.userUncertainty[d] ** 2) * this.meanWithinVar[d];
        const combinedVar = regVar + userVar;
        const diff = this.userVector[d] - occ.mean[d];
        const dimD2 = (diff * diff) / combinedVar;

        sumWeightedD2 += infoD * dimD2;

        const distinctiveness = Math.min(1.0, Math.abs(occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01));
        const refCombinedVar = (1.0 + (this.userUncertainty[d] ** 2)) * this.meanWithinVar[d];
        const logRatio = Math.log(refCombinedVar / combinedVar);
        const rangeAdvantage = 1.0 - Math.min(2.0, dimD2);
        specialistTerm += infoD * distinctiveness * logRatio * rangeAdvantage;
      }

      const effDist = Math.sqrt(sumWeightedD2 / (totalInfo || 1));
      const normBonus = totalInfo > 0 ? (specialistTerm / totalInfo) : 0;
      const baseFit = 100 * Math.exp(-0.35 * effDist);
      const rawFit = baseFit * (1.0 + 0.10 * Math.max(-0.35, Math.min(0.35, normBonus)));
      const totalScore = rawFit + this.alpha * occ.normPrior;

      scoredJobs[j] = { occ, totalScore, rawFit };
    }

    // Sort scoredJobs exactly as snapshot line 1283 did
    scoredJobs.sort((a, b) => {
      if (Math.abs(b.totalScore - a.totalScore) > 1e-6) {
        return b.totalScore - a.totalScore;
      }
      return b.rawFit - a.rawFit;
    });

    // In snapshot, this.topJobs was all scoredJobs.
    // pickNextQuestionV4 sorted [...this.topJobs] by b.rawFit - a.rawFit and took top 25:
    const rawCandidates = [...scoredJobs].sort((a, b) => b.rawFit - a.rawFit).slice(0, 25);

    if (rawCandidates.length > 1) {
      const topOccs = rawCandidates.map(c => c.occ);
      for (let d = 0; d < DIM; d++) {
        let sum = 0;
        for (const occ of topOccs) sum += occ.mean[d];
        const avg = sum / topOccs.length;
        let ssq = 0;
        for (const occ of topOccs) {
          const diff = occ.mean[d] - avg;
          ssq += diff * diff;
        }
        const candidateStd = Math.sqrt(ssq / topOccs.length);
        candidateDivRatio[d] = candidateStd / (this.popStd[d] || 0.01);
      }
    }

    return candidateDivRatio;
  }

  private pickNextQuestionV4() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    // Initial Anchor Question
    if (this.answeredHistory.length === 0) {
      this.currentQuestion = this.questions[0];
      return;
    }

    // Identify candidate divergence across top 25 candidate occupations by RAW FIT (unbiased by market sample prior)
    // using the exact V4 candidate extractor for 100% deterministic replay
    const candidateDivRatio = this.getCandidateDivergenceV4();

    let bestQuestion: QuestionRecord | null = null;
    let maxGain = -Infinity;

    for (const q of this.questions) {
      if (this.askedQuestionIds.has(q.id)) continue;

      let gain = 0;
      for (let d = 0; d < DIM; d++) {
        const normW = Math.abs(q.gradient[d]) / this.gradMaxV2[d];
        if (normW <= 0.10) continue;

        // V4 Quadratic Evidence Precision: directly aligns with IRT information model
        const dPrec = normW * normW * 2.5;
        const curPrec = 1.0 / (this.userUncertainty[d] ** 2);
        const deltaVar = dPrec / (curPrec * (curPrec + dPrec));

        // Candidate Disambiguation Weight:
        // Early questions (< 4): foundational trait anchoring
        // Later questions (>= 4): discriminate between active psychometric candidate occupations
        const careerWeight = this.answeredHistory.length < 4 ? 0.25 : (candidateDivRatio[d] * 2.5);
        const foundationalBonus = d < 5 ? 1.2 : 1.0;
        gain += deltaVar * (1.0 + careerWeight) * foundationalBonus;
      }

      if (gain > maxGain) {
        maxGain = gain;
        bestQuestion = q;
      }
    }

    this.currentQuestion = bestQuestion;
  }

  /**
   * Candidate divergence and circumplex macro-axis dispersion extractor for V5 adaptive question selection.
   * Extracts candidate variance across all 24 psychometric traits and standard deviation across
   * Schwartz Circumplex macro-axes (Axis 1: Self-Transcendence vs Self-Enhancement;
   * Axis 2: Openness to Change vs Conservation) from the top 25 candidates under V5 matching.
   */
  private getCandidateDivergenceV5(): {
    candidateDivRatio: Float32Array;
    axis1Std: number;
    axis2Std: number;
  } {
    const candidateDivRatio = new Float32Array(DIM);
    let axis1Std = 0;
    let axis2Std = 0;

    const topOccs = this.topCandidatesV5;
    if (topOccs.length > 1) {
      for (let d = 0; d < DIM; d++) {
        let sum = 0;
        for (const occ of topOccs) sum += occ.mean[d];
        const avg = sum / topOccs.length;
        let ssq = 0;
        for (const occ of topOccs) {
          const diff = occ.mean[d] - avg;
          ssq += diff * diff;
        }
        candidateDivRatio[d] = Math.sqrt(ssq / topOccs.length) / (this.popStd[d] || 0.01);
      }

      let a1Sum = 0;
      let a2Sum = 0;
      for (const occ of topOccs) {
        a1Sum += occ.axis1 ?? 0;
        a2Sum += occ.axis2 ?? 0;
      }
      const a1Avg = a1Sum / topOccs.length;
      const a2Avg = a2Sum / topOccs.length;
      let a1Ssq = 0;
      let a2Ssq = 0;
      for (const occ of topOccs) {
        a1Ssq += ((occ.axis1 ?? 0) - a1Avg) ** 2;
        a2Ssq += ((occ.axis2 ?? 0) - a2Avg) ** 2;
      }
      axis1Std = Math.sqrt(a1Ssq / topOccs.length);
      axis2Std = Math.sqrt(a2Ssq / topOccs.length);
    }

    return { candidateDivRatio, axis1Std, axis2Std };
  }

  private pickNextQuestionV5() {
    if (this.questions.length === 0) {
      this.currentQuestion = null;
      return;
    }

    // Initial Anchor Question
    if (this.answeredHistory.length === 0) {
      this.currentQuestion = this.questions[0];
      return;
    }

    // Extract multidimensional divergence and circumplex dispersion across active V5 candidates
    const { candidateDivRatio, axis1Std, axis2Std } = this.getCandidateDivergenceV5();

    let bestQuestion: QuestionRecord | null = null;
    let maxGain = -Infinity;

    for (const q of this.questions) {
      if (this.askedQuestionIds.has(q.id)) continue;

      let gain = 0;
      for (let d = 0; d < DIM; d++) {
        const normW = Math.abs(q.gradient[d]) / this.gradMaxV2[d];
        if (normW <= 0.10) continue;

        // V5 Quadratic Evidence Precision: directly aligns with IRT information model
        const dPrec = normW * normW * 2.5;
        const curPrec = 1.0 / (this.userUncertainty[d] ** 2);
        const deltaVar = dPrec / (curPrec * (curPrec + dPrec));

        // Candidate Disambiguation Weight:
        // Early questions (< 4): foundational trait anchoring
        // Later questions (>= 4): discriminate between active candidate occupations
        const careerWeight = this.answeredHistory.length < 4 ? 0.25 : (candidateDivRatio[d] * 2.5);

        // Circumplex Macro-Axis Discrimination Bonus:
        // If candidate occupations diverge on Axis 1 (Transcendence vs Enhancement) or Axis 2 (Openness vs Conservation),
        // boost questions that discriminate those polar quadrants.
        let circumplexBonus = 1.0;
        if (axis1Std > 0.35 && ((d >= 18 && d <= 23) || (d >= 8 && d <= 12))) {
          circumplexBonus += Math.min(0.5, axis1Std);
        }
        if (axis2Std > 0.35 && ((d >= 5 && d <= 8) || (d >= 12 && d <= 18))) {
          circumplexBonus += Math.min(0.5, axis2Std);
        }

        // Foundational Big Five bonus in early stages (< 10 questions)
        const foundationalBonus = d < 5 ? (this.answeredHistory.length < 10 ? 1.25 : 1.10) : 1.0;

        // Trait Saturation Dampening:
        // When a trait already has high certainty (uncertainty < 0.25), dampen further exploration of it
        // so the test broadens and resolves other discriminating dimensions.
        const uncertaintyDamp = Math.min(1.0, this.userUncertainty[d] / 0.25);

        gain += deltaVar * (1.0 + careerWeight) * circumplexBonus * foundationalBonus * uncertaintyDamp;
      }

      if (gain > maxGain) {
        maxGain = gain;
        bestQuestion = q;
      }
    }

    this.currentQuestion = bestQuestion;
  }

  private recalculateMatches() {
    if (this.occupations.length === 0) return;
    const nJobs = this.occupations.length;

    const mahalanobisD2 = new Float32Array(nJobs);
    const rawFitScores = new Float32Array(nJobs);
    let minD2 = Infinity;

    // User Schwartz Circumplex Macro-Axes:
    // Theoretical foundation (Schwartz 1992, 2012; SchwartzCircle):
    // Boundary values straddle adjacent quadrants:
    // - Humility (18): shared by Self-Transcendence (18..23) and Conservation (12..18)
    // - Face (12): shared by Self-Enhancement (8..12) and Conservation (12..18)
    // - Hedonism (8): shared by Openness to Change (5..8) and Self-Enhancement (8..12)
    //
    // Axis 1: Self-Transcendence (18..23, 6 values) minus Self-Enhancement (8..12, 5 values)
    // Axis 2: Openness to Change (5..8, 4 values) minus Conservation (12..18, 7 values)
    let uTrans = 0, uEnh = 0, uOpen = 0, uCons = 0;
    for (let d = 18; d <= 23; d++) uTrans += (this.userVector[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
    uTrans /= 6;
    for (let d = 8; d <= 12; d++) uEnh += (this.userVector[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
    uEnh /= 5;
    const userAxis1 = uTrans - uEnh;

    for (let d = 5; d <= 8; d++) uOpen += (this.userVector[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
    uOpen /= 4;
    for (let d = 12; d <= 18; d++) uCons += (this.userVector[d] - this.popMean[d]) / (this.popStd[d] || 0.01);
    uCons /= 7;
    const userAxis2 = uOpen - uCons;

    for (let j = 0; j < nJobs; j++) {
      const occ = this.occupations[j];
      let sumD4 = 0;
      let specialistTerm = 0;
      let totalInfo = 0;
      let excessB5 = 0;
      let excessVal = 0;

      for (let d = 0; d < DIM; d++) {
        const infoD = Math.max(0, 1.0 - (this.userUncertainty[d] ** 2));
        totalInfo += infoD;

        // Centroid Normalization: distance is evaluated in occupational centroid space (between-job standard deviation)
        const zCentroid = (this.userVector[d] - occ.mean[d]) / (this.popStd[d] || 0.01);
        const careerTolerance = occ.regVariance[d] / (this.meanWithinVar[d] || 0.01);
        const effVar = careerTolerance + (this.userUncertainty[d] ** 2);
        const dimD2 = (zCentroid * zCentroid) / effVar;

        // Big Five operational boundary hurdle:
        // Working condition mismatches beyond 1.40 sigma (e.g. extreme extraversion/neuroticism clash)
        // register as an operational barrier
        if (d < 5 && infoD > 0.25) {
          const absZ = Math.abs(zCentroid);
          if (absZ > 1.40) {
            const exc = absZ - 1.40;
            excessB5 += exc * exc;
          }
        }

        // Schwartz Extreme Values boundary hurdle:
        // Acute single-trait clashes beyond 1.75 sigma (e.g. ruthless Power or hyper-Achievement for a humble user)
        // act as an ethical/motivational barrier without penalizing harmless vocabulary variance around 1.50 sigma
        if (d >= 5 && infoD > 0.25) {
          const absZ = Math.abs(zCentroid);
          if (absZ > 1.75) {
            const exc = absZ - 1.75;
            excessVal += exc * exc;
          }
        }

        // Symmetric L4 Metric: 4th power of occupational distance prevents single-trait extreme clashes
        // from being diluted away by neutral traits
        sumD4 += infoD * (dimD2 * dimD2);

        const distinctiveness = Math.min(1.0, Math.abs(occ.mean[d] - this.popMean[d]) / (this.popStd[d] || 0.01));
        const refVar = 1.0 + (this.userUncertainty[d] ** 2);
        const logRatio = Math.log(refVar / effVar);
        const rangeAdv = 1.0 - Math.min(2.0, dimD2);
        specialistTerm += infoD * distinctiveness * logRatio * rangeAdv;
      }

      // Root of order 4 (L4 norm) across effectively probed traits
      const effDist = Math.pow(sumD4 / (totalInfo || 1), 0.25);

      // Schwartz Circumplex Macro-Axis Hurdle:
      // Protects against polar value opposition (e.g. Humanitarian care vs Power dominance/conquest)
      let excessCircumplex = 0;
      const axis1Diff = Math.abs(userAxis1 - (occ.axis1 ?? 0));
      const axis2Diff = Math.abs(userAxis2 - (occ.axis2 ?? 0));
      const THRESHOLD = 0.85;
      if (axis1Diff > THRESHOLD) {
        excessCircumplex += (axis1Diff - THRESHOLD) ** 2;
      }
      if (axis2Diff > THRESHOLD) {
        excessCircumplex += (axis2Diff - THRESHOLD) ** 2;
      }
      
      // Multi-tier Operational Boundary Hurdle:
      // Working conditions (Big Five) + Macro value orientation (Circumplex) + Acute single-trait clash (Values)
      const penalizedDist = effDist 
        + 0.60 * Math.sqrt(excessB5) 
        + 0.50 * Math.sqrt(excessCircumplex)
        + 0.40 * Math.sqrt(excessVal);
      mahalanobisD2[j] = penalizedDist * penalizedDist;
      if (mahalanobisD2[j] < minD2) minD2 = mahalanobisD2[j];

      const normBonus = totalInfo > 0 ? (specialistTerm / totalInfo) : 0;
      // Calibrated sensitivity factor in centroid-normalized space
      const baseFit = 100 * Math.exp(-0.35 * penalizedDist);
      const rawFit = baseFit * (1.0 + 0.10 * Math.max(-0.35, Math.min(0.35, normBonus)));
      rawFitScores[j] = rawFit;
    }

    // 1. Sector Probabilities (Softmax over Double Mahalanobis distance)
    const sectorRawProbs = new Float32Array(8);
    let sumExp = 0;

    for (let j = 0; j < nJobs; j++) {
      // Gaussian RBF kernel exp(-0.5 * (d2 - minD2))
      const p = Math.exp(-0.5 * (mahalanobisD2[j] - minD2));
      sumExp += p;
      sectorRawProbs[this.occupations[j].sectorIndex] += p;
    }

    const sectorNames = sectorsData.sectors as string[];
    const newSectorScores: SectorScore[] = [];

    for (let s = 0; s < 8; s++) {
      const rawP = sectorRawProbs[s] / (sumExp || 1);
      const rawName = sectorNames[s] || 'Other';
      const name = SECTOR_DISPLAY_NAMES[rawName] || rawName;
      const color = SECTOR_COLORS[name] || '#ffffff';
      newSectorScores.push({
        name,
        color,
        percentage: Number((rawP * 100).toFixed(1)),
        rawProbability: rawP
      });
    }

    newSectorScores.sort((a, b) => b.percentage - a.percentage);
    this.sectorScores = newSectorScores;

    // Convergence metric: Bayesian variance reduction ratio
    let sumVar = 0;
    for (let d = 0; d < DIM; d++) {
      sumVar += this.userUncertainty[d] * this.userUncertainty[d];
    }
    const meanVar = sumVar / DIM;
    const reductionRatio = Math.max(0, 1.0 - meanVar);
    this.confidence = Math.max(0, Math.min(99, Math.round(reductionRatio * 100)));

    // 2. Occupation Matches with Unified Double Mahalanobis Fit & Specialist Tuning
    const scoredJobs = this.occupations.map((occ, j) => {
      const rawFit = rawFitScores[j];
      const matchScore = Math.max(25, Math.min(99, Math.round(rawFit)));

      // When alpha = 0 (Niche), totalScore = rawFit (strict 1:1 monotonic match with Fit %)
      // When alpha > 0 (Market), hiring scale smoothly elevates high-volume careers
      const totalScore = rawFit + this.alpha * occ.normPrior;

      const sectorName = SECTOR_DISPLAY_NAMES[occ.sectorName] || occ.sectorName;

      return {
        occ,
        title: occ.title,
        totalScore,
        matchScore,
        rawFit,
        sampleCount: occ.sampleCount,
        sectorName,
        sectorColor: SECTOR_COLORS[sectorName] || '#ffffff'
      };
    });

    // Extract top 25 candidates by rawFit (unbiased by market sample prior) for V5 adaptive discrimination
    this.topCandidatesV5 = [...scoredJobs].sort((a, b) => b.rawFit - a.rawFit).slice(0, 25).map(s => s.occ);

    scoredJobs.sort((a, b) => {
      if (Math.abs(b.totalScore - a.totalScore) > 1e-6) {
        return b.totalScore - a.totalScore;
      }
      return b.rawFit - a.rawFit;
    });

    this.topJobs = scoredJobs.map((job, idx) => ({
      rank: idx + 1,
      title: job.title,
      matchScore: job.matchScore,
      rawFit: job.rawFit,
      sampleCount: job.sampleCount,
      sectorName: job.sectorName,
      sectorColor: job.sectorColor
    }));
  }
}

// Global shared engine instance for seamless coordination across navbar and page
export const testEngine = new TestEngine();
