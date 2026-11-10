import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { emptyEnvironment, getFramework, planRelease, saveFramework, STAGES, transitionFramework } from '../../api/framework'
import type { EnvironmentName, FrameworkProfile, FrameworkSpec, Stage } from '../../api/framework'
import ConfirmDialog from '../../components/ConfirmDialog'
import Spinner from '../../components/Spinner'
import { useToast } from '../../context/ToastContext'
import { useUser } from '../../context/UserContext'
import { formatDateTime } from '../../utils/format'
import { contractFields, environmentFields, operationsFields, orchestrationFields, ownershipFields } from './fields'
import type { Field } from './fields'
import './framework.css'

const ENVIRONMENTS: EnvironmentName[] = ['dev', 'test', 'qa', 'prod']
const OPTIONAL_NUMBERS = new Set(['data_retention_days', 'heartbeat_timeout_seconds', 'rate_limit_per_second', 'slo_availability', 'latency_target_ms', 'rto_minutes', 'rpo_minutes'])
function cleanSpec(spec: FrameworkSpec): FrameworkSpec {
  // Preserve text as typed while editing; normalize list entries only at the save boundary.
  return JSON.parse(JSON.stringify(spec, (_key, value) => Array.isArray(value) && value.every(v => typeof v === 'string')
    ? value.map(v => v.trim()).filter(Boolean) : value)) as FrameworkSpec
}
function Fields<T extends object>({ prefix, fields, value, editable, onChange }: {
  prefix: string; fields: Field<T>[]; value: T; editable: boolean; onChange: (next: T) => void
}) {
  return <div className="framework-fields">{fields.map(field => {
    const key = String(field.key)
    const id = `framework-${prefix}-${key}`
    const current = value[field.key]
    const display = Array.isArray(current) ? current.join('\n') : String(current ?? '')
    const change = (raw: string) => onChange({ ...value, [field.key]: field.type === 'number'
      ? (raw === '' ? null : Number(raw)) : field.type === 'list' ? raw.split('\n') : raw })
    return <div className={`framework-field ${field.type === 'textarea' || field.type === 'list' ? 'wide' : ''}`} key={key}>
      <label htmlFor={editable ? id : undefined}>{field.label}</label>
      {editable ? <>
        {field.options ? <select id={id} value={display} onChange={e => change(e.target.value)}>{field.options.map(option => <option key={option} value={option}>{option.replace(/_/g, ' ')}</option>)}</select>
          : field.type === 'textarea' || field.type === 'list' ? <textarea id={id} value={display} rows={3} maxLength={field.type === 'list' ? 20000 : 2000} onChange={e => change(e.target.value)} aria-describedby={`${id}-hint`} />
          : <input id={id} type={field.type === 'number' ? 'number' : field.type === 'url' ? 'url' : 'text'} value={display}
            min={field.min} max={field.max} step={field.step ?? 1} maxLength={field.type === 'url' ? 2000 : 200}
            required={field.type === 'number' && !OPTIONAL_NUMBERS.has(key)} onChange={e => change(e.target.value)} aria-describedby={`${id}-hint`} />}
        <small id={`${id}-hint`} className="muted">{field.hint}{field.type === 'list' ? ' One entry per line.' : ''}{field.type === 'url' ? ' HTTP(S), without credentials, query parameters or fragments.' : ''}</small>
      </> : <div className={`framework-value ${display ? '' : 'muted'}`}>{Array.isArray(current) && current.length ? current.map((item, i) => <span className="chip system" key={i}>{String(item)}</span>) : display || 'Not recorded'}</div>}
    </div>
  })}</div>
}

