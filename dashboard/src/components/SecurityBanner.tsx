import { useInsecure } from '@/store'

export function SecurityBanner() {
  const insecure = useInsecure()
  if (!insecure) return null
  return (
    <div className="bg-red-600 text-white px-4 py-2 text-sm sticky top-0 z-50 flex items-center gap-3">
      <span className="text-xl" aria-hidden>
        ⚠
      </span>
      <div className="flex-1">
        <div className="font-semibold">EXPOSED ON NETWORK</div>
        <div>
          This dashboard is reachable from other devices on this network. Anyone with the URL
          can manage your LocalLLM install.
        </div>
      </div>
      <a
        className="underline shrink-0"
        href="/docs/dashboard-security#risks"
        target="_blank"
        rel="noreferrer"
      >
        Why this is risky
      </a>
      <a
        className="underline shrink-0"
        href="/docs/dashboard-security#lockdown"
        target="_blank"
        rel="noreferrer"
      >
        How to lock down
      </a>
    </div>
  )
}
