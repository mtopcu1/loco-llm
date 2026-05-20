import { Link } from '@tanstack/react-router'
import { useAppStore } from '@/store'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/runtimes', label: 'Runtimes' },
  { to: '/models', label: 'Models' },
  { to: '/configs', label: 'Configs' },
  { to: '/instance', label: 'Instance' },
  { to: '/doctor', label: 'Doctor' },
  { to: '/disk', label: 'Disk' },
  { to: '/history', label: 'History' },
  { to: '/settings', label: 'Settings' },
]

export function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  return (
    <nav className={cn(
      "border-r bg-white shrink-0 transition-all",
      collapsed ? "w-12" : "w-56",
    )}>
      <ul className="p-2 space-y-1">
        {NAV.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              className="block rounded px-3 py-1.5 text-sm hover:bg-zinc-100"
              activeProps={{ className: "bg-zinc-100 font-medium" }}
            >
              {!collapsed && item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
