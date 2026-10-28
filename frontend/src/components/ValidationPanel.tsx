import { api } from '../api/client'
import type { ScreenshotItem, ValidationResultsFile } from '../api/types'

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
    return <p className="muted">Validation results are not available for this run yet.</p>
  }

  const rate = validation.behavioral_match_rate_percent
  const shotByName = new Map(screenshots.map((s) => [s.filename, s]))

  return (
    <div className="validation-panel">
      <div className="stat-row">
        <div className="stat">
          <span className="stat-label">Passed</span>
          <strong>{validation.passed ?? '—'}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Failed</span>
          <strong>{validation.failed ?? '—'}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Invalid</span>
          <strong>{validation.invalid ?? '—'}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Match rate</span>
          <strong>
            {rate == null ? 'unavailable' : `${rate}%`}
          </strong>
        </div>
      </div>

      {(validation.tests || []).map((test) => {
        const origFile = filenameFromPath(test.original?.screenshot)
        const reconFile = filenameFromPath(test.reconstruction?.screenshot)
        const origShot = origFile ? shotByName.get(origFile) : undefined
        const reconShot = reconFile ? shotByName.get(reconFile) : undefined
        return (
          <article key={test.test_id} className="test-card">
            <header>
              <h4>{test.test_id}</h4>
              <span className={`pill status-${test.status}`}>{test.status}</span>
            </header>
            <p>{test.description}</p>
            <div className="compare-grid">
              <div>
                <h5>Original</h5>
                <pre>{JSON.stringify(test.original?.observed_state || {}, null, 2)}</pre>
                {investigationId && origShot && (
                  <img
                    src={api.screenshotUrl(investigationId, origShot.filename)}
                    alt={`${test.test_id} original`}
                  />
                )}
                {test.original?.error && <p className="error-text">{test.original.error}</p>}
              </div>
              <div>
                <h5>Reconstruction</h5>
                <pre>{JSON.stringify(test.reconstruction?.observed_state || {}, null, 2)}</pre>
                {investigationId && reconShot && (
                  <img
                    src={api.screenshotUrl(investigationId, reconShot.filename)}
                    alt={`${test.test_id} reconstruction`}
                  />
                )}
                {test.reconstruction?.error && (
                  <p className="error-text">{test.reconstruction.error}</p>
                )}
              </div>
            </div>
            {!!test.differences?.length && (
              <ul className="diff-list">
                {test.differences.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            )}
          </article>
        )
      })}
    </div>
  )
}
