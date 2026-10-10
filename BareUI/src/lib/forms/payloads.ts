import type { ApiRecord, ResourceDefinition } from '../types'
import { resumeEntryFields, type ResumeEntrySection } from './resumeEntries'

function words(form: FormData, name: string) {
  return String(form.get(name) ?? '').split(',').map((item) => item.trim()).filter(Boolean)
}

function lines(form: FormData, name: string) {
  return String(form.get(name) ?? '').split('\n').map((item) => item.trim()).filter(Boolean)
}

function resumeEntries(form: FormData, section: ResumeEntrySection, previous: unknown) {
  const prefix = new RegExp(`^${section}_(\\d+)_`)
  const indices = [...form.keys()].flatMap((key) => {
    const match = key.match(prefix)
    return match ? [Number(match[1])] : []
  })
  const uniqueIndices = [...new Set(indices)].sort((left, right) => left - right)
  const previousEntries = Array.isArray(previous) ? previous : []
  return uniqueIndices.flatMap((index) => {
    const sourceIndex = Number(form.get(`${section}_${index}_source_index`))
    const oldEntry = Number.isInteger(sourceIndex) && sourceIndex >= 0 ? previousEntries[sourceIndex] : undefined
    const entry = oldEntry && typeof oldEntry === 'object' && !Array.isArray(oldEntry) ? oldEntry as ApiRecord : {}
    const values = Object.fromEntries(resumeEntryFields[section].map((field) => {
      const raw = String(form.get(`${section}_${index}_${field.name}`) ?? '').trim()
      return [field.name, field.list ? raw.split('\n').map((line) => line.trim()).filter(Boolean) : raw]
    }))
    if (Object.values(values).every((value) => Array.isArray(value) ? value.length === 0 : !value)) return []
    return [{ ...entry, ...values }]
  })
}

export function createResourcePayload(resource: ResourceDefinition, form: FormData, existing?: ApiRecord): Record<string, unknown> | null {
  if (resource.create === 'role') {
    const requiredSkills = [...form.entries()]
      .filter(([key, value]) => key.startsWith('skill_name_') && String(value).trim())
      .map(([key, value]) => {
        const index = key.slice('skill_name_'.length)
        return { name: String(value).trim(), weight: Number(form.get(`skill_weight_${index}`)) }
      })
    return {
      ...existing,
      _id: existing?._id ?? form.get('id'), title: form.get('title'), department: form.get('department') || null,
      team: form.get('team') || null, employment_type: form.get('employment_type'), work_mode: form.get('work_mode'),
      experience_level: form.get('experience_level'), description: form.get('description') || '',
      responsibilities: lines(form, 'responsibilities'), tech_stack: words(form, 'tech_stack'),
      nice_to_have: words(form, 'nice_to_have'), required_skills: requiredSkills,
      min_years: Number(form.get('min_years') || 0), seniority: Number(form.get('seniority') || 1),
      w_skills: Number(form.get('w_skills') || 0.4), w_years: Number(form.get('w_years') || 0.25),
      w_seniority: Number(form.get('w_seniority') || 0.2), w_relevance: Number(form.get('w_relevance') || 0.15),
    }
  }

  if (resource.create === 'task') return {
    role_id: form.get('role_id'), title: form.get('title'), description: form.get('description'),
    instructions: form.get('instructions') || '', deadline: form.get('deadline') || null,
    is_open: form.get('is_open') === 'on',
  }

  if (resource.create === 'user') return {
    email: form.get('email'), full_name: form.get('full_name') || null, password: form.get('password'),
    roles: words(form, 'roles'), is_active: true, grants: words(form, 'grants'), denies: words(form, 'denies'),
  }

  if (resource.create === 'submission') return {
    task_id: form.get('task_id'), candidate_id: form.get('candidate_id'), candidate_name: form.get('candidate_name'),
    candidate_email: form.get('candidate_email') || null, demo_video_url: form.get('demo_video_url'),
    project_url: form.get('project_url') || null, repo_url: form.get('repo_url') || null, notes: form.get('notes') || '',
  }

  if (resource.create === 'resume') {
    const skillItems = words(form, 'skills')
    const previousResume = existing?.resume && typeof existing.resume === 'object' ? existing.resume as ApiRecord : {}
    const previousContact = existing?.contact && typeof existing.contact === 'object' ? existing.contact as ApiRecord : {}
    const previousEmail = existing?.email && typeof existing.email === 'object' ? existing.email as ApiRecord : {}
    const emails = words(form, 'emails')
    const phones = words(form, 'phones')
    const urls = words(form, 'urls')
    const sender = form.get('sender') || previousEmail.sender || null
    const subject = form.get('subject') || previousEmail.subject || null
    const messageId = form.get('message_id') || previousEmail.message_id || null
    const date = form.get('date') || previousEmail.date || null
    return {
      ...existing,
      _id: form.get('id') || existing?._id || null,
      email: sender || subject || messageId || date
        ? { ...previousEmail, sender, subject, message_id: messageId, date }
        : existing?.email ?? null,
      body: form.get('body') || existing?.body || null, resume_file: form.get('resume_file') || existing?.resume_file || null,
      contact: {
        ...previousContact,
        ...(emails.length ? { emails } : {}),
        ...(phones.length ? { phones } : {}),
        ...(urls.length ? { urls } : {}),
      },
      resume: {
        ...previousResume,
        name: form.get('name') || previousResume.name || null,
        summary: form.get('summary') || previousResume.summary || null,
        skills: skillItems.length ? [{ category: 'General', items: skillItems }] : previousResume.skills ?? [],
        experience: resumeEntries(form, 'experience', previousResume.experience),
        education: resumeEntries(form, 'education', previousResume.education),
        projects: resumeEntries(form, 'projects', previousResume.projects),
        certifications: resumeEntries(form, 'certifications', previousResume.certifications),
        interests: words(form, 'interests').length ? words(form, 'interests') : previousResume.interests ?? [],
      },
    }
  }

  return null
}

export function createEndpoint(resource: ResourceDefinition, payload: Record<string, unknown>) {
  if (resource.create !== 'submission') return resource.endpoint
  const taskId = String(payload.task_id ?? '')
  if (!taskId) throw new Error('Task ID is required to submit candidate work.')
  delete payload.task_id
  return `/api/v1/task-review/tasks/${encodeURIComponent(taskId)}/submissions`
}