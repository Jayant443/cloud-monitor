import { useCallback, useEffect, useState } from 'react'
import { apiKeysApi, type ApiKeyCreated, type ApiKeyItem } from '../lib/api'
import { formatRelative } from '../lib/format'

export function SettingsPanel() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setError('')
    try {
      setKeys(await apiKeysApi.list(signal))
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause.message : 'Could not load API keys')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  const create = async () => {
    setFormError('')
    setBusy(true)
    try {
      const created = await apiKeysApi.create(name.trim() ? { name: name.trim() } : {})
      setNewKey(created)
      setCopied(false)
      setName('')
      void refresh()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Could not create API key')
    } finally {
      setBusy(false)
    }
  }

  const revoke = async (id: number) => {
    setFormError('')
    try {
      await apiKeysApi.revoke(id)
      if (newKey?.id === id) setNewKey(null)
      void refresh()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Could not revoke API key')
    }
  }

  const copy = async () => {
    if (!newKey) return
    try {
      await navigator.clipboard.writeText(newKey.key)
      setCopied(true)
    } catch {
      setFormError('Copy failed — select the key text manually')
    }
  }

  return <>
    {error && <div className="notice error-notice"><strong>Couldn’t load API keys.</strong><span>{error}</span></div>}
    {formError && <div className="inline-error">{formError}</div>}
    {loading && keys.length === 0 && !error && <div className="detail-loading"><span className="spinner" />Loading API keys…</div>}

    {newKey && <section className="panel detail-panel container-panel">
      <div className="panel-title-row"><div><div className="section-kicker">NEW KEY — COPY IT NOW</div><h2>{newKey.name || 'Unnamed key'}</h2></div><span className="count-badge">{newKey.key_prefix}…</span></div>
      <div className="notice warning-notice"><strong>Save this key somewhere safe.</strong><span>It will never be shown again. Agents use it as the X-API-Key header value.</span></div>
      <div className="apikey-reveal"><code>{newKey.key}</code><button className="primary-button" onClick={() => void copy()}>{copied ? 'Copied ✓' : 'Copy'}</button></div>
      <div className="rule-form-actions"><span className="rule-form-hint">Dismiss after copying — the full key cannot be retrieved later.</span><button className="text-button" onClick={() => setNewKey(null)}>Dismiss</button></div>
    </section>}

    <section className="panel detail-panel container-panel">
      <div className="panel-title-row"><div><div className="section-kicker">AUTOMATION</div><h2>API keys</h2></div><span className="count-badge">{keys.length}</span></div>
      {keys.length ? <div className="table-scroll"><table><thead><tr><th>NAME</th><th>PREFIX</th><th>STATUS</th><th>CREATED</th><th>LAST USED</th><th /></tr></thead><tbody>
        {keys.map((key) => <tr key={key.id}>
          <td><strong>{key.name || '—'}</strong></td>
          <td><small><code>{key.key_prefix}…</code></small></td>
          <td>{key.is_active ? <span className="health-text good-text">Active</span> : <span className="health-text">Revoked</span>}</td>
          <td className="muted-cell">{formatRelative(key.created_at)}</td>
          <td className="muted-cell">{key.last_used_at ? formatRelative(key.last_used_at) : 'Never'}</td>
          <td><button className="text-button" onClick={() => { if (window.confirm(`Revoke key "${key.name || key.key_prefix}…"? Agents using it will be rejected.`)) void revoke(key.id) }}>Revoke</button></td>
        </tr>)}
      </tbody></table></div> : <div className="empty-inline">No API keys yet. Agents fall back to the server API_KEY env var until you create one.</div>}
      <div className="rule-form">
        <div className="rule-form-title"><span className="section-kicker">NEW KEY</span><p>Create a key for an agent. Only the hash is stored — the full key is shown once. Keys are personal: hosts reported with your keys are visible only to you.</p></div>
        <div className="rule-form-grid apikey-form-grid">
          <label className="rule-field rule-field-wide"><span>Name (optional)</span><input value={name} onChange={(e) => setName(e.target.value)} placeholder="ec2-web-1" /></label>
        </div>
        <div className="rule-form-actions"><span className="rule-form-hint">Example: one key per monitored host.</span><button className="primary-button" disabled={busy} onClick={() => void create()}>{busy ? 'Creating…' : 'Create key'}</button></div>
      </div>
    </section>
  </>
}
