import { useReducer, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { WizardContext } from './WizardContext'
import { StepParams } from './StepParams'
import { StepPickModel } from './StepPickModel'
import { StepPickRuntime } from './StepPickRuntime'
import { StepReview, reviewBlocksAdvance } from './StepReview'
import { StepSave } from './StepSave'
import type { ParamGridHandle } from '@/features/params/ParamGrid'
import {
  createInitialWizardState,
  validateStep,
  WIZARD_STEPS,
  wizardReducer,
} from './wizardState'

function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="flex flex-wrap gap-2 mb-6">
      {WIZARD_STEPS.map(({ step, label }) => (
        <li
          key={step}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium border',
            step === current
              ? 'bg-primary text-primary-foreground border-primary'
              : step < current
                ? 'bg-zinc-100 text-zinc-700'
                : 'text-zinc-400',
          )}
        >
          {step}. {label}
        </li>
      ))}
    </ol>
  )
}

export function NewConfigWizard() {
  const [state, dispatch] = useReducer(wizardReducer, undefined, createInitialWizardState)
  const paramsGridRef = useRef<ParamGridHandle>(null)

  const configs = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs')
      if (error) throw new Error('Failed to load configs')
      return (data ?? []) as Array<{ id: string }>
    },
    enabled: state.step === 4,
  })

  const idTaken =
    state.step === 4 &&
    state.configId.trim() !== '' &&
    (configs.data?.some((c) => c.id === state.configId) ?? false)

  const handleNext = () => {
    let working = state

    if (state.step === 3) {
      const cells = paramsGridRef.current?.getCells()
      if (!cells?.length) {
        dispatch({ type: 'setValidationError', error: 'Load parameters before continuing.' })
        return
      }
      working = { ...state, params: cells }
      dispatch({ type: 'setParams', params: cells })
    }

    const err = validateStep(working)
    if (err) {
      dispatch({ type: 'setValidationError', error: err })
      return
    }

    if (state.step === 4 && reviewBlocksAdvance(working, idTaken)) {
      dispatch({
        type: 'setValidationError',
        error: idTaken ? 'Choose a unique config ID.' : 'Config ID is required.',
      })
      return
    }

    dispatch({ type: 'setValidationError', error: null })
    dispatch({ type: 'next' })
  }

  const handleBack = () => dispatch({ type: 'back' })

  return (
    <WizardContext.Provider value={{ state, dispatch }}>
      <StepIndicator current={state.step} />

      {state.step === 1 && <StepPickRuntime />}
      {state.step === 2 && <StepPickModel />}
      {state.step === 3 && <StepParams ref={paramsGridRef} />}
      {state.step === 4 && <StepReview />}
      {state.step === 5 && <StepSave />}

      {state.validationError && (
        <p className="mt-4 text-sm text-red-600" role="alert">
          {state.validationError}
        </p>
      )}

      {state.step < 5 && (
        <div className="mt-6 flex gap-2">
          {state.step > 1 && (
            <Button type="button" variant="outline" onClick={handleBack}>
              Back
            </Button>
          )}
          <Button type="button" onClick={handleNext}>
            {state.step === 4 ? 'Save' : 'Next'}
          </Button>
        </div>
      )}
    </WizardContext.Provider>
  )
}
