<script lang="ts">
  import { BriefcaseBusiness, ExternalLink, GraduationCap, Pencil, X } from '@lucide/svelte'
  import type { ApiRecord } from '../types'
  import { formatCandidate } from '../format'

  let { record, onClose, onEdit }: { record: ApiRecord; onClose: () => void; onEdit: () => void } = $props()
  const candidate = $derived(formatCandidate(record))
</script>

<div class="modal-backdrop candidate-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) onClose() }}>
  <dialog open class="modal candidate-preview" aria-labelledby="candidate-preview-title">
    <div class="candidate-preview-head">
      <div class="candidate-avatar">{candidate.name.slice(0, 1).toUpperCase()}</div>
      <div class="candidate-preview-title-block"><div class="candidate-id-line"><span class="candidate-id-label">RESUME ID</span><code>{candidate.id || 'ID unavailable'}</code></div><h2 id="candidate-preview-title">{candidate.name}</h2><p>{candidate.headline || candidate.email || 'Candidate profile'}</p></div>
      <div class="candidate-preview-actions"><button class="button" onclick={onEdit}><Pencil size={14} /> Edit</button><button class="icon-button" onclick={onClose} aria-label="Close candidate preview"><X size={16} /></button></div>
    </div>
    <div class="candidate-preview-body">
      <section class="candidate-profile-meta"><span>{candidate.email || 'No email'}</span>{#if candidate.received}<span>Received {candidate.received}</span>{/if}{#if candidate.file}<span>File: {candidate.file}</span>{/if}{#each candidate.urls as url (url)}<a href={url} target="_blank" rel="noreferrer"><ExternalLink size={13} />{url}</a>{/each}</section>
      {#if candidate.summary}<section class="candidate-preview-section"><h3>Profile summary</h3><p>{candidate.summary}</p></section>{/if}
      {#if candidate.totalExperience}<section class="candidate-preview-section"><h3>Total experience</h3><p>{candidate.totalExperience} calculated from non-overlapping work-history date ranges.</p></section>{/if}
      <section class="candidate-preview-section"><h3>Skills</h3>{#if candidate.skills.length}<div class="skill-chips">{#each candidate.skills as skill (skill)}<span>{skill}</span>{/each}</div>{:else}<p class="candidate-muted">No skills listed.</p>{/if}</section>
      <section class="candidate-preview-section"><h3><BriefcaseBusiness size={15} /> Experience</h3>{#if candidate.experience.length}{#each candidate.experience as item, index (`${item.company}-${item.title}-${index}`)}<article class="timeline-entry"><div class="timeline-top"><strong>{item.title || 'Experience'}</strong><span>{item.period}</span></div><div class="timeline-sub">{item.company}</div>{#if item.highlights.length}<ul>{#each item.highlights as highlight (highlight)}<li>{highlight}</li>{/each}</ul>{/if}</article>{/each}{:else}<p class="candidate-muted">No experience listed.</p>{/if}</section>
      <section class="candidate-preview-section"><h3><GraduationCap size={16} /> Education</h3>{#if candidate.education.length}{#each candidate.education as item, index (`${item.institution}-${index}`)}<article class="timeline-entry"><div class="timeline-top"><strong>{item.institution || 'Education'}</strong><span>{item.period}</span></div><div class="timeline-sub">{item.degree}</div></article>{/each}{:else}<p class="candidate-muted">No education listed.</p>{/if}</section>
      {#if candidate.projects.length}<section class="candidate-preview-section"><h3>Projects</h3>{#each candidate.projects as project, index (`${project.name}-${index}`)}<article class="timeline-entry"><div class="timeline-top"><strong>{project.name || 'Project'}</strong></div>{#if project.tech.length}<div class="timeline-sub">{project.tech.join(' · ')}</div>{/if}{#each project.highlights as highlight (highlight)}<p>{highlight}</p>{/each}</article>{/each}</section>{/if}
      {#if candidate.certifications.length}<section class="candidate-preview-section"><h3>Certifications</h3>{#each candidate.certifications as item, index (`${item.name}-${index}`)}<div class="cert-row"><strong>{item.name}</strong><span>{item.issuer}</span></div>{/each}</section>{/if}
      {#if candidate.matches.length}<section class="candidate-preview-section"><h3>Role matches</h3>{#each [...candidate.matches].sort((a, b) => b.scoreValue - a.scoreValue) as match (match.role)}<div class="preview-match"><span>{match.role}</span><strong>{match.score || 'Matched'}</strong></div>{#if match.matchedSkills.length}<div class="preview-match-skills">Matched: {match.matchedSkills.join(', ')}</div>{/if}{#if match.missingSkills.length}<div class="preview-match-skills missing">Missing: {match.missingSkills.join(', ')}</div>{/if}{/each}</section>{/if}
      {#if candidate.interests.length}<section class="candidate-preview-section"><h3>Interests</h3><div class="skill-chips">{#each candidate.interests as interest (interest)}<span>{interest}</span>{/each}</div></section>{/if}
    </div>
  </dialog>
</div>