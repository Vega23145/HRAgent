<script lang="ts">
  import {
    ArrowLeft,
    ArrowRight,
    BriefcaseBusiness,
    Copy,
    Edit3,
    Eye,
    Search,
    Trash2,
  } from "@lucide/svelte";
  import type { ApiRecord, ResourceDefinition } from "../types";
  import { formatCandidate } from "../format";

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
    onEdit,
    onPreview,
    onDiscard,
  }: {
    resource: ResourceDefinition;
    items: ApiRecord[];
    page: number;
    size: number;
    total: number;
    filters: Record<string, string>;
    loading?: boolean;
    onFilter: (name: string, value: string) => void;
    onPage: (page: number) => void;
    onSize: (size: number) => void;
    onEdit: (record: ApiRecord) => void;
    onPreview: (record: ApiRecord) => void;
    onDiscard: (record: ApiRecord) => void;
  } = $props();

  const pageCount = $derived(Math.max(1, Math.ceil(total / size)));
  let copiedId = $state("");
  let copyError = $state("");

  async function copyId(id: string) {
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
      copiedId = id;
      copyError = "";
      setTimeout(() => {
        if (copiedId === id) copiedId = "";
      }, 1400);
    } catch {
      copyError = "Clipboard access is unavailable in this browser.";
    }
  }
</script>

<section class="panel candidate-panel">
  <div class="panel-head">
    <div>
      <div class="panel-title">Candidates</div>
      <div class="panel-subtitle">{total.toLocaleString()} resumes</div>
    </div>
    <div class="filters">
      <label class="searchbox"
        ><Search size={15} /><input
          class="input"
          placeholder="Search candidates…"
          aria-label="Search candidates"
          value={filters.q ?? ""}
          oninput={(event) => onFilter("q", event.currentTarget.value)}
        /></label
      >
      {#each resource.filters ?? [] as filter (filter.name)}
        {#if filter.type === "select"}
          <select
            class="select extra-filter"
            aria-label={filter.label}
            value={filters[filter.name] ?? ""}
            onchange={(event) =>
              onFilter(filter.name, event.currentTarget.value)}
          >
            <option value="">{filter.label}</option>
            {#each filter.options ?? [] as option}<option value={option}
                >{option}</option
              >{/each}
          </select>
        {:else}
          <input
            class="input extra-filter"
            type={filter.type ?? "search"}
            placeholder={filter.label}
            aria-label={filter.label}
            value={filters[filter.name] ?? ""}
            oninput={(event) =>
              onFilter(filter.name, event.currentTarget.value)}
          />
        {/if}
      {/each}
    </div>
  </div>
  {#if loading}<div class="loading">Loading candidates…</div>
  {:else if items.length === 0}<div class="empty">No candidates found.</div>
  {:else}<div class="candidate-list">
      {#each items as record, index (String(record._id ?? record.id ?? `${page}-${index}`))}
        {@const candidate = formatCandidate(record)}
        <article class="candidate-row">
          <div class="candidate-identity">
            <div class="candidate-id-line">
              <span class="candidate-id-label">RESUME ID</span><code
                >{candidate.id || "ID unavailable"}</code
              ><button
                class="copy-id"
                onclick={() => void copyId(candidate.id)}
                disabled={!candidate.id}
                title="Copy resume ID"
                aria-label="Copy resume ID"
                ><Copy size={13} />{copiedId === candidate.id
                  ? "Copied"
                  : "Copy ID"}</button
              >
            </div>
            {#if copyError}<span class="copy-error">{copyError}</span>{/if}
            <div class="candidate-name">{candidate.name}</div>
            {#if candidate.status}<span
                class="badge"
                class:bad={candidate.status.toLowerCase() === "rejected"}
                >{candidate.status}</span
              >{/if}
            {#if candidate.headline}<div class="candidate-headline">
                {candidate.headline}
              </div>{/if}
            <div class="candidate-contact">
              {candidate.email ||
                "No email on record"}{#if candidate.received}<span
                  >Added {candidate.received}</span
                >{/if}{#if candidate.emailHistory.length}<span
                  >Last email · {candidate.emailHistory.at(-1)?.label}</span
                >{/if}
            </div>
          </div>
          <div class="candidate-summary-cell">
            <div class="candidate-cell-label">TOTAL EXPERIENCE</div>
            {#if candidate.totalExperience}<strong class="experience-total"
                >{candidate.totalExperience}</strong
              >{/if}
            {#if candidate.experience.length}
              <span
                >{candidate.experience[0].title ||
                  "Experience"}{#if candidate.experience[0].company}
                  · {candidate.experience[0].company}{/if}</span
              >
            {:else}<span class="candidate-muted">No experience listed</span
              >{/if}
          </div>
          <div class="candidate-skills-cell">
            <div class="candidate-cell-label">TOP SKILLS</div>
            {#if candidate.skills.length}<div class="skill-chips">
                {#each candidate.skills.slice(0, 5) as skill (skill)}<span
                    >{skill}</span
                  >{/each}{#if candidate.skills.length > 5}<small
                    >+{candidate.skills.length - 5}</small
                  >{/if}
              </div>
            {:else}<span class="candidate-muted">No skills listed</span>{/if}
          </div>
          <div class="candidate-match-cell">
            <div class="candidate-cell-label">TOP ROLE MATCH</div>
            {#if candidate.bestMatch}
              <div class="candidate-match best-match">
                <BriefcaseBusiness size={13} /><span
                  >{candidate.bestMatch.role}</span
                ><strong>{candidate.bestMatch.score}</strong>
              </div>
              {#if candidate.bestMatch.matchedSkills.length}<div
                  class="matched-skill-label"
                >
                  Matched skills
                </div>
                <div class="matched-skills">
                  {candidate.bestMatch.matchedSkills
                    .slice(0, 4)
                    .join(
                      " · ",
                    )}{#if candidate.bestMatch.matchedSkills.length > 4}<span>
                      +{candidate.bestMatch.matchedSkills.length - 4}</span
                    >{/if}
                </div>{/if}
            {:else}<span class="candidate-muted">Not matched yet</span>{/if}
          </div>
          <div class="candidate-actions">
            <button
              class="icon-button"
              onclick={() => onEdit(record)}
              title="Edit candidate"
              aria-label="Edit candidate"><Edit3 size={15} /></button
            ><button
              class="icon-button preview-action"
              onclick={() => onPreview(record)}
              title="Preview candidate"
              aria-label="Preview candidate"><Eye size={15} /></button
            ><button
              class="icon-button discard-action"
              onclick={() => onDiscard(record)}
              title="Discard candidate"
              aria-label="Discard candidate"><Trash2 size={15} /></button
            >
          </div>
        </article>
      {/each}
    </div>{/if}
  <footer class="table-footer">
    <span
      >Showing {total ? (page - 1) * size + 1 : 0}–{Math.min(
        page * size,
        total,
      )} of {total}</span
    >
    <div class="pagination">
      <label for="candidate-page-size">Rows</label><select
        class="select"
        id="candidate-page-size"
        value={size}
        onchange={(event) => onSize(Number(event.currentTarget.value))}
        ><option value="10">10</option><option value="20">20</option><option
          value="50">50</option
        ><option value="100">100</option></select
      ><button
        onclick={() => onPage(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"><ArrowLeft size={14} /></button
      ><span>{page} / {pageCount}</span><button
        onclick={() => onPage(page + 1)}
        disabled={page >= pageCount}
        aria-label="Next page"><ArrowRight size={14} /></button
      >
    </div>
  </footer>
</section>
