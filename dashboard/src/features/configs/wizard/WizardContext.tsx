import { createContext, useContext, type Dispatch } from 'react'
import type { WizardAction, WizardState } from './wizardState'

export type WizardContextValue = {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

export const WizardContext = createContext<WizardContextValue | null>(null)

export function useWizard() {
  const ctx = useContext(WizardContext)
  if (!ctx) throw new Error('useWizard must be used within NewConfigWizard')
  return ctx
}
