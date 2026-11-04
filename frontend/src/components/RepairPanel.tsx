import type { RepairReport } from '../api/types'
import { EmptyState, StatCard, StatusPill } from './ui'

export function RepairPanel({
  repair,
  controlledExample = false,
}: {
  repair: RepairReport | null
  controlledExample?: boolean
}) {
  if (!repair) {
    return (
      <EmptyState>
        {controlledExample
          ? 'The controlled repair example is unavailable right now. Confirm the local backend can serve /api/demo/controlled-repair.'
          : 'No repair was recorded for this investigation. Repair runs after real validation failures, or you can open the separate Controlled Repair Example.'}
      </EmptyState>
    )
  }

  const isControlled =
    controlledExample || repair.evaluation_kind === 'controlled_fault_injection'
  const kindLabel = isControlled ? 'Controlled Repair Example' : 'Investigation repair'

  return (
    <div className="space-y-5">
      <div className="rounded-[12px] border border-rx-blue/25 bg-rx-blue-soft px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-rx-blue">{kindLabel}</p>
        <p className="mt-1 text-sm text-rx-muted">
          {isControlled
            ? 'This example deliberately introduces a defect into a reconstruction so ReverseX can demonstrate detecting and correcting it — not an organically occurring Muse reconstruction failure.'
            : 'Repair driven by recorded validation failures from this investigation.'}
        </p>
        <p className="mt-2 text-sm font-medium">{repair.label}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Initial match"
          value={
            repair.initial_match_rate_percent == null ? '—' : `${repair.initial_match_rate_percent}%`
          }
        />
        <StatCard
          label="Final match"
          value={repair.final_match_rate_percent == null ? '—' : `${repair.final_match_rate_percent}%`}
        />
        <StatCard label="Repair attempts" value={repair.attempts?.length ?? 0} />
        <StatCard label="Meta requests" value={repair.meta_api_requests_total ?? 0} />
      </div>

      <div className="text-sm text-rx-muted">
        <p>
          Stopped reason: <span className="font-mono text-rx-text">{repair.stopped_reason || '—'}</span>
        </p>
        {!!repair.initial_failed?.length && (
          <p className="mt-2">
            Failed tests:{' '}
            <span className="font-mono text-rx-text">{repair.initial_failed.join(', ')}</span>
          </p>
        )}
      </div>

      <div className="space-y-3">
        {(repair.attempts || []).map((a) => (
          <article key={a.attempt} className="rounded-[12px] border border-rx-line bg-white p-4">
            <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-semibold">Attempt {a.attempt}</h4>
              <StatusPill status={String(a.status || 'unknown')} />
            </header>
            <p className="text-sm tabular-nums">
              {a.prior_match_rate_percent ?? '—'}% → {a.new_match_rate_percent ?? '—'}%
              {a.accepted_as_best ? ' · accepted as best' : ''}
            </p>
            {!!a.newly_passed_tests?.length && (
              <p className="mt-2 text-xs text-rx-ok">Newly passed: {a.newly_passed_tests.join(', ')}</p>
            )}
            {!!a.regressed_tests?.length && (
              <p className="mt-1 text-xs text-rx-danger">Regressed: {a.regressed_tests.join(', ')}</p>
            )}
            {!!a.remaining_failures?.length && (
              <p className="mt-1 text-xs text-rx-muted">Remaining: {a.remaining_failures.join(', ')}</p>
            )}
            {!!a.changed_files?.length && (
              <p className="mt-2 font-mono text-xs text-rx-muted">Changed: {a.changed_files.join(', ')}</p>
            )}
            {a.error && <p className="mt-2 text-xs text-rx-danger">{a.error}</p>}
          </article>
        ))}
      </div>

      {!!repair.notes?.length && (
        <ul className="space-y-1 text-xs text-rx-muted">
          {repair.notes.map((n) => (
            <li key={n}>• {shortenPathNote(n)}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function shortenPathNote(note: string): string {
  return note.replace(/[A-Za-z]:\\[^\s]+/g, (path) => {
    const parts = path.split(/[/\\]/)
    return parts.slice(-3).join('/')
  })
}
