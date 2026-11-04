import { api } from '../api/client'
import type { ScreenshotItem, ValidationResultsFile } from '../api/types'
import { EmptyState, StatCard, StatusPill } from './ui'

function filenameFromPath(path?: string | null): string | null {
  if (!path) return null
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || null
}

export function ValidationPanel({
  validation,
  investigationId,
  screenshots,
}: {
  validation: ValidationResultsFile | null
  investigationId: string | null
  screenshots: ScreenshotItem[]
}) {
  if (!validation) {
    return <EmptyState>Validation results are not available for this run yet.</EmptyState>
  }

  const rate = validation.behavioral_match_rate_percent
  const shotByName = new Map(screenshots.map((s) => [s.filename, s]))

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Passed" value={validation.passed ?? '—'} />
        <StatCard label="Failed" value={validation.failed ?? '—'} />
        <StatCard label="Invalid" value={validation.invalid ?? '—'} />
        <StatCard
          label="Behavioral match"
          value={rate == null ? 'unavailable' : `${rate}%`}
          hint="From recorded validation artifact — never hardcoded"
        />
      </div>

      <div className="space-y-4">
        {(validation.tests || []).map((test) => {
          const origFile = filenameFromPath(test.original?.screenshot)
          const reconFile = filenameFromPath(test.reconstruction?.screenshot)
          const origShot = origFile ? shotByName.get(origFile) : undefined
          const reconShot = reconFile ? shotByName.get(reconFile) : undefined
          return (
            <article
              key={test.test_id}
              className={
                test.status === 'pass'
                  ? 'rounded-[12px] border border-rx-sage/25 bg-rx-sage-soft p-4'
                  : test.status === 'fail'
                    ? 'rounded-[12px] border border-rx-danger/25 bg-[#fef3f2] p-4'
                    : 'rounded-[12px] border border-rx-warn/25 bg-[#fff7ed] p-4'
              }
            >
              <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h4 className="font-semibold text-rx-text">{test.test_id}</h4>
                <StatusPill status={test.status} />
              </header>
              {test.description && (
                <p className="mb-3 text-sm text-rx-muted">
                  <span className="font-medium text-rx-text">What was tested: </span>
                  {test.description}
                </p>
              )}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-[12px] border border-rx-line bg-white p-3">
                  <h5 className="mb-2 text-xs font-medium uppercase tracking-wide text-rx-muted">
                    Original result
                  </h5>
                  <pre className="max-h-40 overflow-auto font-mono text-xs text-rx-muted">
                    {JSON.stringify(test.original?.observed_state || {}, null, 2)}
                  </pre>
                  {investigationId && origShot && (
                    <img
                      src={api.screenshotUrl(investigationId, origShot.filename)}
                      alt={`${test.test_id} original`}
                      className="mt-2 max-h-48 w-full rounded-lg border border-rx-line object-cover object-top"
                    />
                  )}
                  {test.original?.error && <p className="mt-2 text-xs text-rx-danger">{test.original.error}</p>}
                </div>
                <div className="rounded-[12px] border border-rx-line bg-white p-3">
                  <h5 className="mb-2 text-xs font-medium uppercase tracking-wide text-rx-muted">
                    Reconstructed result
                  </h5>
                  <pre className="max-h-40 overflow-auto font-mono text-xs text-rx-muted">
                    {JSON.stringify(test.reconstruction?.observed_state || {}, null, 2)}
                  </pre>
                  {investigationId && reconShot && (
                    <img
                      src={api.screenshotUrl(investigationId, reconShot.filename)}
                      alt={`${test.test_id} reconstruction`}
                      className="mt-2 max-h-48 w-full rounded-lg border border-rx-line object-cover object-top"
                    />
                  )}
                  {test.reconstruction?.error && (
                    <p className="mt-2 text-xs text-rx-danger">{test.reconstruction.error}</p>
                  )}
                </div>
              </div>
              {!!test.differences?.length && (
                <div className="mt-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-rx-muted">Observed difference</p>
                  <ul className="mt-1 space-y-1 text-xs text-rx-warn">
                    {test.differences.map((d) => (
                      <li key={d}>• {d}</li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
