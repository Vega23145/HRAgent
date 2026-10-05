<script lang="ts">
  import { Activity, ArrowRight, BriefcaseBusiness, ClipboardList, FileText, Mail } from '@lucide/svelte'
  import type { ApiRecord } from '../types'
  import { displayValue } from '../format'

  let { stats, manifest, loading = false, onRunMatches, onOpen }: {
    stats: ApiRecord | null
    manifest: ApiRecord | null
    loading?: boolean
    onRunMatches: () => void
    onOpen: (label: string) => void
  } = $props()

  function flatten(record: ApiRecord | null, prefix = ''): { label: string; value: unknown }[] {
    if (!record) return []
    return Object.entries(record).flatMap(([key, value]) => {
      const label = prefix ? `${prefix} / ${key}` : key
      if (value && typeof value === 'object' && !Array.isArray(value)) return flatten(value as ApiRecord, label)
      if (Array.isArray(value)) return [{ label, value: `${value.length} items` }]
      return [{ label, value }]
    }).slice(0, 12)
  }

  const metrics = $derived(flatten(stats).slice(0, 8).map((metric) => ({
    ...metric,
    label: metric.label.split('/').map((part) => part.trim().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())).join(' / '),
  })))
</script>

<div class="page-heading">
  <div><p class="eyebrow">Recruiting workspace</p><h1>Overview</h1><p class="subheading">A quick look at your hiring pipeline.</p></div>
  <button class="button" onclick={onRunMatches}><Activity size={15} /> Run all matches</button>
</div>
<div class="stats-grid">
  {#each metrics as metric (metric.label)}
    <article class="stat"><div class="stat-top"><span>{metric.label}</span><Activity size={16} /></div><div class="stat-value">{loading ? '…' : displayValue(metric.value)}</div><div class="stat-note">Live workspace value</div></article>
  {/each}
  {#if !metrics.length}<div class="empty panel">{loading ? 'Loading workspace statistics…' : 'No statistics returned by the API.'}</div>{/if}
</div>
<div class="panel">
  <div class="panel-head"><div><div class="panel-title">Workspace resources</div><div class="panel-subtitle">Jump into hiring records and administration.</div></div></div>
  <div class="resource-shortcuts">
    {#each ['Resumes', 'Job roles', 'Matching', 'Tasks', 'Submissions', 'Email jobs', 'Email templates', 'Users', 'Access roles', 'Audit log', 'Permissions'] as label}
      <button class="shortcut" onclick={() => onOpen(label)}><span>{label}</span><ArrowRight size={15} /></button>
    {/each}
  </div>
  {#if manifest}
    <details class="manifest-details"><summary>Access and resource manifest</summary><pre class="manifest-json">{JSON.stringify(manifest, null, 2)}</pre></details>
  {/if}
</div>