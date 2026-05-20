import type { ParamCell } from '@/lib/paramCell'

export type WizardStep = 1 | 2 | 3 | 4 | 5

export function proposeConfigId(runtimeId: string, modelId: string | null): string {
  const model = modelId ?? 'nomodel'
  return `${runtimeId}__${model}__default`
}

export interface WizardState {
  step: WizardStep
  runtimeId: string | null
  modelId: string | null
  params: ParamCell[] | null
  configId: string
  validationError: string | null
}

export type WizardAction =
  | { type: 'setRuntime'; runtimeId: string }
  | { type: 'setModel'; modelId: string | null }
  | { type: 'setParams'; params: ParamCell[] }
  | { type: 'setConfigId'; configId: string }
  | { type: 'goToStep'; step: WizardStep }
  | { type: 'setValidationError'; error: string | null }
  | { type: 'next' }
  | { type: 'back' }

export const WIZARD_STEPS: { step: WizardStep; label: string }[] = [
  { step: 1, label: 'Runtime' },
  { step: 2, label: 'Model' },
  { step: 3, label: 'Params' },
  { step: 4, label: 'Review' },
  { step: 5, label: 'Save' },
]

export function createInitialWizardState(): WizardState {
  return {
    step: 1,
    runtimeId: null,
    modelId: null,
    params: null,
    configId: '',
    validationError: null,
  }
}

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'setRuntime':
      return {
        ...state,
        runtimeId: action.runtimeId,
        modelId: null,
        params: null,
        configId: proposeConfigId(action.runtimeId, null),
        validationError: null,
      }
    case 'setModel': {
      const configId = state.runtimeId
        ? proposeConfigId(state.runtimeId, action.modelId)
        : state.configId
      return {
        ...state,
        modelId: action.modelId,
        params: null,
        configId,
        validationError: null,
      }
    }
    case 'setParams':
      return { ...state, params: action.params, validationError: null }
    case 'setConfigId':
      return { ...state, configId: action.configId, validationError: null }
    case 'goToStep':
      return { ...state, step: action.step, validationError: null }
    case 'setValidationError':
      return { ...state, validationError: action.error }
    case 'next':
      return state.step < 5
        ? { ...state, step: (state.step + 1) as WizardStep, validationError: null }
        : state
    case 'back':
      return state.step > 1
        ? { ...state, step: (state.step - 1) as WizardStep, validationError: null }
        : state
    default:
      return state
  }
}

export function validateStep(state: WizardState): string | null {
  switch (state.step) {
    case 1:
      if (!state.runtimeId) return 'Select an installed runtime to continue.'
      return null
    case 2:
      return null
    case 3:
      if (!state.params || state.params.length === 0) return 'Load parameters before continuing.'
      return null
    case 4:
      if (!state.configId.trim()) return 'Config ID is required.'
      if (!state.runtimeId) return 'Runtime is required.'
      if (!state.params) return 'Parameters are required.'
      return null
    default:
      return null
  }
}
