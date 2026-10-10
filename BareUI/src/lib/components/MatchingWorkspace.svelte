<script lang="ts">
  import { onMount } from 'svelte'
  import { Play, RotateCcw, Search, Trash2 } from '@lucide/svelte'
  import { request } from '../api'
  import RoleSelect from './RoleSelect.svelte'
  import { displayValue } from '../format'
  import type { ApiRecord } from '../types'

  let { onError, initialTab = 'Match candidate' }: { onError: (error: string) => void; initialTab?: string } = $props()

  type MatchTab = 'Match candidate' | 'Role leaderboard' | 'Resume matches' | 'Jobs'
  type ResultRow = ApiRecord & { result_kind?: 'single' | 'resume'; result_role_id?: string }
  let tab = $state<MatchTab>('Match candidate')
  let resumeId = $state('')
  let roleId = $state('')
  let limit = $state(25)
  let minScore = $state(0)
  let status = $state('')
  let result = $state<unknown>(null)
  let jobs = $state<ApiRecord[]>([])
  let busy = $state(false)
  const resultRows = $derived(normalizeMatchRows(result))

  function record(value: unknown): ApiRecord {
    return value && typeof value === 'object' && !Array.isArray(value) ? value as ApiRecord : {}
  }

  function normalizeMatchRows(value: unknown): ResultRow[] {
    if (Array.isArray(value)) return value.map(record)
    const root = record(value)
    if (root.resume_id && root.role_id && root.result !== undefined) {
      return [{ ...record(root.result), resume_id: root.resume_id, role_id: root.role_id, result_kind: 'single' }]
    }
    if (root.resume_id && root.match && typeof root.match === 'object') {
      return Object.entries(record(root.match)).map(([roleId, match]) => ({ ...record(match), resume_id: root.resume_id, result_role_id: roleId, result_kind: 'resume' }))
    }
    const nested = record(root.data ?? root.results ?? root.result)
    const candidates = root.items ?? root.matches ?? root.leaderboard ?? root.results ?? root.data
      ?? nested.items ?? nested.matches ?? nested.leaderboard ?? nested.results
    if (Array.isArray(candidates)) return candidates.map(record)
    if (candidates && typeof candidates === 'object') {
      return Object.entries(candidates as ApiRecord).map(([key, item]) => ({ candidate_id: key, ...record(item) }))
    }
    if (root.candidate_id || root.resume_id || root.score !== undefined || root.match) return [root]
    return []
  }

  function candidateId(row: ApiRecord) {
    const candidate = record(row.candidate)
    return String(row.candidate_id ?? row.resume_id ?? row._id ?? row.id ?? candidate._id ?? '—')
  }

  function candidateName(row: ApiRecord) {
    const candidate = record(row.candidate)
    return String(row.candidate_name ?? row.name ?? candidate.name ?? '—')
  }

  function roleName(row: ApiRecord) {
    const role = record(row.role)
    return String(row.result_role_id ?? row.role_id ?? row.role_name ?? role.title ?? (typeof row.role === 'string' ? row.role : '') ?? roleId ?? '—') || '—'
  }

  function matchScore(row: ApiRecord) {
    const match = record(row.match)
    const score = row.score ?? row.total_score ?? row.match_score ?? match.score
    return typeof score === 'number' ? `${score.toFixed(1).replace(/\.0$/, '')}%` : displayValue(score)
  }

  function matchedSkills(row: ApiRecord) {
    const match = record(row.match)
    const skills = row.matched_skills ?? match.matched_skills ?? row.skills_matched
    return Array.isArray(skills) ? skills.map(displayValue).join(', ') : '—'
  }

  function missingSkills(row: ApiRecord) {
    const match = record(row.match)
    const skills = row.missing_skills ?? match.missing_skills
    return Array.isArray(skills) && skills.length ? skills.map(displayValue).join(', ') : '—'
  }

  function metric(row: ApiRecord, key: string) {
    const scoreKey = key === 'skills' ? 'skill_score' : `${key}_score`
    const score = record(row.breakdown)[key] ?? row[scoreKey]
    if (typeof score !== 'number') return '—'
    return `${score.toFixed(1).replace(/\.0$/, '')}${key === 'skill' || key === 'skills' || key === 'years' || key === 'seniority' || key === 'relevance' ? '%' : ''}`
  }

  function resultLabel() {
    if (tab === 'Role leaderboard') return `Leaderboard · ${roleId}`
    if (tab === 'Resume matches') return `Matches · ${resumeId}`
    if (tab === 'Match candidate') return 'Match result'
    return 'Run result'
  }

  onMount(() => {
    tab = initialTab as MatchTab
    void loadJobs()
  })

  async function run(action: () => Promise<unknown>) {
    busy = true
    onError('')
    try { result = await action() }
    catch (cause) { onError(cause instanceof Error ? cause.message : 'Matching request failed.') }
    finally { busy = false }
  }

  async function loadJobs() {
    try {
      const data = await request<unknown>(`/api/v1/matching/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`)
      jobs = Array.isArray(data) ? data as ApiRecord[] : ((data as ApiRecord).items ?? (data as ApiRecord).results ?? []) as ApiRecord[]
    } catch (cause) { onError(cause instanceof Error ? cause.message : 'Could not load run history.') }
  }

  async function matchOne() {
    if (!resumeId.trim() || !roleId.trim()) return onError('Enter both a resume ID and role ID.')
    await run(() => request(`/api/v1/matching/resumes/${encodeURIComponent(resumeId.trim())}/roles/${encodeURIComponent(roleId.trim())}`, { method: 'POST' }))
  }

  async function runRole() {
    if (!roleId.trim()) return onError('Enter a role ID to run matching.')
    await run(() => request(`/api/v1/matching/roles/${encodeURIComponent(roleId.trim())}/run`, { method: 'POST' }))
  }

  async function showLeaderboard() {
    if (!roleId.trim()) return onError('Enter a role ID to view its leaderboard.')
    await run(() => request(`/api/v1/matching/roles/${encodeURIComponent(roleId.trim())}/leaderboard?limit=${limit}&min_score=${minScore}`))
  }

  async function showResumeMatches() {
    if (!resumeId.trim()) return onError('Enter a resume ID to inspect its matches.')
    await run(() => request(`/api/v1/matching/resumes/${encodeURIComponent(resumeId.trim())}`))
  }

  async function clearMatch() {
    if (!resumeId.trim() || !roleId.trim()) return onError('Enter both IDs to clear a match.')
    await run(() => request(`/api/v1/matching/resumes/${encodeURIComponent(resumeId.trim())}/roles/${encodeURIComponent(roleId.trim())}`, { method: 'DELETE' }))
  }

  async function runAll() {
    await run(() => request('/api/v1/matching/run-all', { method: 'POST' }))
  }
