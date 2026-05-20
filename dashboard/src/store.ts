import { create } from 'zustand'

interface AppStore {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  jobsTrayOpen: boolean
  setJobsTrayOpen: (open: boolean) => void
}

export const useAppStore = create<AppStore>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  jobsTrayOpen: false,
  setJobsTrayOpen: (open) => set({ jobsTrayOpen: open }),
}))
