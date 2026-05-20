import { Link } from '@tanstack/react-router'
import { NewConfigWizard } from './wizard/NewConfigWizard'

export function NewConfigPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link to="/configs" className="text-sm text-zinc-500 hover:underline">
          ← Configs
        </Link>
        <h1 className="text-2xl font-semibold mt-1">Create a new config</h1>
      </div>
      <NewConfigWizard />
    </div>
  )
}
