import type { ApiRecord } from './types'

export function getPath(record: ApiRecord, path: string): unknown {
  return path.split('.').reduce<unknown>((current, key) => {
    if (Array.isArray(current) && /^\d+$/.test(key)) return current[Number(key)]
    if (current && typeof current === 'object') return (current as ApiRecord)[key]
    return undefined
  }, record)
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.map((item) => displayValue(item)).join(', ') || '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export type RequiredSkillSummary = { name: string; weight: number | null }

export function formatRequiredSkills(value: unknown): RequiredSkillSummary[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((skill) => {
    if (typeof skill === 'string') return [{ name: skill, weight: null }]
    if (!skill || typeof skill !== 'object') return []
    const record = skill as ApiRecord
    const name = typeof record.name === 'string' ? record.name.trim() : ''
    if (!name) return []
    const weight = typeof record.weight === 'number' ? record.weight : Number(record.weight)
    return [{ name, weight: Number.isFinite(weight) ? weight : null }]
  })
}

export function formatRoleWeight(value: unknown) {
  const weight = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(weight) ? `${Math.round(weight * 100)}%` : '—'
}

export type CandidateSummary = {
  id: string
  status: string
  name: string
  email: string
  headline: string
  summary: string
  totalExperienceMonths: number
  totalExperience: string
  skills: string[]
  experience: { title: string; company: string; period: string; highlights: string[] }[]
  education: { institution: string; degree: string; period: string }[]
  projects: { name: string; tech: string[]; highlights: string[] }[]
  certifications: { name: string; issuer: string; score: string }[]
  interests: string[]
  matches: { role: string; score: string; scoreValue: number; matchedSkills: string[]; missingSkills: string[]; details: string }[]
  emailHistory: { jobId: string; action: string; label: string; roleId: string; taskId: string; sentAt: string; status: string; dryRun: boolean }[]
  bestMatch: { role: string; score: string; scoreValue: number; matchedSkills: string[]; missingSkills: string[] } | null
  received: string
  file: string
  urls: string[]
}

function recordValue(value: unknown): ApiRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as ApiRecord : {}
}

function asStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return value === undefined || value === null || value === '' ? [] : [displayValue(value)]
  return value.flatMap((item) => {
    if (typeof item === 'string' || typeof item === 'number') return [String(item)]
    const group = recordValue(item)
    const list = group.items ?? group.skills ?? group.tech
    if (Array.isArray(list)) return list.map(displayValue)
    if (group.name || group.title) return [String(group.name ?? group.title)]
    return [displayValue(item)]
  }).filter((item) => item !== '—')
}

function text(record: ApiRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = getPath(record, key)
    if (value !== undefined && value !== null && value !== '') return displayValue(value)
  }
  return ''
}

function entries(value: unknown) {
  return Array.isArray(value) ? value.map(recordValue) : []
}

function monthIndex(value: unknown, now: Date) {
  if (typeof value !== 'string' || !value) return null
  const match = value.match(/^(\d{4})-(\d{1,2})/)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  if (month < 1 || month > 12) return null
  return year * 12 + month - 1
}

export function calculateExperienceMonths(experience: ApiRecord[], now = new Date()) {
  const currentMonth = now.getFullYear() * 12 + now.getMonth()
  const periods = experience.flatMap((item) => {
    const start = monthIndex(item.start, now)
    const end = item.end && item.end !== 'present' ? monthIndex(item.end, now) : currentMonth
    return start !== null && end !== null && end >= start ? [[start, end + 1] as const] : []
  }).sort((left, right) => left[0] - right[0])
  let total = 0
  let rangeStart: number | null = null
  let rangeEnd: number | null = null
  for (const [start, end] of periods) {
    if (rangeStart === null || rangeEnd === null) {
      rangeStart = start
      rangeEnd = end
    } else if (start <= rangeEnd) {
      rangeEnd = Math.max(rangeEnd, end)
    } else {
      total += rangeEnd - rangeStart
      rangeStart = start
      rangeEnd = end
    }
  }
  if (rangeStart !== null && rangeEnd !== null) total += rangeEnd - rangeStart
  return total
}

export function formatExperienceDuration(months: number) {
  const years = Math.floor(months / 12)
  const remainingMonths = months % 12
  if (years && remainingMonths) return `${years} yr ${remainingMonths} mo`
  if (years) return `${years} ${years === 1 ? 'yr' : 'yrs'}`
  return `${remainingMonths} mo`
}

