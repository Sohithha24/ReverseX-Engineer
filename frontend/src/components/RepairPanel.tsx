import type { RepairReport } from '../api/types'

export function RepairPanel({ repair }: { repair: RepairReport | null }) {
  if (!repair) {
    return (
      <p className="muted">
        No repair results for this job. Repair runs only after real validation failures (or a labeled
        controlled evaluation).
      </p>
    )
  }

  const kindLabel =
    repair.evaluation_kind === 'controlled_fault_injection'
      ? 'Controlled Repair Evaluation (fault injection — not an organic Muse reconstruction failure)'
      : 'Pipeline repair after differential validation failures'

  return (
    <div className="repair-panel">
      <p className="eyebrow">{kindLabel}</p>
      <div className="stat-row">
        <div className="stat">
          <span className="stat-label">Initial match</span>
          <strong>
            {repair.initial_match_rate_percent == null
              ? '—'
              : `${repair.initial_match_rate_percent}%`}
          </strong>
        </div>
        <div className="stat">
          <span className="stat-label">Final match</span>
          <strong>
            {repair.final_match_rate_percent == null
              ? '—'
              : `${repair.final_match_rate_percent}%`}
          </strong>
        </div>
        <div className="stat">
          <span className="stat-label">Attempts</span>
          <strong>{repair.attempts?.length ?? 0}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Meta requests</span>
          <strong>{repair.meta_api_requests_total ?? 0}</strong>
        </div>
      </div>
      <p>
        Status: <span className="mono">{repair.stopped_reason || '—'}</span>
      </p>
      {!!repair.initial_failed?.length && (
        <p>
          Failed scenarios:{' '}
          <span className="mono">{repair.initial_failed.join(', ')}</span>
        </p>
      )}
      {(repair.attempts || []).map((a) => (
        <article key={a.attempt} className="test-card">
          <header>
            <h4>Attempt {a.attempt}</h4>
            <span className={`pill status-${a.status === 'perfect' || a.status === 'improved' ? 'pass' : a.status === 'error' || a.status === 'regressed' ? 'fail' : 'invalid'}`}>
              {a.status}
            </span>
          </header>
          <p>
            {a.prior_match_rate_percent ?? '—'}% → {a.new_match_rate_percent ?? '—'}%
            {a.accepted_as_best ? ' · accepted as best' : ''}
          </p>
          {!!a.newly_passed_tests?.length && (
            <p className="small">Newly passed: {a.newly_passed_tests.join(', ')}</p>
          )}
          {!!a.regressed_tests?.length && (
            <p className="error-text small">Regressed: {a.regressed_tests.join(', ')}</p>
          )}
          {!!a.remaining_failures?.length && (
            <p className="small">Remaining failures: {a.remaining_failures.join(', ')}</p>
          )}
          {!!a.changed_files?.length && (
            <p className="mono small">Changed: {a.changed_files.join(', ')}</p>
          )}
          {a.validation_artifact && (
            <p className="mono small">Evidence: {a.validation_artifact}</p>
          )}
          {a.error && <p className="error-text">{a.error}</p>}
        </article>
      ))}
      {!!repair.notes?.length && (
        <ul className="diff-list">
          {repair.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
