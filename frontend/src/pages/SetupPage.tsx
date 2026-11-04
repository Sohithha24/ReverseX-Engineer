import { Calculator, Kanban, Mail, Sparkles, Wrench, Zap } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type {
  AuthorizedTarget,
  CreateInvestigationRequest,
  InvestigationGoal,
  InvestigationMode,
  Pipeline,
  ResolveTargetResponse,
  TargetId,
} from '../api/types'
import { Button, EmptyState, Mono, Panel, StatusPill, cx } from '../components/ui'

type UiMode = 'demo' | 'live'
type EntryMode = 'custom' | 'sample'

const SAMPLE_COPY: Record<string, { title: string; blurb: string; icon: typeof Kanban }> = {
  taskboard: {
    title: 'TaskBoard',
    blurb: 'Explore how tasks are created, validated, and preserved after refreshing.',
    icon: Kanban,
  },
  calculator: {
    title: 'MiniCalc',
    blurb: 'Explore how a calculator performs operations, handles inputs, and resets results.',
    icon: Calculator,
  },
  contactpad: {
    title: 'ContactPad',
    blurb: 'Explore how a contact form validates fields and confirms a sent message.',
    icon: Mail,
  },
  'it-tools': {
    title: 'IT-Tools',
    blurb: 'Third-party local container. Investigate Base64 text encoding and decoding.',
    icon: Wrench,
  },
}

