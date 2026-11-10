// Paginated audit history for one integration. Consecutive entries sharing a
// change_group_id render as one group; created/deleted entries carry a full
// JSON snapshot rendered as a compact key/value grid.
import { Fragment, useEffect, useState } from 'react'
import { getIntegrationAudit } from '../../api/integrations'
import type { AuditEntry, AuditPage } from '../../api/types'
import EmptyState from '../../components/EmptyState'
import Pagination from '../../components/Pagination'
import Spinner from '../../components/Spinner'
import { formatDateTime } from '../../utils/format'
import { auditFieldLabel } from './fields'

const EM_DASH = '—'
const PAGE_SIZE = 25

interface AuditHistoryPanelProps {
  integrationId: string
  /** Bump to reload (e.g. after a successful save). */
  refreshKey?: number
}

interface Group {
  groupId: string
  entries: AuditEntry[]
}

function groupEntries(items: AuditEntry[]): Group[] {
  const groups: Group[] = []
  for (const entry of items) {
    const last = groups[groups.length - 1]
    if (last && last.groupId === entry.change_group_id) last.entries.push(entry)
    else groups.push({ groupId: entry.change_group_id, entries: [entry] })
  }
  return groups
}

function readableSnapshot(raw: string | null): string {
  if (raw === null || raw === 'null') return 'No value recorded.'
  try { return JSON.stringify(JSON.parse(raw), null, 2) }
  catch { return raw }
}

function AuditChange({ entry }: { entry: AuditEntry }) {
  const large = entry.field?.startsWith('framework.') ||
    (entry.old_value?.length ?? 0) > 300 || (entry.new_value?.length ?? 0) > 300
  if (!large) return <span>{entry.old_value ?? EM_DASH} → {entry.new_value ?? EM_DASH}</span>
  return <details className="audit-change">
    <summary>View before and after snapshots</summary>
    <div className="audit-snapshots">
      <section aria-label="Before change"><h3>Before change</h3><pre>{readableSnapshot(entry.old_value)}</pre></section>
      <section aria-label="After change"><h3>After change</h3><pre>{readableSnapshot(entry.new_value)}</pre></section>
    </div>
  </details>
}

function SnapshotGrid({ raw }: { raw: string | null }) {
  let snap: Record<string, unknown> | null = null
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      snap = parsed as Record<string, unknown>
    }
  } catch {
    snap = null
  }
  if (!snap) return <span className="muted">{raw ?? EM_DASH}</span>
  const pairs = Object.entries(snap).filter(([, v]) => v !== null && v !== undefined && v !== '')
  if (pairs.length === 0) return <span className="muted">{EM_DASH}</span>
  return (
    <div className="audit-grid">
      {pairs.map(([key, value]) => (
        <Fragment key={key}>
          <span className="muted">{auditFieldLabel(key)}</span>
          <span>{typeof value === 'object' ? <pre className="audit-value">{JSON.stringify(value, null, 2)}</pre> : String(value)}</span>
        </Fragment>
      ))}
    </div>
  )
}

function GroupBlock({ group }: { group: Group }) {
  const first = group.entries[0]
  const isSnapshot = first.action === 'created' || first.action === 'deleted'
  const isComment = first.action === 'commented'
  return (
    <div style={{ padding: '10px 0', borderTop: '1px solid var(--color-border)' }}>
      <p style={{ margin: 0 }}>
        <strong>{first.changed_by_name || first.changed_by_email}</strong>{' '}
        <span className="muted">
          {formatDateTime(first.changed_at)} · {first.action}
        </span>
      </p>
      {isComment ? (
        <blockquote
          style={{
            margin: '6px 0 0',
            padding: '4px 0 4px 10px',
            borderLeft: '3px solid var(--color-border-strong)',
            whiteSpace: 'pre-wrap',
            fontSize: '13px',
          }}
        >
          {first.new_value ?? EM_DASH}
        </blockquote>
      ) : isSnapshot ? (
        <SnapshotGrid raw={first.action === 'created' ? first.new_value : first.old_value} />
      ) : (
        <div className="audit-grid">
          {group.entries
            .filter((e) => e.field !== null)
            .map((e) => (
              <Fragment key={e.id}>
                <span className="muted">{auditFieldLabel(e.field ?? '')}</span>
                <AuditChange entry={e} />
              </Fragment>
            ))}
        </div>
      )}
    </div>
  )
}

export default function AuditHistoryPanel({ integrationId, refreshKey = 0 }: AuditHistoryPanelProps) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AuditPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Jump back to the first page when the record changes or is saved.
  useEffect(() => {
    setPage(1)
  }, [integrationId, refreshKey])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getIntegrationAudit(integrationId, page, PAGE_SIZE)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [integrationId, page, refreshKey])

  const groups = data ? groupEntries(data.items) : []

  return (
    <section className="card audit-panel" style={{ marginTop: 16 }}>
      <h2>Audit history</h2>
      {error ? (
        <div className="error-note" role="alert">
          Could not load audit history: {error}
        </div>
      ) : loading && !data ? (
        <p className="muted">
          <Spinner label="Loading audit history" /> Loading…
        </p>
      ) : data && data.total === 0 ? (
        <EmptyState title="No audit history yet" />
      ) : (
        <>
          {groups.map((group, idx) => (
            <GroupBlock key={`${group.groupId}-${idx}`} group={group} />
          ))}
          {data && (
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </section>
  )
}
