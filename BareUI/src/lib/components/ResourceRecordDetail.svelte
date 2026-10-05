<script lang="ts">
  import { X } from '@lucide/svelte'
  import type { ApiRecord } from '../types'
  import { displayValue } from '../format'

  let { record, title, onClose }: { record: ApiRecord; title: string; onClose: () => void } = $props()
</script>

<div class="modal-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) onClose() }}>
  <dialog open class="modal detail-modal" aria-labelledby="detail-title">
    <div class="modal-head"><h2 id="detail-title">{title} details</h2><button class="icon-button" onclick={onClose} aria-label="Close"><X size={16} /></button></div>
    <div class="detail-content">
      {#each Object.entries(record) as [key, value] (key)}
        <div class="detail-field"><div class="detail-label">{key.replaceAll('_', ' ')}</div><pre>{typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : displayValue(value)}</pre></div>
      {/each}
    </div>
  </dialog>
</div>