export function SetupPage({
  targets,
  targetsError,
  busy,
  onStart,
}: {
  targets: AuthorizedTarget[]
  targetsError: string | null
  busy: boolean
  onStart: (payload: CreateInvestigationRequest) => void
}) {
  const [entryMode, setEntryMode] = useState<EntryMode>('custom')
  const [applicationUrl, setApplicationUrl] = useState('http://127.0.0.1:8005/')
  const [feature, setFeature] = useState('Submit a contact message and view confirmation')
  const [goal, setGoal] = useState<InvestigationGoal>('understand')
  const [resolveInfo, setResolveInfo] = useState<ResolveTargetResponse | null>(null)
  const [resolveError, setResolveError] = useState<string | null>(null)
  const [resolving, setResolving] = useState(false)

  const [targetId, setTargetId] = useState<TargetId>('taskboard')
  const [uiMode, setUiMode] = useState<UiMode>('demo')
  const [maxActions, setMaxActions] = useState(10)
  const [pipeline, setPipeline] = useState<Pipeline>('full')
  const [reuseReconstruction, setReuseReconstruction] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    if (targets.length && !targets.some((t) => t.id === targetId)) {
      setTargetId(targets[0].id)
    }
  }, [targets, targetId])

  const selected = useMemo(
    () => targets.find((t) => t.id === targetId) ?? targets[0] ?? null,
    [targets, targetId],
  )

  const activeCapabilityTarget = useMemo(() => {
    if (entryMode === 'sample') return selected
    if (resolveInfo?.target_id) {
      return targets.find((t) => t.id === resolveInfo.target_id) ?? null
    }
    const url = applicationUrl.trim().toLowerCase()
    return (
      targets.find((t) => url.startsWith(t.origin.toLowerCase().replace(/\/$/, ''))) ?? null
    )
  }, [entryMode, selected, resolveInfo, targets, applicationUrl])

  useEffect(() => {
    if (selected && !selected.reuse_reconstruction_allowed) {
      setReuseReconstruction(false)
    } else if (uiMode === 'demo' && selected?.reuse_reconstruction_allowed) {
      setReuseReconstruction(true)
    }
  }, [selected, uiMode])

  useEffect(() => {
    if (goal === 'understand') {
      setPipeline('investigate_only')
    } else if (pipeline === 'investigate_only') {
      setPipeline('full')
    }
    // Keep pipeline in sync with goal so Advanced settings cannot silently contradict the radios.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goal])

  async function checkUrl() {
    setResolving(true)
    setResolveError(null)
    try {
      const result = await api.resolveTarget({
        application_url: applicationUrl.trim(),
        feature: feature.trim() || undefined,
      })
      setResolveInfo(result)
    } catch (e) {
      setResolveInfo(null)
      setResolveError(friendlyError(e instanceof Error ? e.message : String(e)))
    } finally {
      setResolving(false)
    }
  }

  function submit() {
    const mode: InvestigationMode = uiMode === 'demo' ? 'scripted' : 'muse'
    if (entryMode === 'custom') {
      if (!applicationUrl.trim() || !feature.trim()) return
      onStart({
        mode,
        pipeline: goal === 'understand' ? 'investigate_only' : pipeline,
        reuse_reconstruction: false,
        max_actions: maxActions,
        application_url: applicationUrl.trim(),
        feature: feature.trim(),
        investigation_goal: goal,
      })
      return
    }
    if (!selected) return
    onStart({
      target_id: selected.id,
      max_actions: maxActions,
      mode,
      pipeline: goal === 'understand' ? 'investigate_only' : pipeline,
      reuse_reconstruction:
        uiMode === 'live'
          ? false
          : selected.reuse_reconstruction_allowed
            ? reuseReconstruction
            : false,
      feature: selected.description,
      investigation_goal: goal,
    })
  }

  const canLaunchCustom = Boolean(applicationUrl.trim() && feature.trim() && !busy)
  const canLaunchSample = Boolean(selected && !busy)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Start an Investigation</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-rx-muted">
          Connect an approved local application URL, describe the feature to investigate, and let ReverseX
          explore it. Only allowlisted local hosts and ports are accepted — not arbitrary public websites.
        </p>
      </div>

      <Panel title="Investigate your application">
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setEntryMode('custom')}
            className={cx(
              'rounded-[12px] border px-3 py-2 text-sm',
              entryMode === 'custom'
                ? 'border-rx-blue/40 bg-rx-blue-soft font-medium text-rx-blue'
                : 'border-rx-line bg-white text-rx-muted',
            )}
          >
            Use application URL
          </button>
          <button
            type="button"
            onClick={() => setEntryMode('sample')}
            className={cx(
              'rounded-[12px] border px-3 py-2 text-sm',
              entryMode === 'sample'
                ? 'border-rx-blue/40 bg-rx-blue-soft font-medium text-rx-blue'
                : 'border-rx-line bg-white text-rx-muted',
            )}
          >
            Use a sample card below
          </button>
        </div>

        {entryMode === 'custom' && (
          <div className="grid gap-4">
            <label className="block text-sm">
              <span className="font-medium text-rx-text">Application URL</span>
              <input
                value={applicationUrl}
                onChange={(e) => {
                  setApplicationUrl(e.target.value)
                  setResolveInfo(null)
                  setResolveError(null)
                }}
                placeholder="http://127.0.0.1:8005/"
                className="mt-1 w-full rounded-[12px] border border-rx-line bg-white px-3 py-2 text-rx-text"
              />
              <span className="mt-1 block text-xs text-rx-muted">
                Approved examples: http://127.0.0.1:8001/ (TaskBoard), :8003/ (MiniCalc), :8005/
                (ContactPad), :8010/ (IT-Tools).
              </span>
            </label>

            <label className="block text-sm">
              <span className="font-medium text-rx-text">Feature to investigate</span>
              <input
                value={feature}
                onChange={(e) => setFeature(e.target.value)}
                placeholder="Describe the feature ReverseX should focus on"
                className="mt-1 w-full rounded-[12px] border border-rx-line bg-white px-3 py-2 text-rx-text"
              />
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" disabled={resolving || !applicationUrl.trim()} onClick={() => void checkUrl()}>
                {resolving ? 'Checking…' : 'Check if URL is approved'}
              </Button>
              {resolveInfo && <StatusPill status="approved" />}
            </div>
            {resolveInfo && (
              <div className="rounded-[12px] border border-rx-sage/30 bg-rx-sage-soft px-3 py-2 text-sm text-rx-text">
                Approved: <strong>{resolveInfo.label}</strong> ({resolveInfo.origin}). Feature focus:{' '}
                {resolveInfo.feature}. Independent validation:{' '}
                {resolveInfo.independent_validation_available ? 'available' : 'unavailable for this app'}.
              </div>
            )}
            {resolveError && (
              <p className="rounded-[12px] border border-rx-danger/30 bg-[#fef3f2] px-3 py-2 text-sm text-rx-danger">
                {resolveError}
              </p>
            )}
          </div>
        )}

        {entryMode === 'sample' && selected && (
          <div className="rounded-[12px] border border-rx-line bg-rx-beige/40 px-3 py-2 text-sm text-rx-text">
            Selected sample: <strong>{selected.label || selected.id}</strong> ({selected.origin}). Feature focus
            uses the sample description. Change the investigation goal below before launching.
          </div>
        )}

        <fieldset className="mt-4 grid gap-2">
          <legend className="text-sm font-medium text-rx-text">Investigation goal</legend>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="goal"
              checked={goal === 'understand'}
              onChange={() => setGoal('understand')}
              className="mt-1"
            />
            <span>
              <span className="font-medium">Understand</span>
              <span className="mt-0.5 block text-xs text-rx-muted">
                Investigate and report observations only. No reconstruction or validation claims.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="goal"
              checked={goal === 'understand_and_reconstruct'}
              onChange={() => {
                setGoal('understand_and_reconstruct')
                setPipeline('full')
              }}
              className="mt-1"
            />
            <span>
              <span className="font-medium">Understand and reconstruct</span>
              <span className="mt-0.5 block text-xs text-rx-muted">
                Investigate, then generate an independent recreation. Independent original-vs-recreation scoring
                runs only for samples with a built-in test suite (TaskBoard, MiniCalc).
              </span>
            </span>
          </label>
          {goal === 'understand_and_reconstruct' &&
            activeCapabilityTarget &&
            activeCapabilityTarget.independent_validation_available === false && (
              <p className="rounded-[12px] border border-rx-line bg-rx-beige px-3 py-2 text-xs text-rx-muted">
                Reconstruction can still be requested for this app, but ReverseX will not claim independent
                validation or accuracy scores because no fixture oracle is configured for{' '}
                <strong>{activeCapabilityTarget.label || activeCapabilityTarget.id}</strong>.
              </p>
            )}
          {goal === 'understand' && (
            <p className="text-xs text-rx-muted">
              Backend pipeline will be set to investigate-only. Reconstruction stages will be skipped intentionally.
            </p>
          )}
        </fieldset>
      </Panel>

      <Panel title="Try a sample application">
        {targetsError && <p className="mb-3 text-sm text-rx-danger">{targetsError}</p>}
        {!targets.length && !targetsError && <EmptyState>Loading sample applications…</EmptyState>}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {[...targets]
            .sort((a, b) => Number(b.id === 'taskboard') - Number(a.id === 'taskboard'))
            .map((target) => {
              const meta = SAMPLE_COPY[target.id] ?? {
                title: target.label,
                blurb: target.description,
                icon: Zap,
              }
              const Icon = meta.icon
              const active = entryMode === 'sample' && target.id === targetId
              return (
                <button
                  key={target.id}
                  type="button"
                  onClick={() => {
                    setEntryMode('sample')
                    setTargetId(target.id)
                    setApplicationUrl(target.origin.endsWith('/') ? target.origin : `${target.origin}/`)
                    setFeature(target.description)
                    setResolveInfo(null)
                    setResolveError(null)
                  }}
                  className={cx(
                    'rounded-[12px] border p-4 text-left transition',
                    active
                      ? 'border-rx-blue/40 bg-rx-blue-soft'
                      : 'border-rx-line bg-white hover:border-rx-blue/25',
                  )}
                >
                  <div className="mb-3 flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-[12px] border border-rx-line bg-rx-beige text-rx-blue">
                      <Icon size={18} />
                    </span>
                    <div>
                      <p className="font-semibold">{meta.title}</p>
                      <p className="text-xs text-rx-muted">Controlled test application</p>
                    </div>
                  </div>
                  <p className="text-sm leading-relaxed text-rx-muted">{meta.blurb}</p>
                  <p className="mt-2 text-xs text-rx-muted">
                    <Mono>{target.origin}</Mono>
                    {target.independent_validation_available === false
                      ? ' · Understand works; original-vs-recreation scoring is not available for this sample yet'
                      : ''}
                  </p>
                </button>
              )
            })}
        </div>
      </Panel>

      <Panel title="Investigation mode">
        <div className="grid gap-3 md:grid-cols-2">
          <ModeCard
            active={uiMode === 'demo'}
            title="Guided Demo"
            icon={Zap}
            body="Follow a predefined investigation path for the selected application. Preferred for local walkthroughs without Muse investigation calls."
            badge="Recommended for walkthroughs"
            onClick={() => {
              setUiMode('demo')
              if (selected?.reuse_reconstruction_allowed) setReuseReconstruction(true)
            }}
          />
          <ModeCard
            active={uiMode === 'live'}
            title="Fresh AI Investigation"
            icon={Sparkles}
            body="Let Meta Muse Spark choose browser actions focused on the selected feature. Uses Meta model API credits."
            badge="Uses Meta Muse Spark credits"
            onClick={() => {
              setUiMode('live')
              setReuseReconstruction(false)
            }}
          />
        </div>
      </Panel>

      <Panel
        title="Advanced settings"
        action={
          <Button variant="ghost" onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? 'Hide' : 'Show'}
          </Button>
        }
      >
        {!showAdvanced && (
          <EmptyState>Optional technical controls: action budget, pipeline, and reconstruction reuse.</EmptyState>
        )}
        {showAdvanced && (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm">
              <span className="text-rx-muted">Action budget</span>
              <input
                type="number"
                min={1}
                max={20}
                value={maxActions}
                onChange={(e) => setMaxActions(Number(e.target.value))}
                className="mt-1 w-full rounded-[12px] border border-rx-line bg-white px-3 py-2 text-rx-text"
              />
            </label>
            <label className="block text-sm">
              <span className="text-rx-muted">Pipeline (when reconstructing)</span>
              <select
                value={pipeline}
                onChange={(e) => setPipeline(e.target.value as Pipeline)}
                disabled={goal === 'understand'}
                className="mt-1 w-full rounded-[12px] border border-rx-line bg-white px-3 py-2 text-rx-text"
              >
                <option value="full">Full (investigate → reconstruct → validate when available)</option>
                <option value="investigate_only">Investigate only</option>
              </select>
            </label>
            <label className="flex items-start gap-2 text-sm md:col-span-2">
              <input
                type="checkbox"
                checked={reuseReconstruction}
                disabled={
                  entryMode === 'custom' ||
                  uiMode === 'live' ||
                  !selected?.reuse_reconstruction_allowed ||
                  goal === 'understand'
                }
                onChange={(e) => setReuseReconstruction(e.target.checked)}
                className="mt-1"
              />
              <span>
                Reuse existing reconstruction when available
                <span className="mt-1 block text-xs text-rx-muted">
                  Only for Guided Demo on samples that support it (TaskBoard). Custom URL investigations do not
                  reuse TaskBoard reconstructions.
                </span>
              </span>
            </label>
          </div>
        )}
      </Panel>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          disabled={entryMode === 'custom' ? !canLaunchCustom : !canLaunchSample}
          onClick={submit}
        >
          {busy ? 'Starting…' : 'Launch investigation'}
        </Button>
        <p className="text-xs text-rx-muted">
          Progress and evidence-backed reports appear after the investigation runs.
        </p>
      </div>
    </div>
  )
}

function friendlyError(message: string): string {
  if (/400:/.test(message)) {
    return message.replace(/^\d+:\s*/, '')
  }
  if (/Failed to fetch|NetworkError/i.test(message)) {
    return 'Cannot reach the ReverseX backend. Confirm the local API is running.'
  }
  return message
}

function ModeCard({
  active,
  title,
  icon: Icon,
  body,
  badge,
  onClick,
}: {
  active: boolean
  title: string
  icon: typeof Zap
  body: string
  badge: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        'rounded-[12px] border p-4 text-left transition',
        active ? 'border-rx-sage/40 bg-rx-sage-soft' : 'border-rx-line bg-white hover:border-rx-sage/30',
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <Icon size={16} className="text-rx-sage" />
        <p className="font-semibold">{title}</p>
      </div>
      <p className="text-sm leading-relaxed text-rx-muted">{body}</p>
      <p className="mt-3 text-xs font-medium text-rx-sage">{badge}</p>
    </button>
  )
}
