import { Calculator, CheckCircle2, ChevronDown, ChevronUp, Hammer, Kanban, Search, ShieldCheck, Wand2 } from 'lucide-react'
import { useState } from 'react'
import type { HealthResponse } from '../api/types'
import { Button, Panel, StatusPill } from '../components/ui'

const workflow = [
  {
    title: 'Investigate',
    icon: Search,
    accent: 'bg-rx-blue-soft text-rx-blue',
    body: 'Explore how a supported sample application behaves through controlled browser steps and capture evidence.',
  },
  {
    title: 'Reconstruct',
    icon: Wand2,
    accent: 'bg-rx-sage-soft text-rx-sage',
    body: 'Recreate an independent version that aims to match the behaviors ReverseX observed.',
  },
  {
    title: 'Verify',
    icon: ShieldCheck,
    accent: 'bg-rx-blue-soft text-rx-blue',
    body: 'Replay the same actions against the original and the recreation, then score how well they match.',
  },
  {
    title: 'Repair',
    icon: Hammer,
    accent: 'bg-rx-sage-soft text-rx-sage',
    body: 'When tests fail, attempt targeted repairs and re-check the recreation.',
  },
]

export function OverviewPage({
  health,
  healthError,
  exploreBusy,
  exploreError,
  onStart,
  onExploreDemo,
}: {
  health: HealthResponse | null
  healthError: string | null
  exploreBusy?: boolean
  exploreError?: string | null
  onStart: () => void
  onExploreDemo: () => void
}) {
  const [showDiag, setShowDiag] = useState(false)
  const healthy = Boolean(health) && !healthError

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section className="rounded-[14px] border border-rx-line bg-white px-6 py-10 shadow-[0_1px_2px_rgba(38,50,56,0.04)] sm:px-10 sm:py-14">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-rx-blue">ReverseX Engineer</p>
        <h2 className="mt-4 font-serif text-4xl font-medium leading-[1.15] tracking-tight text-rx-text sm:text-5xl">
          Understand software.
          <br />
          Reconstruct behavior.
          <br />
          Verify results.
        </h2>
        <p className="mt-5 max-w-2xl text-base leading-relaxed text-rx-muted sm:text-lg">
          ReverseX investigates how supported software features behave, recreates them, and tests whether the
          recreated versions match.
        </p>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-rx-muted">
          Enter an approved local application URL (allowlisted 127.0.0.1 ports only), or try the built-in
          samples TaskBoard, MiniCalc, and ContactPad. Arbitrary public websites are not supported.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button variant="primary" onClick={onStart}>
            Start Investigation
          </Button>
          <Button variant="secondary" disabled={exploreBusy} onClick={onExploreDemo}>
            {exploreBusy ? 'Opening example…' : 'Explore Completed Example'}
          </Button>
        </div>
        {exploreError && (
          <p className="mt-4 rounded-[12px] border border-rx-danger/30 bg-[#fef3f2] px-3 py-2 text-sm text-rx-danger">
            {exploreError}
          </p>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Panel title="Sample applications" className="bg-white sm:col-span-2">
          <p className="mb-4 text-sm text-rx-muted">
            These are controlled local test applications ReverseX is allowed to investigate.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-[12px] border border-rx-line bg-rx-beige/60 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Kanban size={16} className="text-rx-blue" />
                <p className="font-semibold">TaskBoard</p>
              </div>
              <p className="text-sm leading-relaxed text-rx-muted">
                Explore how tasks are created, validated, and preserved after refreshing.
              </p>
            </div>
            <div className="rounded-[12px] border border-rx-line bg-rx-beige/60 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Calculator size={16} className="text-rx-blue" />
                <p className="font-semibold">MiniCalc</p>
              </div>
              <p className="text-sm leading-relaxed text-rx-muted">
                Explore how a calculator performs operations, handles inputs, and resets results.
              </p>
            </div>
            <div className="rounded-[12px] border border-rx-line bg-rx-beige/60 p-4 md:col-span-2">
              <p className="font-semibold">ContactPad, IT-Tools + allowlisted local URLs</p>
              <p className="mt-2 text-sm leading-relaxed text-rx-muted">
                Investigate ContactPad on port 8005, IT-Tools on port 8010, or another allowlisted local
                origin, with a feature description you choose.
              </p>
            </div>
          </div>
        </Panel>

        {workflow.map((item) => (
          <Panel key={item.title} className="bg-white">
            <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-[12px] ${item.accent}`}>
              <item.icon size={18} strokeWidth={1.75} />
            </div>
            <h3 className="text-base font-semibold text-rx-text">{item.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-rx-muted">{item.body}</p>
          </Panel>
        ))}
      </section>

      <Panel tone="beige">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <CheckCircle2 className={healthy ? 'text-rx-sage' : 'text-rx-warn'} size={18} />
            <div>
              <p className="text-sm font-medium text-rx-text">System status</p>
              <p className="text-xs text-rx-muted">
                {healthy
                  ? 'Backend online'
                  : healthError || 'Checking backend…'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill status={healthy ? 'online' : healthError ? 'offline' : 'checking'} />
            <Button variant="ghost" onClick={() => setShowDiag((v) => !v)}>
              Diagnostics {showDiag ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </Button>
          </div>
        </div>
        {showDiag && (
          <pre className="mt-4 overflow-x-auto rounded-[12px] border border-rx-line bg-white p-3 font-mono text-xs text-rx-muted">
            {health ? JSON.stringify(health, null, 2) : healthError || 'No health payload yet.'}
          </pre>
        )}
      </Panel>
    </div>
  )
}
