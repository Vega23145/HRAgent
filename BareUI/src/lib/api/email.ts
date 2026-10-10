import { request } from '../api'
import type { ApiRecord } from '../types'

export type EmailPageParams = {
  page?: number
  size?: number
  status?: string
  action?: string
}

function emailQuery(params: EmailPageParams) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return query.size ? `?${query.toString()}` : ''
}

export function sendSingleEmail(payload: ApiRecord) {
  return request<unknown>('/api/v1/email-agent/send', { method: 'POST', body: JSON.stringify(payload) })
}

export function sendBulkEmail(payload: ApiRecord) {
  return request<unknown>('/api/v1/email-agent/bulk', { method: 'POST', body: JSON.stringify(payload) })
}

export function fetchEmailJobs(params: EmailPageParams = {}) {
  return request<unknown>(`/api/v1/email-agent/jobs${emailQuery(params)}`)
}

export function fetchEmailJob(jobId: string) {
  return request<ApiRecord>(`/api/v1/email-agent/jobs/${encodeURIComponent(jobId)}`)
}

export function deleteEmailJob(jobId: string) {
  return request<void>(`/api/v1/email-agent/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' })
}

export function fetchEmailJobLog(jobId: string, params: EmailPageParams = {}) {
  return request<unknown>(`/api/v1/email-agent/jobs/${encodeURIComponent(jobId)}/log${emailQuery(params)}`)
}

export function fetchEmailTemplates() {
  return request<unknown>('/api/v1/email-agent/templates')
}

export function previewEmailTemplate(action: string) {
  return request<ApiRecord>(`/api/v1/email-agent/templates/${encodeURIComponent(action)}/preview`)
}