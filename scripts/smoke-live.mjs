const base = process.env.FIELDNOTES_URL ?? 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  const payload = response.status === 204 ? null : await response.json().catch(() => null)
  return { response, payload }
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

let caseId
try {
  const { response: healthResponse, payload: health } = await request('/api/health')
  assert(healthResponse.ok && health.automated_collection === false, 'local-only health endpoint failed')
  const aiStatus = await request('/api/ai/status')
  assert(aiStatus.response.ok, 'AI configuration status endpoint failed')
  assert(aiStatus.payload.uses_live_search === false && aiStatus.payload.stores_ai_responses === false, 'AI safety defaults changed unexpectedly')
  assert(!JSON.stringify(aiStatus.payload).includes('api_key') && !JSON.stringify(aiStatus.payload).includes('base_url'), 'AI status leaked provider configuration')

  const pageResponse = await fetch(base)
  const page = await pageResponse.text()
  assert(pageResponse.ok && page.includes('<title>Fieldnotes — Research Graph</title>'), 'web UI shell did not load')
  const assetPaths = [...page.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1]).filter((path) => path.endsWith('.js') || path.endsWith('.css'))
  assert(assetPaths.length >= 2, 'compiled frontend assets were not referenced')
  for (const assetPath of assetPaths) {
    const asset = await fetch(new URL(assetPath, base))
    assert(asset.ok, `frontend asset failed: ${assetPath}`)
    if (assetPath.endsWith('.css')) {
      const css = await asset.text()
      assert(!css.includes('fonts.googleapis.com'), 'frontend unexpectedly calls an external font service')
      assert(css.includes('.ai-review'), 'AI review styles are missing from the production asset')
    } else if (assetPath.endsWith('.js')) {
      const bundle = await asset.text()
      assert(bundle.includes('AI review') && bundle.includes('Analyze selected sources'), 'AI review UI is missing from the production bundle')
    }
  }

  const createdCase = await request('/api/cases', {
    method: 'POST',
    body: JSON.stringify({ title: 'Synthetic live smoke test', purpose: 'Automated test only' }),
  })
  assert(createdCase.response.status === 201, 'case creation failed')
  caseId = createdCase.payload.id

  const addPerson = async (name) => {
    const result = await request(`/api/cases/${caseId}/people`, {
      method: 'POST', body: JSON.stringify({ name }),
    })
    assert(result.response.status === 201, `person creation failed: ${name}`)
    return result.payload
  }
  const personA = await addPerson('Morgan Example')
  const personB = await addPerson('Casey Sample')

  const sourceResult = await request(`/api/cases/${caseId}/sources`, {
    method: 'POST',
    body: JSON.stringify({
      url: 'https://example.org/synthetic-record',
      title: 'Synthetic public record',
      publisher: 'Example Publisher',
    }),
  })
  assert(sourceResult.response.status === 201, 'source creation failed')

  const findingResult = await request(`/api/cases/${caseId}/findings`, {
    method: 'POST',
    body: JSON.stringify({
      person_id: personA.id,
      source_id: sourceResult.payload.id,
      claim: 'Synthetic source-backed note',
      confidence: 0.8,
      status: 'unreviewed',
    }),
  })
  assert(findingResult.response.status === 201, 'finding creation failed')

  const relationResult = await request(`/api/cases/${caseId}/relationships`, {
    method: 'POST',
    body: JSON.stringify({
      source_person_id: personA.id,
      target_person_id: personB.id,
      source_id: sourceResult.payload.id,
      label: 'Listed together in a synthetic public record',
      confidence: 0.6,
      status: 'unreviewed',
    }),
  })
  assert(relationResult.response.status === 201, 'relationship creation failed')

  const graphResult = await request(`/api/cases/${caseId}/graph`)
  assert(graphResult.response.ok, 'graph endpoint failed')
  assert(graphResult.payload.nodes.length === 2, 'graph did not return both people')
  assert(graphResult.payload.edges.length === 1, 'graph did not return its sourced connection')
  assert(graphResult.payload.edges[0].source_url === 'https://example.org/synthetic-record', 'relationship lost its source URL')

  const exportResult = await request(`/api/cases/${caseId}/export`)
  assert(exportResult.response.ok, 'JSON export endpoint failed')
  assert(exportResult.payload.findings[0].source.url === 'https://example.org/synthetic-record', 'export lost finding provenance')
  assert(exportResult.payload.relationships.length === 1, 'export lost relationship record')

  console.log('Live PostgreSQL API smoke passed: health, case, people, source, finding, relationship, graph, and provenance export.')
} finally {
  if (caseId) {
    const deleted = await request(`/api/cases/${caseId}`, { method: 'DELETE' })
    assert(deleted.response.status === 204, 'synthetic smoke case cleanup failed')
    const absent = await request(`/api/cases/${caseId}/export`)
    assert(absent.response.status === 404, 'deleted smoke case still exists')
    console.log('Synthetic smoke records removed; deletion confirmed.')
  }
}
