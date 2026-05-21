import type { ReactNode } from 'react'
import { JobDetailSheet } from '@/features/jobs/JobDetailSheet'
import { useJobNotifications } from '@/hooks/useJobNotifications'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { SecurityBanner } from './SecurityBanner'

export function Layout({ children }: { children: ReactNode }) {
  useJobNotifications()
  return (
    <div className="min-h-screen flex flex-col">
      <SecurityBanner />
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
      <JobDetailSheet />
    </div>
  )
}
