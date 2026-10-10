<script lang="ts">
  import { Plus, Trash2 } from '@lucide/svelte'
  import type { ApiRecord } from '../types'
  import { resumeEntryFields, type ResumeEntrySection } from '../forms/resumeEntries'

  let { section, label, initialEntries = [] }: {
    section: ResumeEntrySection
    label: string
    initialEntries?: ApiRecord[]
  } = $props()

  let entries = $state<ApiRecord[]>([])
  const fields = $derived(resumeEntryFields[section])

  $effect(() => {
    entries = initialEntries.map((entry, sourceIndex) => ({ ...entry, __sourceIndex: sourceIndex }))
  })

  function fieldValue(entry: ApiRecord, name: string) {
    const value = entry[name]
    return Array.isArray(value) ? value.map(String).join('\n') : value == null ? '' : String(value)
  }
</script>

<section class="resume-entry-section" aria-label={label}>
  <div class="resume-entry-heading">
    <h3>{label}</h3>
    <button class="button resume-entry-add" type="button" onclick={() => entries = [...entries, { __sourceIndex: -1 }]}>
      <Plus size={14} /> Add {section === 'experience' ? 'role' : section === 'education' ? 'school' : section === 'projects' ? 'project' : 'certification'}
    </button>
  </div>
  {#if entries.length === 0}<p class="resume-entry-empty">No entries added.</p>{/if}
  {#each entries as entry, index (index)}
    <fieldset class="resume-entry-item">
      <legend>{label} {index + 1}</legend>
      <input type="hidden" name={`${section}_${index}_source_index`} value={entry.__sourceIndex ?? -1} />
      <button class="icon-button resume-entry-remove" type="button" onclick={() => entries = entries.filter((_, itemIndex) => itemIndex !== index)} title="Remove entry" aria-label={`Remove ${label.toLowerCase()} ${index + 1}`}>
        <Trash2 size={14} />
      </button>
      <div class="resume-entry-fields">
        {#each fields as field}
          {@const id = `resume-${section}-${index}-${field.name}`}
          <div class="field" class:resume-entry-wide={field.multiline}>
            <label for={id}>{field.label}</label>
            {#if field.multiline}
              <textarea class="textarea" {id} name={`${section}_${index}_${field.name}`}>{fieldValue(entry, field.name)}</textarea>
            {:else}
              <input class="input" {id} name={`${section}_${index}_${field.name}`} value={fieldValue(entry, field.name)} />
            {/if}
          </div>
        {/each}
      </div>
    </fieldset>
  {/each}
</section>

<style>
  .resume-entry-section { display: grid; gap: 10px; }
  .resume-entry-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .resume-entry-heading h3 { margin: 0; font-size: 14px; font-weight: 650; }
  .resume-entry-add { white-space: nowrap; }
  .resume-entry-empty { margin: 0; color: var(--muted, #68746c); font-size: 13px; }
  .resume-entry-item { position: relative; min-width: 0; margin: 0; padding: 14px; border: 1px solid var(--line, #dce2dd); border-radius: 6px; }
  .resume-entry-item legend { padding: 0 5px; color: var(--muted, #68746c); font-size: 12px; }
  .resume-entry-remove { position: absolute; top: 4px; right: 8px; }
  .resume-entry-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; }
  .resume-entry-wide { grid-column: 1 / -1; }
  @media (max-width: 600px) {
    .resume-entry-heading { align-items: flex-start; flex-direction: column; }
    .resume-entry-fields { grid-template-columns: minmax(0, 1fr); }
    .resume-entry-wide { grid-column: auto; }
  }
</style>