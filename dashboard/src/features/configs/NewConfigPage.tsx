import { Link } from '@tanstack/react-router'
import { ConfigForm } from './ConfigForm'

export function NewConfigPage() {
  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <Link to="/configs" className="text-sm text-zinc-500 hover:underline">
          ← Configs
        </Link>
        <h1 className="text-2xl font-semibold mt-1">New config</h1>
        <p className="text-sm text-zinc-500">
          Raw form for v1 — param grid wizard arrives in Plan 3.
        </p>
      </div>
      <ConfigForm mode="create" />
    </div>
  )
}
