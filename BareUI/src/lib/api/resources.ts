import { request } from '../api'
import type { ApiRecord, ResourceDefinition } from '../types'

const detailRoutes: Record<string, (id: string) => string> = {
  resumes: (id) => `/api/v1/resumes/${id}`,
  roles: (id) => `/api/v1/job-roles/${id}`,
  tasks: (id) => `/api/v1/task-review/tasks/${id}`,
  users: (id) => `/api/v1/users/${id}`,
  'access-roles': (id) => `/api/v1/access-roles/${id}`,
  'email-jobs': (id) => `/api/v1/email-agent/jobs/${id}`,
  audit: (id) => `/api/v1/admin/audit/${id}`,
  submissions: (id) => `/api/v1/task-review/submissions/${id}`,
}

function unwrapRecord(value: unknown): ApiRecord {
  let current = value
  const wrappers = ['data', 'item', 'result']
  for (let depth = 0; depth < 4 && current && typeof current === 'object' && !Array.isArray(current); depth += 1) {
    const record = current as ApiRecord
    const wrapper = wrappers.find((key) => record[key] && typeof record[key] === 'object' && !Array.isArray(record[key]))
    if (!wrapper) break
    current = record[wrapper]
  }
  return current && typeof current === 'object' && !Array.isArray(current) ? current as ApiRecord : {}
}

export async function fetchResourceDetail(resource: ResourceDefinition, record: ApiRecord) {
  const identifier = String(record._id ?? record.id ?? record.name ?? '')
  const route = detailRoutes[resource.id]
  if (!identifier || !route) return record
  const encodedIdentifier = encodeURIComponent(identifier)
  return unwrapRecord(await request<unknown>(route(encodedIdentifier)))
}