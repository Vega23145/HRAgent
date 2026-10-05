import { request } from '../api'
import type { ApiRecord } from '../types'

export function previewEmailTemplate(action: string) {
  return request<ApiRecord>(`/api/v1/email-agent/templates/${encodeURIComponent(action)}/preview`)
}