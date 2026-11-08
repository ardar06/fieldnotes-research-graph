export type ReviewStatus = 'unreviewed' | 'corroborated' | 'disputed'

export interface ResearchCase {
  id: string
  title: string
  purpose: string
  created_at: string
}

export interface Person {
  id: string
  case_id: string
  identity_id: string | null
  name: string
  aliases: string[]
  notes: string
  created_at: string
}

export interface GlobalPerson {
  id: string
  canonical_name: string
  created_at: string
}

export interface UsernameHandle {
  id: string
  username: string
  created_at: string
}

export interface UsernameSite {
  name: string
  home_url: string
}

export interface UsernameScanResult {
  id: string
  site_name: string
  profile_url: string
  status: 'candidate' | 'not_found' | 'inconclusive' | 'unsupported'
  http_status: number | null
  checked_at: string
}

export interface UsernameScan {
  id: string
  handle_id: string
  username: string
  site_names: string[]
  created_at: string
  results: UsernameScanResult[]
}

export interface Source {
  id: string
  case_id: string
  url: string
  title: string
  publisher: string
  published_on: string | null
  retrieved_on: string
  notes: string
}

export interface Evidence {
  id: string
  title: string
  url: string
  retrieved_on: string
}

export interface Finding {
  id: string
  case_id: string
  person_id: string
  person_name: string
  source_id: string
  claim: string
  excerpt: string
  confidence: number
  status: ReviewStatus
  created_at: string
  source: Evidence
}

export interface Relationship {
  id: string
  case_id: string
  source_person_id: string
  target_person_id: string
  source_id: string
  label: string
  details: string
  confidence: number
  status: ReviewStatus
  created_at: string
  source: Evidence
}

export interface GraphNode {
  id: string
  name: string
  aliases: string[]
  notes: string
  findings_count: number
}

export interface GraphEdge {
  id: string
  source: string | GraphNode
  target: string | GraphNode
  label: string
  details: string
  confidence: number
  status: ReviewStatus
  source_title: string
  source_url: string
  retrieved_on: string
}

export interface ResearchGraph {
  case_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  findings_count: number
  sources_count: number
}

export interface AIStatus {
  enabled: boolean
  provider_name: string
  model: string
  reason: string
  uses_live_search: false
  stores_ai_responses: false
}

export interface AISettings {
  provider_name: string
  base_url: string
  model: string
  enabled: boolean
  api_key_configured: boolean
  source: 'local' | 'environment' | 'none'
}

export interface AIClaim {
  text: string
  source_ids: string[]
  evidence_quote: string
  confidence: 'low' | 'medium' | 'high'
  quote_verified: boolean
}

export interface AIAnalysis {
  provider_name: string
  model: string
  summary: string
  claims: AIClaim[]
  open_questions: string[]
  sources: Evidence[]
  saved: false
  disclaimer: string
}

export interface InvestigationExport {
  case: ResearchCase
  people: Person[]
  sources: Source[]
  findings: Finding[]
  relationships: Relationship[]
  graph: ResearchGraph
  exported_on: string
}
