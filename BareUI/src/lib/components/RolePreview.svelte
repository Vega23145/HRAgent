<script lang="ts">
  import { BriefcaseBusiness, Clock3, Pencil, X } from '@lucide/svelte'
  import type { ApiRecord } from '../types'
  import { displayValue, formatRequiredSkills } from '../format'

  let { role, onClose, onEdit }: { role: ApiRecord; onClose: () => void; onEdit: () => void } = $props()

  const scoreWeights = $derived([
    { label: 'Skills', value: Number(role.w_skills ?? 0.4), color: 'skills' },
    { label: 'Experience', value: Number(role.w_years ?? 0.25), color: 'years' },
    { label: 'Seniority', value: Number(role.w_seniority ?? 0.2), color: 'seniority' },
    { label: 'Relevance', value: Number(role.w_relevance ?? 0.15), color: 'relevance' },
  ])
  const skills = $derived(formatRequiredSkills(role.required_skills))
  const responsibilities = $derived(Array.isArray(role.responsibilities) ? role.responsibilities.map(displayValue) : [])
  const niceToHave = $derived(Array.isArray(role.nice_to_have) ? role.nice_to_have.map(displayValue) : [])
  const techStack = $derived(Array.isArray(role.tech_stack) ? role.tech_stack.map(displayValue) : [])
</script>

<div class="modal-backdrop role-preview-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) onClose() }}>
  <dialog open class="modal role-preview" aria-labelledby="role-preview-title">
    <header class="role-preview-head">
      <div class="role-preview-mark"><BriefcaseBusiness size={20} /></div>
      <div class="role-preview-heading">
        <div class="role-preview-id">{displayValue(role._id)}</div>
        <h2 id="role-preview-title">{displayValue(role.title)}</h2>
        <p>{[role.department, role.team].filter(Boolean).map(String).join(' · ') || 'Role details'}</p>
      </div>
      <div class="role-preview-actions"><button class="button" onclick={onEdit}><Pencil size={14} /> Edit role</button><button class="icon-button" onclick={onClose} aria-label="Close role preview"><X size={16} /></button></div>
    </header>

    <div class="role-preview-body">
      <div class="role-fact-row">
        <div class="role-fact"><span>Experience</span><strong>{displayValue(role.experience_level)}</strong><small>{displayValue(role.min_years)} minimum years</small></div>
        <div class="role-fact"><span>Work mode</span><strong>{displayValue(role.work_mode)}</strong><small>{displayValue(role.employment_type)}</small></div>
        <div class="role-fact"><span>Seniority</span><strong>{displayValue(role.seniority)}</strong><small>Seniority level</small></div>
      </div>

      {#if role.description}<section class="role-preview-section"><h3>Role overview</h3><p>{String(role.description)}</p></section>{/if}

      <section class="role-preview-section">
        <div class="role-preview-section-head"><h3>Required skills</h3><span>{skills.length} skills</span></div>
        {#if skills.length}<div class="role-preview-skill-list">{#each skills as skill (`${skill.name}-${skill.weight}`)}<div class="role-preview-skill"><span>{skill.name}</span>{#if skill.weight !== null}<div class="skill-weight-meter"><i style={`width:${Math.min(100, skill.weight * 10)}%`}></i></div><strong>{skill.weight} / 10</strong>{/if}</div>{/each}</div>{:else}<p class="role-preview-empty">No required skills configured.</p>{/if}
      </section>

      {#if techStack.length}<section class="role-preview-section"><h3>Technology stack</h3><div class="role-preview-tags">{#each techStack as item (item)}<span>{item}</span>{/each}</div></section>{/if}

      {#if responsibilities.length}<section class="role-preview-section"><h3>Responsibilities</h3><ul class="role-preview-list">{#each responsibilities as item (item)}<li>{item}</li>{/each}</ul></section>{/if}

      {#if niceToHave.length}<section class="role-preview-section"><h3>Nice to have</h3><div class="role-preview-tags optional">{#each niceToHave as item (item)}<span>{item}</span>{/each}</div></section>{/if}

      <section class="role-preview-section">
        <div class="role-preview-section-head"><h3>Scoring mix</h3><span>Weights</span></div>
        <div class="role-score-grid">{#each scoreWeights as weight (weight.label)}<div class="role-score-item"><div><span>{weight.label}</span><strong>{Math.round(weight.value * 100)}%</strong></div><div class="role-score-track"><i class={`score-${weight.color}`} style={`width:${Math.max(0, Math.min(100, weight.value * 100))}%`}></i></div></div>{/each}</div>
      </section>
    </div>
  </dialog>
</div>