export function formatCandidate(record: ApiRecord): CandidateSummary {
  const resume = recordValue(record.resume)
  const contact = recordValue(record.contact)
  const email = recordValue(record.email)
  const experience = entries(resume.experience ?? record.experience)
  const education = entries(resume.education ?? record.education)
  const projects = entries(resume.projects ?? record.projects)
  const certifications = entries(resume.certifications ?? record.certifications)
  const rawMatches = record.match ?? record.matches ?? record.scores ?? {}
  const formatScore = (value: unknown) => {
    const scoreValue = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(scoreValue) ? `${scoreValue.toFixed(1).replace(/\.0$/, '')}%` : ''
  }
  const matchData = (role: string, item: ApiRecord, fallbackScore: unknown): CandidateSummary['matches'][number] => {
    const rawScore = item.score ?? item.total_score ?? item.match_score ?? fallbackScore
    const scoreValue = typeof rawScore === 'number' ? rawScore : Number(rawScore)
    return {
      role,
      score: formatScore(rawScore),
      scoreValue: Number.isFinite(scoreValue) ? scoreValue : -1,
      matchedSkills: asStrings(item.matched_skills),
      missingSkills: asStrings(item.missing_skills),
      details: displayValue(item),
    }
  }
  const matches = Array.isArray(rawMatches)
    ? rawMatches.map((match, index) => {
      const item = recordValue(match)
      return matchData(text(item, 'role_id', 'role', 'title') || `Role ${index + 1}`, item, undefined)
    })
    : Object.entries(recordValue(rawMatches)).map(([role, value]) => {
      const item = recordValue(value)
      return matchData(role, item, typeof value === 'number' ? value : undefined)
    })
  const emailActionLabels: Record<string, string> = {
    interview: 'Interview', task_assigned: 'Task assigned', rejected: 'Rejected', hired: 'Hired', custom: 'Custom',
  }
  const emailHistory = entries(record.email_history).map((item) => {
    const action = text(item, 'action')
    return {
      jobId: text(item, 'job_id'),
      action,
      label: emailActionLabels[action] ?? (action || 'Email'),
      roleId: text(item, 'role_id'),
      taskId: text(item, 'task_id'),
      sentAt: text(item, 'sent_at'),
      status: text(item, 'status') || 'unknown',
      dryRun: item.dry_run === true,
    }
  }).sort((left, right) => Date.parse(left.sentAt) - Date.parse(right.sentAt))
  const scoredMatches = matches.filter((match) => match.scoreValue >= 0).sort((left, right) => right.scoreValue - left.scoreValue)
  const bestMatch = scoredMatches[0] ?? null
  const skills = asStrings(resume.skills ?? record.skills)
  const urls = [...asStrings(contact.urls), ...asStrings(contact.links)]
  const experienceMonths = calculateExperienceMonths(experience)

  return {
    id: text(record, '_id', 'id') || text(resume, '_id', 'id'),
    status: text(record, 'status'),
    name: text(resume, 'name') || text(record, 'name', 'candidate_name', 'full_name') || 'Unnamed candidate',
    email: text(email, 'sender') || asStrings(contact.emails)[0] || text(record, 'sender', 'email_address'),
    headline: text(record, 'headline', 'title', 'current_title', 'subject') || text(experience[0] ?? {}, 'title', 'role'),
    summary: text(resume, 'summary') || text(record, 'summary'),
    totalExperienceMonths: experienceMonths,
    totalExperience: experienceMonths ? formatExperienceDuration(experienceMonths) : '',
    skills,
    experience: experience.map((item) => ({
      title: text(item, 'title', 'role'), company: [text(item, 'company', 'organization'), text(item, 'location')].filter(Boolean).join(' · '),
      period: [text(item, 'start'), text(item, 'end')].filter(Boolean).join(' – '), highlights: asStrings(item.highlights),
    })),
    education: education.map((item) => ({
      institution: text(item, 'institution', 'school'), degree: [text(item, 'degree'), text(item, 'major')].filter(Boolean).join(' · '),
      period: [text(item, 'start'), text(item, 'end')].filter(Boolean).join(' – '),
    })),
    projects: projects.map((item) => ({ name: text(item, 'name'), tech: asStrings(item.tech), highlights: asStrings(item.highlights) })),
    certifications: certifications.map((item) => ({ name: text(item, 'name'), issuer: text(item, 'issuer'), score: text(item, 'score') })),
    interests: asStrings(resume.interests ?? record.interests),
    matches,
    emailHistory,
    bestMatch,
    received: text(email, 'date') || text(record, 'date', 'created_at', 'received_at'),
    file: text(record, 'resume_file'),
    urls,
  }
}

export function normalizePage(result: unknown, page: number, size: number) {
  if (Array.isArray(result)) return { items: result as ApiRecord[], total: result.length }
  const data = result && typeof result === 'object' ? result as Record<string, unknown> : {}
  const nested = data.data && typeof data.data === 'object' && !Array.isArray(data.data)
    ? data.data as Record<string, unknown>
    : {}
  const collection = ['items', 'results', 'records', 'list', 'resumes', 'roles', 'job_roles', 'tasks', 'submissions', 'jobs', 'users', 'permissions', 'audit', 'entries']
  let rows: unknown = data.items ?? data.results ?? data.records ?? data.list ?? nested.items ?? nested.results ?? data.data
  if (!Array.isArray(rows)) rows = collection.map((key) => data[key] ?? nested[key]).find(Array.isArray) ?? []
  const meta = data.meta && typeof data.meta === 'object' ? data.meta as Record<string, unknown> : {}
  const pagination = data.pagination && typeof data.pagination === 'object' ? data.pagination as Record<string, unknown> : {}
  if (!Array.isArray(rows) && !Object.keys(data).some((key) => collection.includes(key)) && Object.values(data).every((value) => value && typeof value === 'object')) {
    rows = Object.values(data)
  }
  const total = Number(data.total ?? data.count ?? data.total_items ?? nested.total ?? nested.count ?? meta.total ?? pagination.total ?? (Array.isArray(rows) ? rows.length : 0))
  if (Array.isArray(rows)) return { items: rows as ApiRecord[], total }
  if (Array.isArray(data.results)) return { items: data.results as ApiRecord[], total }
  return { items: [], total: total || page * size }
}