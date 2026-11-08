import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { AlertTriangle, ExternalLink, LoaderCircle, Plus, Search, ShieldAlert, Trash2 } from 'lucide-react'
import { api } from './api'
import type { UsernameHandle, UsernameScan, UsernameSite } from './types'

export default function UsernameManager({ caseId, personId }: { caseId: string; personId: string }) {
  const [handles, setHandles] = useState<UsernameHandle[]>([])
  const [sites, setSites] = useState<UsernameSite[]>([])
  const [input, setInput] = useState('')
  const [activeHandle, setActiveHandle] = useState<UsernameHandle | null>(null)
  const [searches, setSearches] = useState<UsernameScan[]>([])
  const [selectedSites, setSelectedSites] = useState<string[]>([])
  const [siteFilter, setSiteFilter] = useState('')
  const [authorization, setAuthorization] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')

  const filteredSites = useMemo(() => {
    const normalized = siteFilter.trim().toLocaleLowerCase()
    return normalized ? sites.filter((site) => site.name.toLocaleLowerCase().includes(normalized) || site.home_url.toLocaleLowerCase().includes(normalized)) : sites
  }, [sites, siteFilter])

  const reloadHandles = async () => {
    const list = await api.usernameHandles(caseId, personId)
    setHandles(list)
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.usernameHandles(caseId, personId), api.usernameSites()]).then(([nextHandles, nextSites]) => {
      if (!active) return
      setHandles(nextHandles)
      setSites(nextSites)
    }).catch((problem) => {
      if (active) setError(problem instanceof Error ? problem.message : 'Could not load username records.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [caseId, personId])

  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const usernames = [...new Set(input.split(/[\s,;]+/).map((value) => value.trim()).filter(Boolean))]
    if (!usernames.length) return
    if (usernames.length > 10) {
      setError('Add no more than 10 usernames in one submission.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.addUsernames(caseId, personId, usernames)
      setInput('')
      await reloadHandles()
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not save usernames.')
    } finally {
      setSaving(false)
    }
  }

  const openSearch = async (handle: UsernameHandle) => {
    setActiveHandle(handle)
    setSelectedSites([])
    setSiteFilter('')
    setAuthorization(false)
    setError('')
    setSearching(false)
    try {
      const history = await api.usernameSearches(caseId, personId, handle.id)
      setSearches(history)
    } catch (problem) {
      setSearches([])
      setError(problem instanceof Error ? problem.message : 'Could not load saved checks.')
    }
  }

  const runSearch = async () => {
    if (!activeHandle || !authorization || !selectedSites.length) return
    setSearching(true)
    setError('')
    try {
      const result = await api.searchUsername(caseId, personId, activeHandle.id, selectedSites)
      setSearches((current) => [result, ...current])
      setAuthorization(false)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Username check failed.')
    } finally {
      setSearching(false)
    }
  }

  const remove = async (handle: UsernameHandle) => {
    if (!window.confirm(`Remove username ${handle.username} and its saved checks from this investigation?`)) return
    setError('')
    try {
      await api.deleteUsername(caseId, personId, handle.id)
      setHandles((current) => current.filter((item) => item.id !== handle.id))
      if (activeHandle?.id === handle.id) {
        setActiveHandle(null)
        setSearches([])
      }
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not remove the username.')
    }
  }

  const toggleSite = (name: string) => {
    setSelectedSites((current) => current.includes(name)
      ? current.filter((item) => item !== name)
      : current.length >= 25 ? current : [...current, name])
  }

  return (
    <section className="username-manager">
      <div className="detail-section-head"><span>Public usernames</span><span className="count-pill">{handles.length}</span></div>
      <p className="username-help">Save up to 10 usernames per submission for this investigation. They are not automatically shared with other workspaces.</p>
      <form className="username-add-form" onSubmit={add}>
        <textarea aria-label="Usernames" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Add one or more usernames, separated by commas or new lines" maxLength={700} rows={2} />
        <button className="quiet-button" type="submit" disabled={saving || !input.trim()}>{saving ? <LoaderCircle size={13} className="spin" /> : <Plus size={13} />} Save handles</button>
      </form>
      {loading && <div className="username-loading"><LoaderCircle size={13} className="spin" /> Loading usernames…</div>}
      {!loading && !handles.length && <p className="detail-muted">No usernames saved for this person in this workspace.</p>}
      {handles.map((handle) => (
        <div className={`username-row ${activeHandle?.id === handle.id ? 'active' : ''}`} key={handle.id}>
          <code>@{handle.username}</code>
          <div>
            <button className="username-action" type="button" onClick={() => void openSearch(handle)} title="Check this username on selected public sites"><Search size={13} /> Check</button>
            <button className="username-delete" type="button" onClick={() => void remove(handle)} title="Remove username"><Trash2 size={13} /></button>
          </div>
        </div>
      ))}
      {activeHandle && (
        <div className="username-search-panel">
          <div className="username-search-head"><strong>Check @{activeHandle.username}</strong><button type="button" onClick={() => setActiveHandle(null)}>Close</button></div>
          <div className="username-safety"><ShieldAlert size={14} /><span>One handle per check, up to 25 selected sites. The app sends HTTPS HEAD requests only, does not fetch profile content or use proxies, and saves only candidate URLs/status codes. A candidate is not proof the account belongs to this person. Respect each site's rules.</span></div>
          <label className="site-filter"><Search size={13} /><input value={siteFilter} onChange={(event) => setSiteFilter(event.target.value)} placeholder={`Filter ${sites.length} supported sites…`} /><span>{selectedSites.length}/25</span></label>
          <div className="username-site-list">
            {filteredSites.map((site) => <label key={site.name}><input type="checkbox" checked={selectedSites.includes(site.name)} disabled={!selectedSites.includes(site.name) && selectedSites.length >= 25} onChange={() => toggleSite(site.name)} /><span>{site.name}</span><small>{new URL(site.home_url).hostname}</small></label>)}
          </div>
          <label className="username-authorization"><input type="checkbox" checked={authorization} onChange={(event) => setAuthorization(event.target.checked)} /><span>I have consent/authorization or a documented public-interest basis for this search. I will treat results as unverified leads.</span></label>
          <button className="primary-button username-run" type="button" disabled={searching || !authorization || !selectedSites.length} onClick={() => void runSearch()}>{searching ? <LoaderCircle size={14} className="spin" /> : <Search size={14} />}{searching ? 'Checking selected sites…' : `Check ${selectedSites.length} selected site${selectedSites.length === 1 ? '' : 's'}`}</button>
          {error && <p className="username-error" role="alert">{error}</p>}
          {!!searches.length && <div className="username-results"><div className="username-results-head"><strong>Saved checks</strong><span>Candidate = URL responded; verify manually</span></div>{searches.slice(0, 3).map((scan) => <section key={scan.id} className="username-scan"><time>{new Date(scan.created_at).toLocaleString()} · {scan.site_names.length} sites</time>{scan.results.map((result) => <div className="username-result" key={result.id}><span className={`username-result-status ${result.status}`}>{result.status.replace('_', ' ')}</span><a href={result.profile_url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">{result.site_name}<ExternalLink size={11} /></a><small>{result.http_status ?? 'no response'}</small></div>)}</section>)}</div>}
          <p className="username-footnote"><AlertTriangle size={12} /> Search results are investigative leads, not evidence of identity. Verify manually against reliable, independent sources before linking accounts or drawing conclusions.</p>
        </div>
      )}
      {error && !activeHandle && <p className="username-error" role="alert">{error}</p>}
    </section>
  )
}
