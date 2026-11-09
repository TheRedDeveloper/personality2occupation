export interface DimensionInfo {
  index: number;
  name: string;
  shortName: string;
  tier: 'behavior' | 'values';
  tierLabel: string;
  description: string;
  model: string;
}

export const DIMENSIONS: DimensionInfo[] = [
  // Tier 1: Behavioral Traits — Big Five (ModernBERT-large)
  {
    index: 0,
    name: 'Openness',
    shortName: 'Openness',
    tier: 'behavior',
    tierLabel: 'Big Five (Behavior)',
    description: 'Intellectual curiosity, aesthetic sensitivity, imagination vs. preference for routine.',
    model: 'ModernBERT-large (aleph-big5-fullp)'
  },
  {
    index: 1,
    name: 'Conscientiousness',
    shortName: 'Conscientiousness',
    tier: 'behavior',
    tierLabel: 'Big Five (Behavior)',
    description: 'Goal-directed persistence, organization, self-discipline vs. spontaneity.',
    model: 'ModernBERT-large (aleph-big5-fullp)'
  },
  {
    index: 2,
    name: 'Extraversion',
    shortName: 'Extraversion',
    tier: 'behavior',
    tierLabel: 'Big Five (Behavior)',
    description: 'Gregariousness, social assertiveness, positive emotional energy vs. quiet introspection.',
    model: 'ModernBERT-large (aleph-big5-fullp)'
  },
  {
    index: 3,
    name: 'Agreeableness',
    shortName: 'Agreeableness',
    tier: 'behavior',
    tierLabel: 'Big Five (Behavior)',
    description: 'Prosocial empathy, cooperation, trust vs. tough-minded, competitive detachment.',
    model: 'ModernBERT-large (aleph-big5-fullp)'
  },
  {
    index: 4,
    name: 'Neuroticism',
    shortName: 'Neuroticism',
    tier: 'behavior',
    tierLabel: 'Big Five (Behavior)',
    description: 'Emotional reactivity, stress sensitivity, vigilance vs. emotional stability.',
    model: 'ModernBERT-large (aleph-big5-fullp)'
  },

  // Tier 2: Motivational Values — Schwartz Refined Theory (RoBERTa-large)
  {
    index: 5,
    name: 'Self-direction: thought',
    shortName: 'SD: Thought',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: "Freedom to cultivate one's own ideas and intellectual independence.",
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 6,
    name: 'Self-direction: action',
    shortName: 'SD: Action',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: "Freedom to choose one's own actions and practical autonomy.",
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 7,
    name: 'Stimulation',
    shortName: 'Stimulation',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Excitement, novelty, challenge, and dynamic adventure in life.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 8,
    name: 'Hedonism',
    shortName: 'Hedonism',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Pleasure, sensuous gratification, and enjoying life.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 9,
    name: 'Achievement',
    shortName: 'Achievement',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Personal success through demonstrated competence according to social standards.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 10,
    name: 'Power: dominance',
    shortName: 'Power: Dominance',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Power through exercising control over people and leadership authority.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 11,
    name: 'Power: resources',
    shortName: 'Power: Resources',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Power through control over material and financial resources.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 12,
    name: 'Face',
    shortName: 'Face',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Maintaining public reputation, prestige, and avoiding embarrassment.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 13,
    name: 'Security: personal',
    shortName: 'Security: Personal',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: "Safety in one's immediate environment, stability, and health.",
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 14,
    name: 'Security: societal',
    shortName: 'Security: Societal',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Safety and stability in the wider society, social order, and rule of law.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 15,
    name: 'Tradition',
    shortName: 'Tradition',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: "Respect, commitment, and acceptance of the customs and ideas of one's culture.",
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 16,
    name: 'Conformity: rules',
    shortName: 'Conformity: Rules',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Compliance with rules, laws, and formal institutional regulations.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 17,
    name: 'Conformity: interpersonal',
    shortName: 'Conformity: Interpersonal',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Avoidance of upsetting or harming other people in direct interactions.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 18,
    name: 'Humility',
    shortName: 'Humility',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Recognizing one’s insignificance in the larger scheme of things; modesty.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 19,
    name: 'Benevolence: caring',
    shortName: 'Benevolence: Caring',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Devotion to the physical and emotional welfare of ingroup members.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 20,
    name: 'Benevolence: dependability',
    shortName: 'Benevolence: Dependability',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Being a reliable, trustworthy, and supportive friend or team member.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 21,
    name: 'Universalism: concern',
    shortName: 'Universalism: Concern',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Commitment to equality, justice, and protection for all human beings.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 22,
    name: 'Universalism: nature',
    shortName: 'Universalism: Nature',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Preservation of the natural environment, animals, and ecology.',
    model: 'RoBERTa-large (Touché 2024)'
  },
  {
    index: 23,
    name: 'Universalism: tolerance',
    shortName: 'Universalism: Tolerance',
    tier: 'values',
    tierLabel: 'Schwartz Human Values',
    description: 'Acceptance and understanding of individuals with differing beliefs and lifestyles.',
    model: 'RoBERTa-large (Touché 2024)'
  }
];

export interface SectorMeta {
  name: string;
  color: string;
  darkColor: string;
}

export const SECTOR_META: Record<number, SectorMeta> = {
  0: { name: 'Education, Academia & Science', color: '#4f46e5', darkColor: '#818cf8' },
  1: { name: 'Public Service, Law & Defense', color: '#475569', darkColor: '#94a3b8' },
  2: { name: 'Creative Arts, Design & Media', color: '#e11d48', darkColor: '#fb7185' },
  3: { name: 'Healthcare & Clinical Practice', color: '#059669', darkColor: '#34d399' },
  4: { name: 'Corporate, Finance & Commerce', color: '#d97706', darkColor: '#fbbf24' },
  5: { name: 'Technology & Engineering', color: '#0284c7', darkColor: '#38bdf8' },
  6: { name: 'Skilled Trades & Construction', color: '#ea580c', darkColor: '#fb923c' },
  7: { name: 'Writing & Journalism', color: '#9333ea', darkColor: '#c084fc' }
};
