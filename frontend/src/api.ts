import type {
  AIAnalysis,
  AISettings,
  AIStatus,
  Finding,
  InvestigationExport,
  GlobalPerson,
  UsernameHandle,
  UsernameScan,
  UsernameSite,
  Person,
  ResearchCase,
  ResearchGraph,
  Relationship,
  Source,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = body.detail ?? message
    } catch {
      // Keep the HTTP status if the response isn't JSON.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  cases: () => request<ResearchCase[]>('/api/cases'),
  createCase: (body: { title: string; purpose: string }) => request<ResearchCase>('/api/cases', json(body)),
  deleteCase: (id: string) => request<void>(`/api/cases/${id}`, { method: 'DELETE' }),
  graph: (id: string) => request<ResearchGraph>(`/api/cases/${id}/graph`),
  people: (id: string) => request<Person[]>(`/api/cases/${id}/people`),
  sources: (id: string) => request<Source[]>(`/api/cases/${id}/sources`),
  findings: (id: string) => request<Finding[]>(`/api/cases/${id}/findings`),
  relationships: (id: string) => request<Relationship[]>(`/api/cases/${id}/relationships`),
  globalPeople: (q = '') => request<GlobalPerson[]>(`/api/people${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  usernameSites: () => request<UsernameSite[]>('/api/username/sites'),
  usernameHandles: (caseId: string, personId: string) => request<UsernameHandle[]>(`/api/cases/${caseId}/people/${personId}/usernames`),
  addUsernames: (caseId: string, personId: string, usernames: string[]) =>
    request<UsernameHandle[]>(`/api/cases/${caseId}/people/${personId}/usernames`, json({ usernames })),
  usernameSearches: (caseId: string, personId: string, handleId: string) =>
    request<UsernameScan[]>(`/api/cases/${caseId}/people/${personId}/usernames/${handleId}/searches`),
  deleteUsername: (caseId: string, personId: string, handleId: string) =>
    request<void>(`/api/cases/${caseId}/people/${personId}/usernames/${handleId}`, { method: 'DELETE' }),
  searchUsername: (caseId: string, personId: string, handleId: string, site_names: string[]) =>
    request<UsernameScan>(`/api/cases/${caseId}/people/${personId}/usernames/${handleId}/search`, json({ site_names, confirm_authorized: true })),
  createPerson: (
    caseId: string,
    body: {
      name: string
      identity_id?: string
      aliases: string[]
      notes: string
      initial_relationship?: {
        other_person_id: string
        source_id: string
        label: string
        details: string
        confidence: number
        status: string
      }
    },
  ) => request<Person>(`/api/cases/${caseId}/people`, json(body)),
  createSource: (caseId: string, body: { url: string; title: string; publisher: string; notes: string }) =>
    request<Source>(`/api/cases/${caseId}/sources`, json(body)),
  createFinding: (
    caseId: string,
    body: { person_id: string; source_id: string; claim: string; excerpt: string; confidence: number; status: string },
  ) => request<Finding>(`/api/cases/${caseId}/findings`, json(body)),
  createRelationship: (
    caseId: string,
    body: {
      source_person_id: string
      target_person_id: string
      source_id: string
      label: string
      details: string
      confidence: number
      status: string
    },
  ) => request<Relationship>(`/api/cases/${caseId}/relationships`, json(body)),
  aiSettings: () => request<AISettings>('/api/ai/settings'),
  saveAISettings: (body: { provider_name: string; base_url: string; model: string; api_key: string; enabled: boolean }) =>
    request<AISettings>('/api/ai/settings', { method: 'PUT', body: JSON.stringify(body) }),
  clearAISettings: () => request<AISettings>('/api/ai/settings', { method: 'DELETE' }),
  aiStatus: () => request<AIStatus>('/api/ai/status'),
  analyze: (caseId: string, body: { question: string; source_ids: string[]; confirm_provider_share: boolean }) =>
    request<AIAnalysis>(`/api/cases/${caseId}/ai/analyze`, json(body)),
  exportCase: (caseId: string) => request<InvestigationExport>(`/api/cases/${caseId}/export`),
}
