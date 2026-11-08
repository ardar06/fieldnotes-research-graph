import { execFileSync } from 'node:child_process'

const base = process.env.FIELDNOTES_URL ?? 'http://127.0.0.1:8000'
const created = await fetch(`${base}/api/cases`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'Synthetic persistence smoke test', purpose: 'Automated test only' }),
})
if (created.status !== 201) throw new Error(`Could not seed persistence test: ${created.status}`)
const seededCase = await created.json()
console.log('Seeded one synthetic case; restarting the app and database container against the existing volume.')

try {
  execFileSync('bash', ['scripts/start.sh'], { stdio: 'inherit' })
  const listResponse = await fetch(`${base}/api/cases`)
  if (!listResponse.ok) throw new Error(`Could not read cases after restart: ${listResponse.status}`)
  const cases = await listResponse.json()
  if (!cases.some((item) => item.id === seededCase.id)) {
    throw new Error('Synthetic case did not persist after the database container was recreated.')
  }
  console.log('PostgreSQL volume persistence verified across container restart.')
} finally {
  const deleted = await fetch(`${base}/api/cases/${seededCase.id}`, { method: 'DELETE' })
  if (deleted.status !== 204) throw new Error('Could not remove the synthetic persistence test case.')
  const check = await fetch(`${base}/api/cases/${seededCase.id}`)
  if (check.status !== 404) throw new Error('Synthetic persistence case remains after cleanup.')
  console.log('Synthetic persistence test case removed.')
}
