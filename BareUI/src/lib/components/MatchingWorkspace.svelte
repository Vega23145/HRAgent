<script lang="ts">
  import { onMount } from 'svelte'
  import { Play, RotateCcw, Search, Trash2 } from '@lucide/svelte'
  import { request } from '../api'
  import type { ApiRecord } from '../types'

  let { onError, initialTab = 'Match candidate' }: { onError: (error: string) => void; initialTab?: string } = $props()

  type MatchTab = 'Match candidate' | 'Role leaderboard' | 'Resume matches' | 'Jobs'
  let tab = $state<MatchTab>('Match candidate')
  let resumeId = $state('')
  let roleId = $state('')
  let limit = $state(25)
  let minScore = $state(0)
  let status = $state('')
  let result = $state<unknown>(null)
  let jobs = $state<ApiRecord[]>([])
  let busy = $state(false)

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
      {#if tab !== 'Resume matches'}<label class="field"><span>Role ID</span><input class="input" bind:value={roleId} placeholder="role-slug" /></label>{/if}
      {#if tab === 'Role leaderboard'}<label class="field"><span>Minimum score</span><input class="input" type="number" min="0" max="100" bind:value={minScore} /></label><label class="field"><span>Result limit</span><input class="input" type="number" min="1" max="200" bind:value={limit} /></label>{/if}
    </div>
    <div class="matching-actions">
      {#if tab === 'Match candidate'}<button class="button primary" onclick={matchOne} disabled={busy}><Play size={14} /> Match resume to role</button><button class="button" onclick={runRole} disabled={busy}><RotateCcw size={14} /> Run all resumes for role</button><button class="button" onclick={clearMatch} disabled={busy}><Trash2 size={14} /> Clear this match</button>
      {:else if tab === 'Role leaderboard'}<button class="button primary" onclick={showLeaderboard} disabled={busy}><Search size={14} /> Load leaderboard</button><button class="button" onclick={runRole} disabled={busy}><RotateCcw size={14} /> Re-run role matching</button>
      {:else}<button class="button primary" onclick={showResumeMatches} disabled={busy}><Search size={14} /> Load resume matches</button>{/if}
    </div>
    {#if result !== null}<div class="match-result"><div class="panel-title">Result</div><pre>{JSON.stringify(result, null, 2)}</pre></div>{/if}
  </section>
{/if}