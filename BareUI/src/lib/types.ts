export type ApiRecord = Record<string, unknown>

export type PageResult = {
  items: ApiRecord[]
  total: number
  page: number
  size: number
}

export type FieldColumn = {
  label: string
  path: string
  alternatives?: string[]
}

export type ResourceDefinition = {
  id: string
  label: string
  endpoint: string
  noun: string
  columns: FieldColumn[]
  filters?: { name: string; label: string; type?: string; options?: string[] }[]
  create?: 'role' | 'task' | 'user' | 'resume' | 'submission'
}