'use client'

import { Sidebar } from './sidebar'
import { Topbar } from './topbar'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="grid min-h-screen w-full bg-slate-50 text-slate-900 lg:grid-cols-[280px_1fr] dark:bg-slate-950 dark:text-slate-50">
      <aside className="hidden lg:block">
        <Sidebar />
      </aside>
      <div className="flex flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto bg-slate-50 p-6 dark:bg-slate-950">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  )
}
