import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { AlertTriangle, BookOpenText, Check, CircleHelp, KeyRound, LoaderCircle, Save, Send, ShieldAlert, Trash2 } from 'lucide-react'
import { api } from './api'
import type { AIAnalysis, AISettings, AIStatus, Source } from './types'

export default function AIReviewView({ caseId, sources }: { caseId: string; sources: Source[] }) {
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [settings, setSettings] = useState<AISettings | null>(null)
  const [providerName, setProviderName] = useState('OpenCode Console')
  const [baseUrl, setBaseUrl] = useState('https://opencode.ai/inference/openai/v1')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [settingsBusy, setSettingsBusy] = useState(false)
  const [settingsError, setSettingsError] = useState('')
  const [settingsMessage, setSettingsMessage] = useState('')
  const [statusError, setStatusError] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [question, setQuestion] = useState('')
  const [consent, setConsent] = useState(false)
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([api.aiStatus(), api.aiSettings()]).then(([statusValue, settingsValue]) => {
      if (!active) return
      setStatus(statusValue)
      setSettings(settingsValue)
      setProviderName(settingsValue.provider_name || 'OpenCode Console')
      setBaseUrl(settingsValue.base_url || 'https://opencode.ai/inference/openai/v1')
      setModel(settingsValue.model)
      setEnabled(settingsValue.enabled)
    }).catch((problem) => {
      if (active) setStatusError(problem instanceof Error ? problem.message : 'Could not read AI configuration.')
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const valid = new Set(sources.map((source) => source.id))
    setSelectedIds((current) => current.filter((id) => valid.has(id)))
  }, [sources])

  const sourceNames = useMemo(() => new Map((analysis?.sources ?? []).map((source) => [source.id, source])), [analysis])

  const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSettingsBusy(true)
    setSettingsError('')
    setSettingsMessage('')
    try {
      const saved = await api.saveAISettings({ provider_name: providerName, base_url: baseUrl, model, api_key: apiKey, enabled })
      setSettings(saved)
      setApiKey('')
      setStatus(await api.aiStatus())
      setSettingsMessage('Saved locally. The key is never returned to this page.')
    } catch (problem) {
      setSettingsError(problem instanceof Error ? problem.message : 'Could not save provider settings.')
    } finally {
      setSettingsBusy(false)
    }
  }

  const clearSettings = async () => {
    if (!window.confirm('Remove the locally saved provider settings and API key?')) return
    setSettingsBusy(true)
    setSettingsError('')
    setSettingsMessage('')
    try {
      const remaining = await api.clearAISettings()
      setSettings(remaining)
      setProviderName(remaining.provider_name || 'OpenCode Console')
      setBaseUrl(remaining.base_url || 'https://opencode.ai/inference/openai/v1')
      setModel(remaining.model)
      setEnabled(remaining.enabled)
      setApiKey('')
      setStatus(await api.aiStatus())
      setSettingsMessage(remaining.source === 'environment' ? 'Local settings removed. Server environment settings remain active.' : 'Local provider settings removed.')
    } catch (problem) {
      setSettingsError(problem instanceof Error ? problem.message : 'Could not clear provider settings.')
    } finally {
      setSettingsBusy(false)
    }
  }

  const toggleSource = (id: string) => {
    setSelectedIds((current) => current.includes(id)
      ? current.filter((value) => value !== id)
      : current.length >= 5 ? current : [...current, id])
    setAnalysis(null)
    setError('')
    setConsent(false)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setAnalysis(null)
    if (!status?.enabled) {
      setError('AI provider is not configured on the server.')
      return
    }
    if (!selectedIds.length) {
      setError('Select at least one source first.')
      return
    }
    if (!consent) {
      setError('Confirm provider sharing before sending anything.')
      return
    }
    setWorking(true)
    setConsent(false)
    try {
      const result = await api.analyze(caseId, {
        question: question.trim(),
        source_ids: selectedIds,
        confirm_provider_share: true,
      })
      setAnalysis(result)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'The AI request failed.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <section className="records-view ai-review">
      <div className="records-head ai-head">
        <div>
          <div className="eyebrow">SOURCE-GROUNDED ASSISTANT</div>
          <h2>AI review</h2>
          <p>Ask for a summary or analysis of selected saved material.</p>
        </div>
        {status?.enabled && <div className="ai-provider-pill"><span className="ai-provider-dot" />{status.provider_name}<span>·</span>{status.model}</div>}
      </div>

      <div className="ai-safety-card">
        <ShieldAlert size={16} />
        <div>
          <strong>AI does not search the web in this version.</strong>
          <p>Only selected source metadata, linked person names, findings/excerpts, relationship notes, and your question are sent after you confirm. Source URLs and unrelated case records are not sent. Responses are not saved automatically.</p>
        </div>
      </div>

      {statusError && <div className="ai-error" role="alert">{statusError}</div>}
      <form className="ai-settings-card" onSubmit={saveSettings}>
        <div className="ai-settings-heading"><div className="ai-config-icon"><KeyRound size={17} /></div><div><strong>AI provider settings</strong><p>Copy the key from OpenCode Console and paste it here. Fieldnotes cannot read it from another website's browser session.</p></div></div>
        <div className="ai-settings-grid">
          <label><span>Provider name</span><input value={providerName} onChange={(event) => setProviderName(event.target.value)} maxLength={100} required /></label>
          <label><span>OpenAI-compatible base URL</span><input type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} maxLength={500} required /></label>
          <label><span>Model ID</span><input value={model} onChange={(event) => setModel(event.target.value)} maxLength={200} placeholder="Your provider's model ID" required /></label>
          <label><span>API key {settings?.api_key_configured ? '· saved; blank keeps current' : ''}</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={settings?.api_key_configured ? 'Saved locally — leave blank to keep' : 'Paste provider API key'} autoComplete="new-password" maxLength={8192} /></label>
        </div>
        {baseUrl.includes('opencode.ai/inference') && <p className="ai-settings-note">OpenCode Console free-tier chat models (including <code>crouton-alpha-free</code>) are restricted to OpenCode itself. Fieldnotes is a separate client; use a paid Console or Go model. See <a href="https://opencode.ai/v2/docs/console/models/" target="_blank" rel="noreferrer">OpenCode's model list</a>.</p>}
        <label className="ai-settings-enable"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span>Enable AI analysis for source-selected requests</span></label>
        <p className="ai-settings-security">The key is sent only to this local Fieldnotes server, stored in a private Docker settings volume with restrictive file permissions, and never returned to the page or stored in the research database. It is sent to the provider only when you submit an analysis and confirm sharing. The local volume is not encrypted; protect your Windows account and Docker data.</p>
        {settings?.source === 'environment' && <p className="ai-settings-note">A server environment configuration is currently active. Saving here creates local settings that take precedence.</p>}
        {settingsError && <div className="ai-error" role="alert">{settingsError}</div>}
        {settingsMessage && <div className="ai-settings-success" role="status">{settingsMessage}</div>}
        <div className="ai-settings-actions"><button className="primary-button small" type="submit" disabled={settingsBusy}>{settingsBusy ? <LoaderCircle size={14} className="spin" /> : <Save size={14} />}{settingsBusy ? 'Saving settings…' : 'Save provider settings'}</button>{settings?.source === 'local' && <button className="quiet-button" type="button" onClick={() => void clearSettings()} disabled={settingsBusy}><Trash2 size={13} /> Clear local settings</button>}<span>{status?.enabled ? `Active · ${status.provider_name}` : status?.reason || 'AI is disabled until a provider is configured and enabled.'}</span></div>
      </form>

      <div className="ai-workbench">
        <div className="ai-source-column">
          <div className="ai-section-heading"><span>Choose source material</span><span>{selectedIds.length}/5 selected</span></div>
          {!sources.length ? (
            <div className="ai-empty-sources"><BookOpenText size={19} /><span>Add reviewed sources before asking AI to analyze them.</span></div>
          ) : (
            <div className="ai-source-list">
              {sources.map((source) => (
                <label className={`ai-source-option ${selectedIds.includes(source.id) ? 'checked' : ''}`} key={source.id}>
                  <input type="checkbox" checked={selectedIds.includes(source.id)} disabled={!selectedIds.includes(source.id) && selectedIds.length >= 5} onChange={() => toggleSource(source.id)} />
                  <span className="ai-check"><Check size={12} /></span>
                  <span className="ai-source-copy"><strong>{source.title}</strong><small>{source.publisher || 'Public source'} · Retrieved {source.retrieved_on}</small></span>
                </label>
              ))}
            </div>
          )}
          <div className="ai-source-limit"><CircleHelp size={13} /> Up to five sources per request; only excerpts already saved in this investigation are included.</div>
        </div>

        <form className="ai-question-card" onSubmit={submit}>
          <label className="ai-question-label" htmlFor="ai-question">What should the assistant examine?</label>
          <textarea id="ai-question" value={question} onChange={(event) => { setQuestion(event.target.value); setAnalysis(null); setConsent(false) }} maxLength={1500} placeholder="For example: Summarize the source-supported claims and list what remains uncertain." required />
          <div className="ai-question-meta"><span>Keep the question focused on the selected evidence.</span><span>{question.length}/1500</span></div>
          <label className="ai-consent">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} disabled={!status?.enabled || working} />
            <span>I confirm selected source metadata, linked names/claims/excerpts/relationship notes, and my question may be sent to <strong>{status?.provider_name || 'the configured AI provider'}</strong> for this request.</span>
          </label>
          {error && <div className="ai-error" role="alert">{error}</div>}
          <button className="primary-button ai-submit" type="submit" disabled={!status?.enabled || working || !question.trim() || !selectedIds.length || !consent}>
            {working ? <LoaderCircle size={15} className="spin" /> : <Send size={14} />}
            {working ? 'Reviewing selected material…' : 'Analyze selected sources'}
          </button>
          {status?.enabled && <div className="ai-config-foot">No search, browsing, or tools are available to the model in this request.</div>}
        </form>
      </div>

      {analysis && (
        <section className="ai-result" aria-live="polite">
          <div className="ai-result-head"><div><div className="eyebrow">UNSAVED DRAFT</div><h3>Assistant notes</h3></div><span className="ai-result-provider">{analysis.provider_name} · {analysis.model}</span></div>
          {analysis.summary && <p className="ai-summary">{analysis.summary}</p>}
          {analysis.claims.length > 0 ? <div className="ai-claims">{analysis.claims.map((claim, index) => (
            <article className="ai-claim" key={`${index}-${claim.text}`}>
              <div className="ai-claim-top"><span>Candidate claim {index + 1}</span><span className="ai-model-confidence">Model self-rating: {claim.confidence} · not proof</span></div>
              <p>{claim.text}</p>
              {claim.evidence_quote && <blockquote className={claim.quote_verified ? 'quote-verified' : 'quote-unverified'}>“{claim.evidence_quote}”</blockquote>}
              <div className={`quote-check ${claim.quote_verified ? 'valid' : 'invalid'}`}>
                {claim.quote_verified ? <Check size={13} /> : <AlertTriangle size={13} />}
                {claim.quote_verified ? 'Quote matched a selected saved excerpt' : 'Quote not verified against the selected excerpts'}
              </div>
              <div className="ai-citations">{claim.source_ids.length ? claim.source_ids.map((id) => {
                const source = sourceNames.get(id)
                return source ? <a key={id} href={source.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">{source.title}<span>↗</span></a> : <span className="ai-invalid-citation" key={id}>Unrecognized source ID</span>
              }) : <span className="ai-invalid-citation">No valid source citation returned</span>}</div>
            </article>
          ))}</div> : <p className="ai-no-claims">No source-cited candidate claims were returned. Review the answer and provide more excerpt text if needed.</p>}
          {analysis.open_questions.length > 0 && <div className="ai-questions"><strong>Questions to verify</strong><ul>{analysis.open_questions.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div>}
          <div className="ai-result-warning"><AlertTriangle size={14} /> {analysis.disclaimer}</div>
          <div className="ai-used-sources"><strong>Material sent:</strong> {analysis.sources.map((source) => source.title).join(' · ')}</div>
        </section>
      )}
    </section>
  )
}
