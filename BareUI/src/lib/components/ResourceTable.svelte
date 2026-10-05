<script lang="ts">
  import { ArrowLeft, ArrowRight, Search, ScanEye, Eye } from '@lucide/svelte'
  import type { ApiRecord, ResourceDefinition } from '../types'
  import { displayValue, getPath } from '../format'

  let {
    resource,
    items,
    page,
    size,
    total,
    filters,
    loading = false,
    onFilter,
    onPage,
    onSize,
    onSelect,
    onPreview,
  }: {
    resource: ResourceDefinition
    items: ApiRecord[]
    page: number
    size: number
    total: number
    filters: Record<string, string>
    loading?: boolean
    onFilter: (name: string, value: string) => void
    onPage: (page: number) => void
    onSize: (size: number) => void
    onSelect: (record: ApiRecord) => void
    onPreview?: (record: ApiRecord) => void
  } = $props()

  const pageCount = $derived(Math.max(1, Math.ceil(total / size)))
</script>

<section class="panel">
  <div class="panel-head">
    <div><div class="panel-title">{resource.label}</div><div class="panel-subtitle">{total.toLocaleString()} records</div></div>
    <div class="filters">
      <label class="searchbox"><Search size={15} /><input class="input" placeholder={`Search ${resource.label.toLowerCase()}…`} aria-label={`Search ${resource.label}`} value={filters.q ?? ''} oninput={(event) => onFilter('q', event.currentTarget.value)} /></label>
      {#each resource.filters ?? [] as filter (filter.name)}
        {#if filter.type === 'select'}
          <select class="select extra-filter" aria-label={filter.label} value={filters[filter.name] ?? ''} onchange={(event) => onFilter(filter.name, event.currentTarget.value)}>
            <option value="">{filter.label}</option>
            {#each filter.options ?? [] as option}<option value={option}>{option}</option>{/each}
          </select>
        {:else}
          <input class="input extra-filter" type={filter.type ?? 'search'} placeholder={filter.label} aria-label={filter.label} value={filters[filter.name] ?? ''} oninput={(event) => onFilter(filter.name, event.currentTarget.value)} />
        {/if}
      {/each}
    </div>
  </div>
  {#if loading}<div class="loading">Loading {resource.label.toLowerCase()}…</div>
  {:else if items.length === 0}<div class="empty">No {resource.label.toLowerCase()} found.</div>
  {:else}<div class="table-wrap"><table><thead><tr>{#each resource.columns as column (column.path)}<th>{column.label}</th>{/each}<th>Inspect</th>{#if onPreview}<th>Preview</th>{/if}</tr></thead><tbody>
    {#each items as record, index (String(record._id ?? record.id ?? `${page}-${index}`))}
      <tr>{#each resource.columns as column (column.path)}{@const raw = [column.path, ...(column.alternatives ?? [])].map((path) => getPath(record, path)).find((value) => value !== undefined && value !== null && value !== '')}<td><span class="cell-value" title={displayValue(raw)}>{displayValue(raw)}</span></td>{/each}<td><button class="icon-button" onclick={() => onSelect(record)} aria-label={`Inspect ${resource.noun}`} title="Inspect full record"><ScanEye size={15} /></button></td>{#if onPreview}<td><button class="icon-button" onclick={() => onPreview?.(record)} aria-label="Preview email template" title="Preview template"><Eye size={15} /></button></td>{/if}</tr>
    {/each}
  </tbody></table></div>{/if}
  <footer class="table-footer"><span>Showing {total ? (page - 1) * size + 1 : 0}–{Math.min(page * size, total)} of {total}</span><div class="pagination"><label for="page-size">Rows</label><select class="select" id="page-size" value={size} onchange={(event) => onSize(Number(event.currentTarget.value))}><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option></select><button onclick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page"><ArrowLeft size={14} /></button><span>{page} / {pageCount}</span><button onclick={() => onPage(page + 1)} disabled={page >= pageCount} aria-label="Next page"><ArrowRight size={14} /></button></div></footer>
</section>