export type InstanceStatus = { running?: boolean; config_id?: string; mode?: string }

export function StatusPill({ instance }: { instance: InstanceStatus | undefined }) {
  if (!instance || !instance.running) {
    return <span className="text-xs rounded-full bg-zinc-200 px-2 py-0.5">idle</span>
  }
  return (
    <span className="text-xs rounded-full bg-green-100 text-green-800 px-2 py-0.5">
      running: {instance.config_id} ({instance.mode})
    </span>
  )
}
