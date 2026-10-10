<script lang="ts">
  import { ArrowLeft, ArrowRight, BriefcaseBusiness, Copy, Pencil, Search, ScanEye } from '@lucide/svelte'
  import type { ApiRecord, ResourceDefinition } from '../types'
  import { displayValue, formatRequiredSkills, formatRoleWeight } from '../format'

  let { resource, items, page, size, total, filters, loading = false, onFilter, onPage, onSize, onSelect, onEdit }: {
    resource: ResourceDefinition
    items: ApiRecord[]
    page: number
    size: number
    total: number
    filters: Record<string, string>
    loading?: boolean
    onFilter: (name: string, value: string) => void
    onPage: (page: number) => void
    onSize: (size: number) => void
    onSelect: (record: ApiRecord) => void
    onEdit: (record: ApiRecord) => void
  } = $props()

  const pageCount = $derived(Math.max(1, Math.ceil(total / size)))
  let copiedId = $state('')
  let copyError = $state('')

  async function copyRoleId(id: string) {
    if (!id) return
    try {
      await navigator.clipboard.writeText(id)
      copiedId = id
      copyError = ''
      setTimeout(() => { if (copiedId === id) copiedId = '' }, 1400)
    } catch {
      copyError = 'Clipboard unavailable'
    }
  }
</script>

<section class="panel role-panel">
  <div class="panel-head">
    <div><div class="panel-title">Job roles</div><div class="panel-subtitle">{total.toLocaleString()} roles</div></div>
    <div class="filters">
      <label class="searchbox"><Search size={15} /><input class="input" placeholder="Search roles…" aria-label="Search roles" value={filters.q ?? ''} oninput={(event) => onFilter('q', event.currentTarget.value)} /></label>
      {#each resource.filters ?? [] as filter (filter.name)}
        <input class="input extra-filter" type={filter.type ?? 'search'} placeholder={filter.label} aria-label={filter.label} value={filters[filter.name] ?? ''} oninput={(event) => onFilter(filter.name, event.currentTarget.value)} />
      {/each}
    </div>
  </div>
  {#if loading}<div class="loading">Loading job roles…</div>
  {:else if items.length === 0}<div class="empty">No job roles found.</div>
  {:else}<div class="table-wrap"><table class="role-table"><thead><tr><th>Role ID</th><th>Role</th><th>Required skills</th><th>Work setup</th><th>Scoring mix</th><th>Actions</th></tr></thead><tbody>
    {#each items as role, index (String(role._id ?? role.id ?? `${page}-${index}`))}
      {@const roleId = String(role._id ?? role.id ?? '')}
      {@const skills = formatRequiredSkills(role.required_skills)}
      <tr>
        <td><div class="role-id-cell"><code title={roleId}>{roleId || '—'}</code><button class="copy-id" onclick={() => void copyRoleId(roleId)} disabled={!roleId} title="Copy role ID" aria-label="Copy role ID"><Copy size={13} />{copiedId === roleId ? 'Copied' : 'Copy'}</button></div>{#if copyError}<small class="copy-error">{copyError}</small>{/if}</td>
        <td><div class="role-title">{displayValue(role.title)}</div><div class="role-meta">{[role.department, role.team].filter(Boolean).map(String).join(' · ') || 'No department'}</div></td>
        <td>{#if skills.length}<div class="role-skill-chips">{#each skills.slice(0, 6) as skill (`${skill.name}-${skill.weight}`)}<span class="role-skill-chip"><span>{skill.name}</span>{#if skill.weight !== null}<b>{skill.weight}</b>{/if}</span>{/each}{#if skills.length > 6}<span class="role-more">+{skills.length - 6}</span>{/if}</div>{:else}<span class="candidate-muted">No required skills</span>{/if}</td>
        <td><div class="role-setup">{displayValue(role.experience_level)}</div><div class="role-meta">{[role.employment_type, role.work_mode].filter(Boolean).map((value) => displayValue(value)).join(' · ') || '—'}</div></td>
        <td><div class="role-weights"><span>Skills <b>{formatRoleWeight(role.w_skills)}</b></span><span>Years <b>{formatRoleWeight(role.w_years)}</b></span><span>Seniority <b>{formatRoleWeight(role.w_seniority)}</b></span><span>Relevance <b>{formatRoleWeight(role.w_relevance)}</b></span></div></td>
        <td><div class="role-actions"><button class="icon-button" onclick={() => onEdit(role)} aria-label="Edit role" title="Edit role"><Pencil size={14} /></button><button class="icon-button" onclick={() => onSelect(role)} aria-label="Inspect role" title="Inspect role details"><ScanEye size={15} /></button></div></td>
      </tr>
    {/each}
  </tbody></table></div>{/if}
  <footer class="table-footer"><span>Showing {total ? (page - 1) * size + 1 : 0}–{Math.min(page * size, total)} of {total}</span><div class="pagination"><label for="role-page-size">Rows</label><select class="select" id="role-page-size" value={size} onchange={(event) => onSize(Number(event.currentTarget.value))}><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option></select><button onclick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page"><ArrowLeft size={14} /></button><span>{page} / {pageCount}</span><button onclick={() => onPage(page + 1)} disabled={page >= pageCount} aria-label="Next page"><ArrowRight size={14} /></button></div></footer>
</section>