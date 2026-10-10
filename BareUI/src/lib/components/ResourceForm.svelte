<script lang="ts">
  import { X } from '@lucide/svelte'
  import type { ResourceDefinition } from '../types'
  import FormField from './FormField.svelte'
  import FormTextArea from './FormTextArea.svelte'
  import ResumeEntriesEditor from './ResumeEntriesEditor.svelte'
  import RequiredSkillsEditor from './RequiredSkillsEditor.svelte'
  import RoleSelect from './RoleSelect.svelte'
  import { displayValue, getPath } from '../format'
  import type { ApiRecord } from '../types'

  let { resource, record = null, busy = false, onClose, onSubmit }: {
    resource: ResourceDefinition
    record?: ApiRecord | null
    busy?: boolean
    onClose: () => void
    onSubmit: (event: SubmitEvent, form: HTMLFormElement) => void
  } = $props()

  const kind = $derived(resource.create)
  function field(path: string, fallback = '') {
    const value = record ? getPath(record, path) : undefined
    return value === undefined || value === null ? fallback : displayValue(value)
  }
  function listField(path: string) {
    const value = record ? getPath(record, path) : undefined
    if (!Array.isArray(value)) return ''
    return value.map((item) => typeof item === 'object' && item !== null ? String((item as ApiRecord).name ?? '') : String(item)).filter(Boolean).join(', ')
  }
  function entryRecords(path: string) {
    const value = record ? getPath(record, path) : undefined
    if (!Array.isArray(value)) return []
    return value.filter((item): item is ApiRecord => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
  }
  function commaField(path: string) {
    const value = record ? getPath(record, path) : undefined
    if (!Array.isArray(value)) return ''
    return value.map((item) => typeof item === 'object' && item !== null ? String((item as ApiRecord).name ?? '') : String(item)).filter(Boolean).join(', ')
  }
  const initialRoleSkills = $derived.by(() => {
    const value = record?.required_skills
    return Array.isArray(value) ? value.flatMap((item) => {
      if (!item || typeof item !== 'object') return []
      const skill = item as ApiRecord
      return typeof skill.name === 'string' ? [{ name: skill.name, weight: Number(skill.weight) || 1 }] : []
    }) : []
  })
</script>

<div class="modal-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) onClose() }}>
  <dialog open class="modal" class:role-form-modal={kind === 'role'} aria-labelledby="dialog-title">
    <div class="modal-head"><h2 id="dialog-title">{record ? 'Edit' : 'Create'} {resource.noun}</h2><button class="icon-button" onclick={onClose} aria-label="Close"><X size={16} /></button></div>
    <form class="form" onsubmit={(event) => onSubmit(event, event.currentTarget as HTMLFormElement)}>
      {#if kind === 'role'}
        <div class="role-form-grid">
          <FormField id="role-id" name="id" label="Role ID" required placeholder="senior-engineer" value={field('_id')} disabled={Boolean(record)} />
          <FormField id="role-title" name="title" label="Title" required maxlength={200} value={field('title')} />
          <FormField id="department" name="department" label="Department" value={field('department')} />
          <FormField id="role-team" name="team" label="Team" value={field('team')} />
          <FormField id="employment-type" name="employment_type" label="Employment type" value={field('employment_type', 'full-time')} />
          <FormField id="work-mode" name="work_mode" label="Work mode" value={field('work_mode', 'onsite')} />
          <FormField id="experience-level" name="experience_level" label="Experience level" value={field('experience_level', 'junior')} />
          <FormField id="min-years" name="min_years" label="Minimum years experience" type="number" min="0" step="0.5" value={field('min_years', '0')} />
          <FormField id="seniority" name="seniority" label="Seniority level" type="number" min="0" value={field('seniority', '1')} />
          <FormField id="tech-stack" name="tech_stack" label="Tech stack, comma separated" value={commaField('tech_stack')} />
          <FormField id="nice-to-have" name="nice_to_have" label="Nice to have, comma separated" value={commaField('nice_to_have')} />
        </div>
        <FormTextArea id="role-description" name="description" label="Description" value={field('description')} />
        <FormTextArea id="responsibilities" name="responsibilities" label="Responsibilities, one per line" value={Array.isArray(record?.responsibilities) ? record.responsibilities.map(String).join('\n') : ''} />
        <RequiredSkillsEditor initialSkills={initialRoleSkills} />
        <div class="form-section-title">Scoring configuration</div>
        <div class="weight-grid">
          <FormField id="w-skills" name="w_skills" label="Skills weight" type="number" min="0" max="1" step="0.01" value={field('w_skills', '0.4')} />
          <FormField id="w-years" name="w_years" label="Years weight" type="number" min="0" max="1" step="0.01" value={field('w_years', '0.25')} />
          <FormField id="w-seniority" name="w_seniority" label="Seniority weight" type="number" min="0" max="1" step="0.01" value={field('w_seniority', '0.2')} />
          <FormField id="w-relevance" name="w_relevance" label="Relevance weight" type="number" min="0" max="1" step="0.01" value={field('w_relevance', '0.15')} />
        </div>
      {:else if kind === 'task'}
        <RoleSelect id="task-role" name="role_id" label="Role ID" required />
        <FormField id="task-title" name="title" label="Title" required maxlength={200} />
        <FormTextArea id="task-description" name="description" label="Description" required maxlength={5000} />
        <FormTextArea id="task-instructions" name="instructions" label="Instructions for the candidate" maxlength={5000} />
        <FormField id="task-deadline" name="deadline" label="Deadline" type="date" />
        <label class="toggle-field"><input type="checkbox" name="is_open" checked /> Accept submissions</label>
      {:else if kind === 'user'}
        <FormField id="user-email" name="email" label="Email" type="email" required maxlength={254} />
        <FormField id="user-name" name="full_name" label="Full name" maxlength={120} />
        <FormField id="user-password" name="password" label="Temporary password" type="password" required minlength={12} maxlength={128} />
        <FormField id="user-roles" name="roles" label="Roles, comma separated" />
        <FormField id="user-grants" name="grants" label="Permission grants, comma separated" />
        <FormField id="user-denies" name="denies" label="Permission denies, comma separated" />
      {:else if kind === 'submission'}
        <p class="form-guidance">Share links to the candidate's deliverables. Google Drive, Loom, and YouTube links are accepted for the demo video.</p>
        <FormField id="submission-task-id" name="task_id" label="Task ID" required />
        <FormField id="submission-candidate-id" name="candidate_id" label="Candidate resume ID" required maxlength={64} />
        <FormField id="submission-candidate-name" name="candidate_name" label="Candidate name" required maxlength={120} />
        <FormField id="submission-candidate-email" name="candidate_email" label="Candidate email" type="email" maxlength={254} />
        <FormField id="submission-demo" name="demo_video_url" label="Demo video URL (Drive, Loom, YouTube)" type="url" required minlength={5} maxlength={500} />
        <FormField id="submission-project" name="project_url" label="Live project URL" type="url" minlength={5} maxlength={500} />
        <FormField id="submission-repo" name="repo_url" label="Repository URL" type="url" minlength={5} maxlength={500} />
        <FormTextArea id="submission-notes" name="notes" label="Candidate notes" maxlength={3000} />
      {:else if kind === 'resume'}
        <FormField id="resume-id" name="id" label="Resume ID (optional)" value={field('_id')} />
        <FormField id="resume-name" name="name" label="Candidate name" value={field('resume.name', field('name'))} />
        <FormField id="resume-sender" name="sender" label="Source email sender" type="email" value={field('email.sender')} />
        <FormField id="resume-subject" name="subject" label="Source email subject" value={field('email.subject')} />
        <FormField id="resume-message-id" name="message_id" label="Email message ID" value={field('email.message_id')} />
        <FormField id="resume-date" name="date" label="Email date" type="text" value={field('email.date')} />
        <!-- <FormField id="resume-file" name="resume_file" label="Resume file name" placeholder="candidate-resume.pdf" value={field('resume_file')} /> -->
        <FormField id="resume-emails" name="emails" label="Contact emails, comma separated" value={listField('contact.emails')} />
        <FormField id="resume-phones" name="phones" label="Contact phones, comma separated" value={listField('contact.phones')} />
        <FormField id="resume-urls" name="urls" label="Contact URLs, comma separated" value={listField('contact.urls')} />
        <FormTextArea id="resume-body" name="body" label="Original resume text" value={field('body')} />
        <FormTextArea id="resume-summary" name="summary" label="Summary" value={field('resume.summary', field('summary'))} />
        <FormField id="resume-skills" name="skills" label="Skills, comma separated" value={listField('resume.skills')} />
        <ResumeEntriesEditor section="experience" label="Experience" initialEntries={entryRecords('resume.experience')} />
        <ResumeEntriesEditor section="education" label="Education" initialEntries={entryRecords('resume.education')} />
        <ResumeEntriesEditor section="projects" label="Projects" initialEntries={entryRecords('resume.projects')} />
        <ResumeEntriesEditor section="certifications" label="Certifications" initialEntries={entryRecords('resume.certifications')} />
        <FormField id="resume-interests" name="interests" label="Interests, comma separated" value={listField('resume.interests')} />
      {/if}
      <div class="modal-actions"><button class="button" type="button" onclick={onClose}>Cancel</button><button class="button primary" type="submit" disabled={busy}>{busy ? 'Saving…' : record ? 'Save changes' : 'Create'}</button></div>
    </form>
  </dialog>
</div>