</script>

<div class="page-heading"><div><p class="eyebrow">Candidate evaluation</p><h1>Matching</h1><p class="subheading">Run and inspect resume-to-role matching.</p></div><button class="button primary" onclick={runAll} disabled={busy}><Play size={15} /> Run all roles</button></div>
<div class="tab-strip" role="tablist" aria-label="Matching tools">
  {#each ['Match candidate', 'Role leaderboard', 'Resume matches', 'Jobs'] as item}<button role="tab" aria-selected={tab === item} class:active={tab === item} onclick={() => { tab = item as MatchTab; result = null; if (item === 'Jobs') void loadJobs() }}>{item}</button>{/each}
</div>
{#if tab === 'Jobs'}
  <section class="panel">
    <div class="panel-head"><div><div class="panel-title">Run history</div><div class="panel-subtitle">Inspect status and outcomes of matching runs.</div></div><div class="filters"><input class="input extra-filter" placeholder="Status" aria-label="Filter job status" bind:value={status} /><button class="button" onclick={loadJobs}><Search size={14} /> Filter</button><button class="icon-button" onclick={loadJobs} aria-label="Refresh run history"><RotateCcw size={14} /></button></div></div>
    {#if jobs.length}<div class="table-wrap"><table><thead><tr><th>Job ID</th><th>Role</th><th>Status</th><th>Started</th><th>Finished</th></tr></thead><tbody>{#each jobs as job}<tr><td>{String(job._id ?? job.id ?? '—')}</td><td>{String(job.role_id ?? 'All roles')}</td><td>{String(job.status ?? '—')}</td><td>{String(job.started_at ?? job.created_at ?? '—')}</td><td>{String(job.finished_at ?? '—')}</td></tr>{/each}</tbody></table></div>{:else}<div class="empty">No matching jobs found.</div>{/if}
  </section>
{:else}
  <section class="panel matching-panel">
    <div class="matching-form">
      {#if tab !== 'Role leaderboard'}<label class="field"><span>Resume ID</span><input class="input" bind:value={resumeId} placeholder="Resume _id" /></label>{/if}
      {#if tab !== 'Resume matches'}<RoleSelect id="matching-role-id" name="role_id" label="Role ID" value={roleId} onChange={(value) => roleId = value} />{/if}
      {#if tab === 'Role leaderboard'}<label class="field"><span>Minimum score</span><input class="input" type="number" min="0" max="100" bind:value={minScore} /></label><label class="field"><span>Result limit</span><input class="input" type="number" min="1" max="200" bind:value={limit} /></label>{/if}
    </div>
    <div class="matching-actions">
      {#if tab === 'Match candidate'}<button class="button primary" onclick={matchOne} disabled={busy}><Play size={14} /> Match resume to role</button><button class="button" onclick={runRole} disabled={busy}><RotateCcw size={14} /> Run all resumes for role</button><button class="button" onclick={clearMatch} disabled={busy}><Trash2 size={14} /> Clear this match</button>
      {:else if tab === 'Role leaderboard'}<button class="button primary" onclick={showLeaderboard} disabled={busy}><Search size={14} /> Load leaderboard</button><button class="button" onclick={runRole} disabled={busy}><RotateCcw size={14} /> Re-run role matching</button>
      {:else}<button class="button primary" onclick={showResumeMatches} disabled={busy}><Search size={14} /> Load resume matches</button>{/if}
    </div>
    {#if result !== null}
      <div class="match-result">
        <div class="match-result-heading"><div><div class="panel-title">{resultLabel()}</div><div class="panel-subtitle">{resultRows.length} result{resultRows.length === 1 ? '' : 's'}</div></div></div>
        {#if resultRows.length}
          {#if tab === 'Match candidate'}
            <div class="match-layout-title">Candidate to role match</div>
            <div class="match-result-context"><span>Resume <code>{resultRows[0].resume_id ?? resumeId}</code></span><span>Role <code>{resultRows[0].role_id ?? roleId}</code></span></div>
            <div class="table-wrap match-result-table"><table><thead><tr><th>Overall score</th><th>Skill score</th><th>Years score</th><th>Seniority score</th><th>Relevance score</th><th>Matched skills</th><th>Missing skills</th></tr></thead><tbody>
              {#each resultRows as row, index (`single-${index}`)}<tr><td><span class="match-score-pill">{matchScore(row)}</span></td><td>{metric(row, 'skills')}</td><td>{metric(row, 'years')}</td><td>{metric(row, 'seniority')}</td><td>{metric(row, 'relevance')}</td><td>{matchedSkills(row)}</td><td>{missingSkills(row)}</td></tr>{/each}
            </tbody></table></div>
          {:else if tab === 'Resume matches'}
            <div class="match-layout-title">Role scores for this resume</div>
            <div class="match-result-context"><span>Resume <code>{resultRows[0].resume_id ?? resumeId}</code></span></div>
            <div class="table-wrap match-result-table"><table><thead><tr><th>Role ID</th><th>Overall score</th><th>Skill score</th><th>Years score</th><th>Seniority score</th><th>Relevance score</th><th>Matched skills</th><th>Missing skills</th></tr></thead><tbody>
              {#each resultRows as row, index (`${roleName(row)}-${index}`)}<tr><td><code>{roleName(row)}</code></td><td><span class="match-score-pill">{matchScore(row)}</span></td><td>{metric(row, 'skills')}</td><td>{metric(row, 'years')}</td><td>{metric(row, 'seniority')}</td><td>{metric(row, 'relevance')}</td><td>{matchedSkills(row)}</td><td>{missingSkills(row)}</td></tr>{/each}
            </tbody></table></div>
          {:else}
            <div class="table-wrap match-result-table"><table><thead><tr><th>#</th><th>Candidate</th><th>Resume ID</th><th>Role</th><th>Score</th><th>Matched skills</th><th>Missing skills</th></tr></thead><tbody>
              {#each resultRows as row, index (`${candidateId(row)}-${index}`)}<tr><td>{index + 1}</td><td>{candidateName(row)}</td><td><code>{candidateId(row)}</code></td><td>{roleName(row)}</td><td><span class="match-score-pill">{matchScore(row)}</span></td><td>{matchedSkills(row)}</td><td>{missingSkills(row)}</td></tr>{/each}
            </tbody></table></div>
          {/if}
        {:else}
          <div class="match-run-status"><span class="match-status-dot"></span><div><strong>{String(record(result).status ?? record(result).message ?? 'Matching request accepted')}</strong><small>{String(record(result).job_id ?? record(result).id ?? 'The run is queued or completed.')}</small></div></div>
        {/if}
        <details class="match-raw"><summary>Raw response</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
      </div>
    {/if}
  </section>
{/if}