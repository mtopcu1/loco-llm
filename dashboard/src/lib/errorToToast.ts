import { toast } from 'sonner'
import { getApiError } from '@/lib/apiError'

const HINT_RE = /^(GET|POST|PUT|DELETE)\s+(\/api\/.+)$/

function parseFixHint(hint: string | null | undefined) {
  if (!hint) return null
  const m = HINT_RE.exec(hint)
  if (!m) return null
  return { method: m[1] as 'GET' | 'POST' | 'PUT' | 'DELETE', path: m[2] }
}

async function executeFixHint(parsed: { method: string; path: string }) {
  if (parsed.method !== 'POST') return
  try {
    const r = await fetch(parsed.path, { method: 'POST' })
    if (r.ok) toast.success('Fix applied')
    else toast.error('Fix failed', { description: await r.text() })
  } catch (e) {
    toast.error('Fix failed', { description: String(e) })
  }
}

const TITLES: Record<string, string> = {
  RUNTIME_ALREADY_INSTALLED: 'Runtime already installed',
  RUNTIME_IN_USE: 'Runtime in use',
  RUNTIME_NOT_FOUND: 'Runtime not found',
  RUNTIME_NOT_INSTALLED: 'Runtime not installed',
  MODEL_ALREADY_REGISTERED: 'Model already registered',
  MODEL_PULL_INVALID_URL: 'Invalid model URL',
  MODEL_NOT_FOUND: 'Model not found',
  CONFIG_ALREADY_EXISTS: 'Config already exists',
  CONFIG_INVALID: 'Configuration invalid',
  CONFIG_IN_USE: 'Config is currently running',
  CONFIG_NOT_FOUND: 'Config not found',
  INSTANCE_FOREGROUND_NOT_SWITCHABLE: 'Cannot switch foreground instance',
  INSTANCE_FOREGROUND_NOT_STOPPABLE: 'Cannot stop foreground instance',
  INSTANCE_ALREADY_RUNNING: 'Instance already running',
  INSTANCE_NOT_RUNNING: 'Instance not running',
  JOB_NOT_FOUND: 'Job not found',
  JOB_NOT_CANCELABLE: 'Job cannot be cancelled',
  SETTINGS_UNKNOWN_KEY: 'Unknown setting',
  SETTINGS_VALIDATION_FAILED: 'Setting validation failed',
  VALIDATION_ERROR: 'Validation error',
  NOT_FOUND: 'Not found',
  CONFLICT: 'Conflict',
  INTERNAL_ERROR: 'Internal error',
}

export function errorToToast(err: unknown) {
  const body = getApiError(err)
  if (body) {
    const fix = parseFixHint(body.fix_hint)
    toast.error(TITLES[body.code] ?? body.code, {
      description: body.message,
      action: fix ? { label: 'Fix', onClick: () => void executeFixHint(fix) } : undefined,
    })
    return
  }
  toast.error('Request failed', { description: String(err) })
}
