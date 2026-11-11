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
  version: 1 | 2;
  choices: number[];
}

/**
 * Ultra-compact 3-bit deterministic Base64URL encoding.
 * Since the test question selection is 100% deterministic given prior choices,
 * we only need to encode the 3-bit Likert choice (1..5 -> 0..4) for each step!
 *
 * Byte 0: format version (1 for v1 legacy, 2 for v2 modern)
 * Byte 1: question count (N)
 * Bytes 2+: bitstream of 3-bit choices (N * 3 bits packed MSB-first)
 *
 * Size: 5 questions = 6 chars, 9 questions = 8 chars, 30 questions = 19 chars!
 */
export function encodeResultChoices(history: AnswerHistoryItem[], version: 1 | 2 = 2): string {
  const count = history.length;
  if (count === 0) return '';

  const totalBits = count * 3;
  const payloadBytes = Math.ceil(totalBits / 8);
  const bytes = new Uint8Array(2 + payloadBytes);

  bytes[0] = version; // format version (1 or 2)
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
    if (version !== 1 && version !== 2) return null;

    const count = bytes[1];
    if (count === 0) return { version: version as 1 | 2, choices: [] };

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

    return { version: version as 1 | 2, choices };
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

  // Engine Version (1 for legacy replay, 2 for modern active testing)
  testVersion = $state<1 | 2>(2);

  // Core Data
  questions: QuestionRecord[] = [];
  occupations: OccupationRecord[] = [];
  popMean = new Float32Array(DIM);
  popStd = new Float32Array(DIM);
  gradMaxV1 = new Float32Array(DIM);
  gradMaxV2 = new Float32Array(DIM);
  totalWorkers = 0;

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
   * If version === 2, uses the modern V2 marginal variance reduction sequence.
   */
  private async reconstructFromChoices(choices: number[], version: 1 | 2) {
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
    this.testVersion = 2; // Always reset to modern v2 engine
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
    const weightedEvidenceSum = new Float32Array(DIM);
    for (let d = 0; d < DIM; d++) {
      weightedEvidenceSum[d] = this.popMean[d] * 1.0;
    }

    for (const item of this.answeredHistory) {
      for (let d = 0; d < DIM; d++) {
        const normW = item.question.gradient[d] / this.gradMaxV2[d];
        const weight = Math.abs(normW) * 1.75;
        if (weight > 0.01) {
          const evidence = Math.max(
            0.0,
            Math.min(1.0, this.popMean[d] + item.k * Math.sign(normW) * this.popStd[d] * 2.2)
          );
          weightedEvidenceSum[d] += weight * evidence;
          traitPrecision[d] += weight;
        }
      }
    }

    for (let d = 0; d < DIM; d++) {
      nextVector[d] = weightedEvidenceSum[d] / traitPrecision[d];
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

  private readStorage(): { version: 1 | 2; history: AnswerHistoryItem[]; alpha: number } | null {
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

      const version: 1 | 2 = data.version === 1 ? 1 : 2;
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
    } else {
      this.pickNextQuestionV2();
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

    const topCandidates = this.topJobs.slice(0, 30);
    const candidateDivergence = new Float32Array(DIM);

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
          candidateDivergence[d] = Math.sqrt(ssq / candidateOccs.length);
        }
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
        const uncertaintyWeight = this.userUncertainty[d];
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

  private recalculateMatches() {
    if (this.occupations.length === 0) return;
    const nJobs = this.occupations.length;

    const logLikelihoods = new Float32Array(nJobs);
    let maxLL = -Infinity;

    for (let j = 0; j < nJobs; j++) {
      const occ = this.occupations[j];
      let ll = 0;

      for (let d = 0; d < DIM; d++) {
        const totalVar = occ.variance[d] + (this.userUncertainty[d] ** 2) * (this.popStd[d] ** 2);
        const diff = this.userVector[d] - occ.mean[d];
        ll += -0.5 * ((diff * diff) / totalVar + Math.log(totalVar));
      }

      logLikelihoods[j] = ll;
      if (ll > maxLL) maxLL = ll;
    }

    // 1. Sector Probabilities (Softmax over Pure Likelihoods)
    const sectorRawProbs = new Float32Array(8);
    let sumExp = 0;

    for (let j = 0; j < nJobs; j++) {
      const p = Math.exp(logLikelihoods[j] - maxLL);
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

    // 2. Occupation Matches with Bayesian Prior Dial (alpha)
    const scoredJobs = this.occupations.map((occ, j) => {
      const logPrior = Math.log(occ.sampleCount / (this.totalWorkers || 1));
      const totalScore = logLikelihoods[j] + this.alpha * logPrior;

      let d2 = 0;
      for (let d = 0; d < DIM; d++) {
        const diff = (this.userVector[d] - occ.mean[d]) / (this.popStd[d] || 0.01);
        d2 += diff * diff;
      }
      const dist = Math.sqrt(d2);
      const matchScore = Math.max(25, Math.min(99, Math.round(100 * Math.exp(-0.038 * dist))));

      const sectorName = SECTOR_DISPLAY_NAMES[occ.sectorName] || occ.sectorName;

      return {
        title: occ.title,
        totalScore,
        matchScore,
        sampleCount: occ.sampleCount,
        sectorName,
        sectorColor: SECTOR_COLORS[sectorName] || '#ffffff'
      };
    });

    scoredJobs.sort((a, b) => b.totalScore - a.totalScore);

    this.topJobs = scoredJobs.map((job, idx) => ({
      rank: idx + 1,
      title: job.title,
      matchScore: job.matchScore,
      sampleCount: job.sampleCount,
      sectorName: job.sectorName,
      sectorColor: job.sectorColor
    }));
  }
}

// Global shared engine instance for seamless coordination across navbar and page
export const testEngine = new TestEngine();
