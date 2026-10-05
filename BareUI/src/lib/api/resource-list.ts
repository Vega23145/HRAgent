import { queryString, request } from '../api'
import { normalizePage } from '../format'
import type { ResourceDefinition } from '../types'

export type ResourceQuery = {
  page: number
  size: number
  filters: Record<string, string>
}

function queryValues({ page, size, filters }: ResourceQuery) {
  const values: Record<string, string | number | boolean | undefined> = { page, size }
  for (const [key, value] of Object.entries(filters)) {
    if (!value) continue
    if (['is_open', 'is_active', 'has_match'].includes(key)) values[key] = value === 'true'
    else if (key === 'min_score') values[key] = Number(value)
    else values[key] = value
  }
  return values
}

export async function fetchResourcePage(resource: ResourceDefinition, query: ResourceQuery) {
  const candidateId = (query.filters.candidate_id ?? '').trim()
  if (resource.id === 'submissions' && !candidateId) return { items: [], total: 0 }

  const endpoint = resource.id === 'submissions'
    ? `${resource.endpoint}/${encodeURIComponent(candidateId)}/submissions`
    : resource.endpoint
  const response = await request<unknown>(`${endpoint}${queryString(queryValues(query))}`)
  return normalizePage(response, query.page, query.size)
}