export default function FrameworkPanel({ integrationId, onDirtyChange, onEditingChange, onUpdated, writesLocked, refreshKey }: {
  integrationId: string; onDirtyChange: (dirty: boolean) => void; onEditingChange: (editing: boolean) => void; onUpdated: () => Promise<void>; writesLocked: boolean; refreshKey: number
}) {
  const { isAdmin } = useUser()
  const { toast } = useToast()
  const [profile, setProfile] = useState<FrameworkProfile | null>(null)
  const [draft, setDraft] = useState<FrameworkSpec | null>(null)
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [confirmReload, setConfirmReload] = useState(false)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [target, setTarget] = useState<Stage>('design')
  const [environment, setEnvironment] = useState<EnvironmentName>('dev')
  const [reason, setReason] = useState('')
  const [pendingAction, setPendingAction] = useState<'transition' | 'plan' | null>(null)
  const dirty = editing && JSON.stringify(draft) !== JSON.stringify(profile?.spec)
  useEffect(() => { onEditingChange(editing || busy || loading); return () => onEditingChange(false) }, [editing, busy, loading, onEditingChange])
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false) }, [dirty, onDirtyChange])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    getFramework(integrationId, controller.signal).then(p => { setProfile(p); setDraft(p.spec) })
      .catch(err => { if (err.name !== 'AbortError') setError(err.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [integrationId, refreshKey])
  useEffect(() => {
    if (profile) setTarget(STAGES[Math.min(STAGES.indexOf(profile.stage) + 1, STAGES.length - 1)])
  }, [profile?.stage])

  async function reload() {
    setBusy(true)
    try {
      const p = await getFramework(integrationId)
      setProfile(p); setDraft(p.spec); setEditing(false); setConflict(false); setError(null); setConfirmReload(false)
      await onUpdated()
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not reload framework.') }
    finally { setBusy(false) }
  }
  async function mutate(operation: () => Promise<FrameworkProfile>, success: string) {
    if (busy || conflict) return
    setBusy(true); setError(null)
    try {
      const p = await operation()
      setProfile(p); setDraft(p.spec); setEditing(false); setReason(''); setPendingAction(null)
      await onUpdated(); toast(success, 'success')
    } catch (err) {
      setPendingAction(null)
      if (err instanceof ApiError && err.status === 409) setConflict(true)
      setError(err instanceof Error ? err.message : 'The request failed. Your edits have been kept.')
    } finally { setBusy(false) }
  }
  if (loading) return <section className="card framework-loading"><Spinner label="Loading framework" /> Loading framework…</section>
  if (!profile || !draft) return <section className="card"><div role="alert" className="error-note">{error || 'Framework is unavailable.'}</div><button className="btn secondary" disabled={busy} onClick={() => void reload()}>Retry</button></section>
  const spec = editing ? draft : profile.spec
  const editable = editing && isAdmin && profile.stage !== 'retired' && !busy && !conflict && !writesLocked
  const passed = profile.readiness.checks.filter(check => check.passed).length
  const transitionTargets = profile.stage === 'retired' ? [] : STAGES.filter((stage, i) => i === STAGES.indexOf(profile.stage) + 1 || (stage === 'development' && ['validation', 'ready', 'live'].includes(profile.stage)))
  const actionsDisabled = busy || conflict || editing || writesLocked || profile.stage === 'retired' || profile.version === 0
  const setGroup = <K extends keyof FrameworkSpec>(key: K, value: FrameworkSpec[K]) => setDraft({ ...draft, [key]: value })
  return <section className="framework" aria-label="Integration framework">
    <div className="framework-hero">
      <div><p className="framework-eyebrow">Enterprise integration framework</p><h2>From contract to operational readiness</h2>
        <p>APIM · OpenAPI · Temporal · Environment governance</p></div>
      <div className="framework-version">Catalog revision <strong>{profile.version}</strong><span>{profile.stage === 'retired' ? 'Retired · read-only' : isAdmin ? 'Integration team access' : 'Read-only access'}</span></div>
    </div>
    <div className="framework-notice">This is a metadata catalog. Lifecycle changes and release plans do not deploy software, publish APIs or run workflows.</div>
    {writesLocked && <p className="framework-notice">Finish editing catalog metadata before changing the framework.</p>}
    {error && <div className="error-note" role="alert">{error}{conflict && <><p>A newer revision or an unmet release prerequisite prevented this action. Your local edits are still here. Review the latest saved profile before trying again.</p><button className="btn secondary" disabled={busy} onClick={() => dirty ? setConfirmReload(true) : void reload()}>Reload saved profile</button></>}</div>}
    {profile.version === 0 && <p className="framework-notice">No framework profile yet. {isAdmin ? 'Edit and save the profile to start the lifecycle.' : 'The integration team can add ownership, contracts and environment metadata.'}</p>}
    <div className="framework-layout">
      <div className="framework-content">
        <section className="card framework-lifecycle">
          <h3>Lifecycle</h3><ol className="stage-track" aria-label="Current lifecycle stage">{STAGES.map(stage => <li key={stage} aria-current={stage === profile.stage ? 'step' : undefined} className={stage === profile.stage ? 'current' : ''}>{stage}</li>)}</ol>
          <p className="muted">Framework lifecycle is separate from the catalog's existing integration status. Lifecycle changes are recorded in audit history.</p>
          {isAdmin && profile.stage !== 'retired' && <><label className="framework-reason">Change rationale<textarea value={reason} maxLength={2000} disabled={busy || editing} onChange={e => setReason(e.target.value)} placeholder="Explain the lifecycle change or rework decision." /></label><div className="framework-action-row">
            <label>Next stage<select value={target} onChange={e => setTarget(e.target.value as Stage)} disabled={actionsDisabled}>{transitionTargets.map(stage => <option key={stage}>{stage}</option>)}</select></label>
            <button className="btn secondary" disabled={actionsDisabled || !reason.trim()} onClick={() => setPendingAction('transition')}>Record stage change</button>
          </div></>}
          {profile.stage === 'retired' && <p className="muted">Retired is a terminal lifecycle stage. This framework profile is read-only; no new release plans can be recorded.</p>}
        </section>
        <form onInvalidCapture={e => { const el = e.target as HTMLElement; let parent = el.parentElement; while (parent) { if (parent instanceof HTMLDetailsElement) parent.open = true; parent = parent.parentElement } }} onSubmit={e => { e.preventDefault(); if (editable) void mutate(() => saveFramework(integrationId, profile.version, cleanSpec(draft)), 'Framework profile saved.') }}>
          <div className="framework-section-head"><div><h3>Framework specification</h3><p className="muted">Capture the decisions your delivery and support teams need.</p></div>
            {isAdmin && !editing && profile.stage !== 'retired' && <button type="button" className="btn" disabled={busy || conflict || writesLocked} onClick={() => setEditing(true)}>Edit framework</button>}</div>
          {editing && <p className="framework-notice">Material specification changes clear design and code approvals and require reapproval. Ready or live profiles return to development. Previous release plans remain in history.</p>}
          <details className="card framework-section" open><summary>01 <span>Ownership & classification</span></summary><Fields prefix="ownership" fields={ownershipFields} value={spec.ownership} editable={editable} onChange={value => setGroup('ownership', value)} /></details>
          <details className="card framework-section"><summary>02 <span>API contract & data</span></summary><Fields prefix="contract" fields={contractFields} value={spec.contract} editable={editable} onChange={value => setGroup('contract', value)} /></details>
          <details className="card framework-section"><summary>03 <span>Temporal orchestration & resilience</span></summary><Fields prefix="orchestration" fields={orchestrationFields} value={spec.orchestration} editable={editable} onChange={value => setGroup('orchestration', value)} /></details>
          <details className="card framework-section"><summary>04 <span>Operations & recovery</span></summary><Fields prefix="operations" fields={operationsFields} value={spec.operations} editable={editable} onChange={value => setGroup('operations', value)} /></details>
          <section className="card framework-environments"><h3>05 · Environment inventory</h3><p className="muted">Record desired configuration and artifact references, not runtime deployment state. Secret references only.</p>
            <div className="environment-grid">{ENVIRONMENTS.map(name => {
              const env = spec.environments.find(item => item.name === name)
              return <details key={name} className={`environment-card ${name === 'prod' ? 'production' : ''}`}><summary><span className="env-name">{name}</span><span>{env?.release_version || (env ? 'Configuration recorded' : 'Not configured')}</span></summary>
                {env ? <><Fields prefix={name} fields={environmentFields} value={env} editable={editable} onChange={value => setGroup('environments', spec.environments.map(item => item.name === name ? value : item))} />{editable && <button type="button" className="btn secondary small" onClick={() => setGroup('environments', spec.environments.filter(item => item.name !== name))}>Remove {name.toUpperCase()} from draft</button>}</>
                  : <div className="environment-empty"><p>No {name.toUpperCase()} configuration recorded.</p>{editable && <button className="btn secondary" type="button" onClick={() => setGroup('environments', [...spec.environments, emptyEnvironment(name)])}>Add {name.toUpperCase()}</button>}</div>}
              </details>
            })}</div>
          </section>
          {editing && <div className="framework-savebar"><span aria-live="polite">{dirty ? 'Unsaved framework changes' : 'No changes yet'}</span><button type="button" className="btn secondary" disabled={busy} onClick={() => dirty ? setConfirmDiscard(true) : setEditing(false)}>Cancel</button><button type="submit" className="btn green" disabled={busy || conflict || writesLocked || (!dirty && profile.version !== 0)}>{busy ? 'Saving…' : 'Save framework'}</button></div>}
        </form>
        <section className="card framework-releases"><h3>Release plans</h3><p className="muted">Plan progression: DEV → TEST → QA → PROD. Production requires readiness, recorded approvals and a matching QA artifact. Plans are not evidence of deployment.</p>
          {isAdmin && profile.stage !== 'retired' && <><label className="framework-reason">Change / release rationale<textarea maxLength={2000} value={reason} disabled={busy || editing} onChange={e => setReason(e.target.value)} placeholder="Why is this stage change or release plan needed?" /></label><div className="framework-action-row"><label>Target environment<select value={environment} onChange={e => setEnvironment(e.target.value as EnvironmentName)} disabled={actionsDisabled}>{ENVIRONMENTS.map(name => <option key={name} value={name}>{name.toUpperCase()}</option>)}</select></label><button className="btn" disabled={actionsDisabled || !reason.trim() || !spec.environments.some(env => env.name === environment)} onClick={() => setPendingAction('plan')}>Record release plan</button></div>{editing && <p className="muted">Save or cancel editing before changing the lifecycle or recording a release plan.</p>}</>}
          {profile.release_plans.length === 0 ? <div className="framework-empty">No release plans recorded. Add environment configuration and save the profile to begin.</div> : <ol className="release-history">{profile.release_plans.map(plan => <li key={plan.id}><div className="release-title"><strong>{plan.environment.toUpperCase()} · {plan.release_version}</strong><span className="chip system">Planned only</span></div><p>{plan.reason}</p><code>{plan.git_sha}</code><p className="muted">{formatDateTime(plan.created_at)} · {plan.created_by}</p></li>)}</ol>}
        </section>
      </div>
      <aside className="framework-readiness card"><p className="framework-eyebrow">Production readiness</p><h3>{profile.readiness.ready ? 'Ready for review' : 'Build a complete picture'}</h3><div className="readiness-score"><strong>{passed}</strong><span>/ {profile.readiness.checks.length} checks</span></div><progress value={passed} max={profile.readiness.checks.length || 1} aria-label="Saved profile readiness" /><p className="muted">Based on saved metadata, not live infrastructure checks.{editing ? ' Save to refresh these checks.' : ''}</p><ul>{profile.readiness.checks.map(check => <li key={check.key} className={check.passed ? 'passed' : ''}><span aria-hidden="true">{check.passed ? '✓' : '○'}</span><div><strong>{check.label}</strong><p>{check.detail}</p></div></li>)}</ul><p className="muted">Design and code approvals are maintained in the existing catalog metadata below.</p></aside>
    </div>
    {confirmDiscard && <ConfirmDialog title="Discard framework changes?" message="Your unsaved framework changes will be discarded." confirmLabel="Discard" onCancel={() => setConfirmDiscard(false)} onConfirm={() => { setDraft(profile.spec); setEditing(false); setConfirmDiscard(false) }} danger />}
    {confirmReload && <ConfirmDialog title="Load the latest saved profile?" message="This will discard your local framework edits and load the current saved revision. Copy any changes you need to retain before continuing." confirmLabel="Discard and reload" busy={busy} onCancel={() => setConfirmReload(false)} onConfirm={() => void reload()} danger />}
    {pendingAction && <ConfirmDialog title={pendingAction === 'plan' ? 'Record a release plan?' : 'Record lifecycle change?'} message={<>{pendingAction === 'plan' ? `Record a planned release to ${environment.toUpperCase()} using the saved artifact references?` : `Move the framework lifecycle from ${profile.stage} to ${target}?`}<p>{reason}</p><p>This updates the catalog only. Nothing will be deployed.</p></>} confirmLabel="Record change" busy={busy} onCancel={() => setPendingAction(null)} onConfirm={() => void mutate(() => pendingAction === 'plan' ? planRelease(integrationId, profile.version, environment, reason.trim()) : transitionFramework(integrationId, profile.version, target, reason.trim()), pendingAction === 'plan' ? 'Release plan recorded. No deployment was performed.' : 'Lifecycle stage recorded.')} />}
  </section>
}
