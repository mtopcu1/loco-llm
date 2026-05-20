import { create } from 'zustand'

interface AppStore {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  jobsTrayOpen: boolean
  setJobsTrayOpen: (open: boolean) => void
  selectedJobId: string | null
  setSelectedJobId: (id: string | null) => void
}

export const useAppStore = create<AppStore>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  jobsTrayOpen: true,
  setJobsTrayOpen: (open) => set({ jobsTrayOpen: open }),
  selectedJobId: null,
  setSelectedJobId: (id) => set({ selectedJobId: id }),
}))
