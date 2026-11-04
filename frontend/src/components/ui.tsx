import { FileText, FolderSearch, Home, PlusCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react'

export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

export type AppView = 'overview' | 'setup' | 'workspace'

export function Shell({
  children,
  view,
  workspaceTab,
  hasJob,
  onNavigate,
}: PropsWithChildren<{
  view: AppView
  workspaceTab?: string
  hasJob?: boolean
  onNavigate: (v: AppView, opts?: { tab?: string }) => void
}>) {
  const nav = [
    { id: 'overview' as const, label: 'Home', short: 'Home', icon: Home, hint: 'Product overview' },
    {
      id: 'setup' as const,
      label: 'New Investigation',
      short: 'New',
      icon: PlusCircle,
      hint: 'Start a guided investigation',
    },
    {
      id: 'workspace' as const,
      label: 'Current Investigation',
      short: 'Current',
      icon: FolderSearch,
      hint: hasJob ? 'Progress and technical details for the open investigation' : 'No investigation open yet',
      tab: 'progress',
      key: 'current',
    },
    {
      id: 'workspace' as const,
      label: 'Results',
      short: 'Results',
      icon: FileText,
      hint: hasJob ? 'Simple and developer reports' : 'Open or finish an investigation to see results',
      tab: 'reports',
      key: 'results',
    },
  ]

  return (
    <div className="min-h-screen bg-rx-bg text-rx-text">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px]">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-rx-line bg-rx-beige px-3 py-5 min-[900px]:flex">
          <div className="mb-8 px-2">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rx-muted">ReverseX</p>
            <p className="mt-1 text-lg font-semibold tracking-tight text-rx-text">Engineer</p>
            <p className="mt-1 text-xs leading-relaxed text-rx-muted">AI Software Investigation Platform</p>
          </div>
          <nav className="flex flex-1 flex-col gap-1" aria-label="Primary">
            {nav.map((item) => {
              const Icon = item.icon
              const isResults = item.key === 'results'
              const isCurrent = item.key === 'current'
              const active = isResults
                ? view === 'workspace' && workspaceTab === 'reports'
                : isCurrent
                  ? view === 'workspace' && workspaceTab !== 'reports'
                  : view === item.id
              return (
                <button
                  key={item.key || item.label}
                  type="button"
                  onClick={() => onNavigate(item.id, item.tab ? { tab: item.tab } : undefined)}
                  className={cx(
                    'flex items-center gap-3 rounded-[12px] px-3 py-2.5 text-left text-sm transition',
                    active
                      ? 'bg-rx-blue-soft font-medium text-rx-blue'
                      : 'text-rx-muted hover:bg-white/70 hover:text-rx-text',
                  )}
                  aria-current={active ? 'page' : undefined}
                  title={item.hint}
                >
                  <Icon size={17} strokeWidth={1.75} aria-hidden />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
          <p className="mt-auto px-2 text-[11px] leading-relaxed text-rx-muted">
            Investigations in this session stay available while the local backend is running.
          </p>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-rx-line bg-rx-bg/90 px-4 py-3 backdrop-blur min-[900px]:hidden">
            <div>
              <p className="text-sm font-semibold">ReverseX Engineer</p>
              <p className="text-xs text-rx-muted">AI Software Investigation Platform</p>
            </div>
            <div className="flex flex-wrap justify-end gap-1">
              {nav.map((item) => (
                <button
                  key={`m-${item.key || item.label}`}
                  type="button"
                  onClick={() => onNavigate(item.id, item.tab ? { tab: item.tab } : undefined)}
                  className="rounded-lg border border-rx-line bg-white px-2.5 py-1.5 text-xs text-rx-muted"
                >
                  {item.short}
                </button>
              ))}
            </div>
          </header>
          <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </div>
  )
}

/** @deprecated Prefer Shell with sidebar; kept for compatibility during polish */
export function TopNav({
  view,
  onNavigate,
}: {
  view: string
  onNavigate: (v: 'overview' | 'setup' | 'workspace') => void
}) {
  return (
    <div className="mb-4 text-sm text-rx-muted">
      Active: {view}
      <button type="button" className="ml-2 underline" onClick={() => onNavigate('overview')}>
        Home
      </button>
    </div>
  )
}

export function Panel({
  children,
  className,
  title,
  action,
  tone = 'white',
}: PropsWithChildren<{
  className?: string
  title?: string
  action?: ReactNode
  tone?: 'white' | 'beige' | 'sage' | 'blue'
}>) {
  const surface =
    tone === 'beige'
      ? 'bg-rx-beige'
      : tone === 'sage'
        ? 'bg-rx-sage-soft'
        : tone === 'blue'
          ? 'bg-rx-blue-soft'
          : 'bg-rx-panel'
  return (
    <section
      className={cx(
        'rounded-[12px] border border-rx-line p-4 shadow-[0_1px_2px_rgba(38,50,56,0.04)] sm:p-5',
        surface,
        className,
      )}
    >
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title ? <h2 className="text-lg font-semibold tracking-tight text-rx-text">{title}</h2> : <span />}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Button({
  variant = 'secondary',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'success'
}) {
  return (
    <button
      {...props}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-[12px] px-4 py-2.5 text-sm font-medium transition disabled:cursor-wait disabled:opacity-55',
        variant === 'primary' && 'bg-rx-blue text-white hover:bg-rx-violet-dim',
        variant === 'secondary' &&
          'border border-rx-line bg-rx-beige text-rx-text hover:border-rx-blue/30 hover:bg-white',
        variant === 'ghost' && 'border border-transparent text-rx-muted hover:bg-rx-beige hover:text-rx-text',
        variant === 'success' && 'bg-rx-sage text-white hover:brightness-95',
        className,
      )}
    />
  )
}

export function StatusPill({ status }: { status: string }) {
  const s = status.toLowerCase()
  const tone =
    s === 'completed' ||
    s === 'pass' ||
    s === 'perfect' ||
    s === 'improved' ||
    s === 'verified' ||
    s === 'online' ||
    s === 'ready' ||
    s === 'approved'
      ? 'border-rx-sage/25 bg-rx-sage-soft text-rx-sage'
      : s === 'failed' || s === 'fail' || s === 'error' || s === 'regressed' || s === 'contradicted' || s === 'offline'
        ? 'border-rx-danger/25 bg-[#fef3f2] text-rx-danger'
        : s === 'incomplete' ||
            s === 'invalid' ||
            s === 'blocked' ||
            s === 'partially_verified' ||
            s === 'running' ||
            s === 'checking'
          ? 'border-rx-warn/25 bg-[#fff7ed] text-rx-warn'
          : 'border-rx-blue/20 bg-rx-blue-soft text-rx-blue'
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize',
        tone,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" aria-hidden />
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function StatCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-[12px] border border-rx-line bg-white p-3 shadow-[0_1px_2px_rgba(38,50,56,0.04)]">
      <p className="text-xs font-medium uppercase tracking-wide text-rx-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-rx-text">{value}</p>
      {hint && <p className="mt-1 text-xs text-rx-muted">{hint}</p>}
    </div>
  )
}

export function EmptyState({ children }: PropsWithChildren) {
  return <p className="text-sm leading-relaxed text-rx-muted">{children}</p>
}

export function Mono({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <code className={cx('break-all font-mono text-xs text-rx-muted', className)}>{children}</code>
}
