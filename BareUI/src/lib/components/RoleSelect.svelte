<script lang="ts">
  import { onMount } from 'svelte'
  import { ChevronDown } from '@lucide/svelte'
  import { request } from '../api'
  import { displayValue, formatRequiredSkills } from '../format'
  import type { ApiRecord } from '../types'

  let {
    id,
    name = 'role_id',
    label = 'Role',
    value = '',
    required = false,
    disabled = false,
    includeBlank = false,
    blankLabel = 'Select a role',
    onChange,
  }: {
    id: string
    name?: string
    label?: string
    value?: string
    required?: boolean
    disabled?: boolean
    includeBlank?: boolean
    blankLabel?: string
    onChange?: (value: string) => void
  } = $props()

  let roles = $state<ApiRecord[]>([])
  let loading = $state(true)
  let error = $state('')
  let focusedRole = $state('')

  onMount(async () => {
    try {
      const response = await request<unknown>('/api/v1/job-roles?page=1&size=100')
      const data = response && typeof response === 'object' ? response as ApiRecord : {}
      const rows = Array.isArray(response) ? response : data.items ?? data.results ?? data.roles ?? []
      roles = Array.isArray(rows) ? rows as ApiRecord[] : []
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Unable to load roles.'
    } finally {
      loading = false
    }
  })

  function roleId(role: ApiRecord) {
    return String(role._id ?? role.id ?? '')
  }

  function roleTitle(role: ApiRecord) {
    return String(role.title ?? role.name ?? roleId(role))
  }

  function skillNames(role: ApiRecord) {
    return formatRequiredSkills(role.required_skills).map((skill) => skill.name)
  }

  function update(value: string) {
    onChange?.(value)
  }
</script>

<div class="field role-select-field">
  <label for={id}>{label}</label>
  <div class="role-select-wrap">
    <select class="select role-select" {id} {name} {required} {disabled} {value} onfocus={(event) => focusedRole = event.currentTarget.value} onblur={() => focusedRole = ''} onmouseenter={(event) => focusedRole = event.currentTarget.value} onmouseleave={() => focusedRole = ''} onchange={(event) => { update(event.currentTarget.value); focusedRole = event.currentTarget.value }}>
      {#if includeBlank}<option value="">{blankLabel}</option>{/if}
      {#if loading}<option value="" disabled>Loading roles…</option>{/if}
      {#each roles as role (roleId(role))}<option value={roleId(role)}>{roleTitle(role)} · {roleId(role)}</option>{/each}
      {#if !loading && value && !roles.some((role) => roleId(role) === value)}<option value={value}>{value}</option>{/if}
    </select>
    <ChevronDown class="role-select-chevron" size={15} />
  </div>
  {#if focusedRole}
    {@const selected = roles.find((role) => roleId(role) === focusedRole)}
    {#if selected}
      <div class="role-skills-tooltip" role="tooltip">
        <strong>{roleTitle(selected)}</strong>
        {#if skillNames(selected).length}<span>Required skills: {skillNames(selected).join(', ')}</span>{:else}<span>No required skills listed</span>{/if}
      </div>
    {/if}
  {/if}
  {#if error}<small class="role-select-error">{displayValue(error)}</small>{/if}
</div>