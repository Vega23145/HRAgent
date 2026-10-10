<script lang="ts">
  import { onMount } from "svelte";
  import {
    ArrowLeft,
    ArrowRight,
    Eye,
    GripVertical,
    Plus,
    RefreshCw,
    Search,
    Send,
    Trash2,
    X,
  } from "@lucide/svelte";
  import {
    deleteEmailJob,
    fetchEmailJob,
    fetchEmailJobLog,
    fetchEmailJobs,
    fetchEmailTemplates,
    previewEmailTemplate,
    sendBulkEmail,
    sendSingleEmail,
  } from "../api/email";
  import { request } from "../api";
  import { displayValue } from "../format";
  import type { ApiRecord } from "../types";
  import RoleSelect from "./RoleSelect.svelte";

  import { ApiError } from "../api";

  let { onError }: { onError: (error: string, status?: number) => void } =
    $props();
  type Tab = "Compose" | "Jobs" | "Templates";
  type Mode = "Single" | "Bulk";

  let tab = $state<Tab>("Compose");
  let mode = $state<Mode>("Single");
  let action = $state("interview");
  let candidateId = $state("");
  let roleId = $state("");
  let taskId = $state("");
  let minScore = $state("");
  let maxScore = $state("");
  let subject = $state("");
  let body = $state("");
  let candidateSearch = $state("");
  let candidates = $state<ApiRecord[]>([]);
  let tasks = $state<ApiRecord[]>([]);
  let selectedCandidateIds = $state<string[]>([]);
  let dragCandidateId = $state("");
  let candidateDropActive = $state(false);
  let response = $state<unknown>(null);
  let templates = $state<ApiRecord[]>([]);
  let jobs = $state<ApiRecord[]>([]);
  let selectedJob = $state<ApiRecord | null>(null);
  let jobLog = $state<ApiRecord[]>([]);
  let templatePreview = $state<ApiRecord | null>(null);
  let logStatus = $state("");
  let statusFilter = $state("");
  let actionFilter = $state("");
  let jobPage = $state(1);
  let logPage = $state(1);
  let pageSize = $state(20);
  let jobTotal = $state(0);
  let logTotal = $state(0);
  let busy = $state(false);
  let loading = $state(false);

  const jobPages = $derived(Math.max(1, Math.ceil(jobTotal / pageSize)));
  const logPages = $derived(Math.max(1, Math.ceil(logTotal / pageSize)));

  onMount(() => {
    void loadTemplates();
    void loadJobs();
    void loadComposeOptions();
  });

  function record(value: unknown): ApiRecord {
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as ApiRecord)
      : {};
  }

  function rows(value: unknown): ApiRecord[] {
    if (Array.isArray(value)) return value.map(record);
    const root = record(value);
    const nested = record(root.data ?? root.result);
    const list =
      root.items ??
      root.results ??
      root.logs ??
      root.templates ??
      root.data ??
      nested.items ??
      nested.results ??
      nested.logs ??
      nested.templates;
    return Array.isArray(list) ? list.map(record) : [];
  }

  function total(value: unknown, count: number) {
    const root = record(value);
    const nested = record(root.pagination ?? root.meta);
    const amount = root.total ?? root.count ?? nested.total ?? nested.count;
    return typeof amount === "number" ? amount : count;
  }

  function idOf(job: ApiRecord) {
    return String(job.job_id ?? job._id ?? job.id ?? "");
  }

  function candidateIdOf(candidate: ApiRecord) {
    const resume = record(candidate.resume);
    return String(
      candidate._id ??
        candidate.id ??
        candidate.candidate_id ??
        resume._id ??
        resume.id ??
        "",
    );
  }

  function candidateName(candidate: ApiRecord) {
    const resume = record(candidate.resume);
    return String(
      resume.name ??
        candidate.name ??
        candidate.candidate_name ??
        candidate.full_name ??
        candidate.email?.toString() ??
        candidateIdOf(candidate),
    );
  }

  function taskIdOf(task: ApiRecord) {
    return String(task._id ?? task.id ?? task.task_id ?? "");
  }

  function taskLabel(task: ApiRecord) {
    return String(task.title ?? task.name ?? taskIdOf(task));
  }

  const availableCandidates = $derived(
    candidates.filter((candidate) => {
      const term = candidateSearch.trim().toLowerCase();
      const id = candidateIdOf(candidate);
      return (
        id &&
        !selectedCandidateIds.includes(id) &&
        (!term ||
          `${candidateName(candidate)} ${id}`.toLowerCase().includes(term))
      );
    }),
  );

  function addCandidate(id: string) {
    if (id && !selectedCandidateIds.includes(id))
      selectedCandidateIds = [...selectedCandidateIds, id];
  }

  function removeCandidate(id: string) {
    selectedCandidateIds = selectedCandidateIds.filter(
      (candidate) => candidate !== id,
    );
  }

  function onCandidateDrop(event: DragEvent) {
    event.preventDefault();
    candidateDropActive = false;
    const id = event.dataTransfer?.getData("text/plain") ?? dragCandidateId;
    addCandidate(id);
    dragCandidateId = "";
  }

  async function loadComposeOptions() {
    try {
      const [candidateData, taskData] = await Promise.all([
        request<unknown>("/api/v1/resumes?page=1&size=100"),
        request<unknown>("/api/v1/task-review/tasks?page=1&size=100"),
      ]);
      candidates = rows(candidateData);
      tasks = rows(taskData);
    } catch (cause) {
      reportError(cause);
    }
  }

  function errorMessage(cause: unknown) {
    return cause instanceof Error
      ? cause.message
      : "Email-agent request failed.";
  }

  function reportError(cause: unknown) {
    onError(
      errorMessage(cause),
      cause instanceof ApiError ? cause.status : undefined,
    );
  }

  async function loadTemplates() {
    loading = true;
    try {
      const data = await fetchEmailTemplates();
      templates = rows(data);
      if (!templates.length && Array.isArray(data))
        templates = data.map(record);
    } catch (cause) {
      reportError(cause);
    } finally {
      loading = false;
    }
  }

  async function loadJobs() {
    loading = true;
    try {
      const data = await fetchEmailJobs({
        page: jobPage,
        size: pageSize,
        status: statusFilter,
        action: actionFilter,
      });
      jobs = rows(data);
      jobTotal = total(data, jobs.length);
    } catch (cause) {
      reportError(cause);
      jobs = [];
      jobTotal = 0;
    } finally {
      loading = false;
    }
  }

  async function submit(modeToSend: Mode) {
    if (modeToSend === "Single" && !candidateId) {
      onError("Choose a candidate before sending.");
      return;
    }
    if (
      minScore !== "" &&
      maxScore !== "" &&
      Number(minScore) > Number(maxScore)
    ) {
      onError("Minimum score must be less than or equal to maximum score.");
      return;
    }
    const shared = {
      action,
      ...(roleId
        ? { role_id: roleId }
        : modeToSend === "Single"
          ? { role_id: "" }
          : {}),
      ...(taskId ? { task_id: taskId } : {}),
      subject: subject.trim() || null,
      body: body.trim() || null,
    };
    const payload: ApiRecord =
      modeToSend === "Single"
        ? { ...shared, candidate_id: candidateId }
        : {
            ...shared,
            ...(minScore !== "" ? { min_score: Number(minScore) } : {}),
            ...(maxScore !== "" ? { max_score: Number(maxScore) } : {}),
            ...(selectedCandidateIds.length
              ? { candidate_ids: selectedCandidateIds }
              : {}),
          };
    busy = true;
    response = null;
    onError("");
    try {
      response =
        modeToSend === "Single"
          ? await sendSingleEmail(payload)
          : await sendBulkEmail(payload);
      response ??= { accepted: true, status: 202 };
      tab = "Jobs";
      jobPage = 1;
      await loadJobs();
    } catch (cause) {
      reportError(cause);
    } finally {
      busy = false;
    }
  }

  async function inspectJob(job: ApiRecord) {
    const jobId = idOf(job);
    if (!jobId) return onError("This job has no ID to inspect.");
    loading = true;
    try {
      selectedJob = await fetchEmailJob(jobId);
      logPage = 1;
      await loadLog(jobId);
      onError("");
    } catch (cause) {
      reportError(cause);
    } finally {
      loading = false;
    }
  }

  async function loadLog(jobId = selectedJob ? idOf(selectedJob) : "") {
    if (!jobId) return;
    try {
      const data = await fetchEmailJobLog(jobId, {
        page: logPage,
        size: pageSize,
        status: logStatus,
      });
      jobLog = rows(data);
      logTotal = total(data, jobLog.length);
    } catch (cause) {
      reportError(cause);
      jobLog = [];
      logTotal = 0;
    }
  }

  async function removeJob(job: ApiRecord) {
    const jobId = idOf(job);
    if (!jobId || !window.confirm(`Delete email job ${jobId}?`)) return;
    busy = true;
    try {
      await deleteEmailJob(jobId);
      if (selectedJob && idOf(selectedJob) === jobId) {
        selectedJob = null;
        jobLog = [];
      }
      onError("");
      await loadJobs();
    } catch (cause) {
      reportError(cause);
    } finally {
      busy = false;
    }
  }

  async function showTemplatePreview(template: ApiRecord) {
    const action = String(template.action ?? template._id ?? "");
    if (!action)
      return onError("This template has no action identifier to preview.");
    try {
      templatePreview = await previewEmailTemplate(action);
      onError("");
    } catch (cause) {
      reportError(cause);
    }
  }

  function resetJobFilters() {
    statusFilter = "";
    actionFilter = "";
    jobPage = 1;
    void loadJobs();
  }
</script>

<div class="page-heading">
  <div>
    <p class="eyebrow">Messaging operations</p>
    <h1>Email agent</h1>
    <p class="subheading">
      Send messages, inspect delivery jobs, and preview templates.
    </p>
  </div>
  <button
    class="button"
    onclick={() => {
      if (tab === "Jobs") void loadJobs();
      else if (tab === "Templates") void loadTemplates();
    }}
    disabled={loading}
    aria-label="Refresh current data"><RefreshCw size={15} /> Refresh</button
  >
</div>
<div class="tab-strip" role="tablist" aria-label="Email agent tools">
  {#each ["Compose", "Jobs", "Templates"] as item}<button
      role="tab"
      aria-selected={tab === item}
      class:active={tab === item}
      onclick={() => {
        tab = item as Tab;
        if (item === "Jobs") void loadJobs();
        if (item === "Templates") void loadTemplates();
      }}>{item}</button
    >{/each}
</div>

{#if tab === "Compose"}
  <section class="panel email-compose">
    <div class="panel-head">
      <div>
        <div class="panel-title">Compose email</div>
        <div class="panel-subtitle">
          Choose a template action, recipient criteria, and optional message
          overrides.
        </div>
      </div>
    </div>
    <div class="form email-compose-form">
      <div class="segmented" role="tablist" aria-label="Send mode">
        {#each ["Single", "Bulk"] as item}<button
            class:active={mode === item}
            role="tab"
            aria-selected={mode === item}
            onclick={() => {
              mode = item as Mode;
              response = null;
            }}>{item} send</button
          >{/each}
      </div>
      <div class="email-field-grid">
        <label class="field"
          ><span>Action <b class="required-mark">Required</b></span><select
            class="select"
            bind:value={action}
            onchange={(event) => {
              action = event.currentTarget.value;
              subject = "";
              body = "";
            }}
            ><option value="interview">Interview</option><option
              value="task_assigned">Task assigned</option
            ><option value="rejected">Rejected</option><option value="hired"
              >Hired</option
            ><option value="custom">Custom</option></select
          ></label
        >
        {#if mode === "Single"}
          <label class="field"
            ><span>Candidate <b class="required-mark">Required</b></span><select
              class="select"
              bind:value={candidateId}
              ><option value="">Choose candidate</option
              >{#each candidates as candidate (candidateIdOf(candidate))}<option
                  value={candidateIdOf(candidate)}
                  >{candidateName(candidate)} · {candidateIdOf(
                    candidate,
                  )}</option
                >{/each}</select
            ></label
          >
        {:else}
          <RoleSelect
            id="bulk-email-role"
            label="Role filter"
            value={roleId}
            includeBlank
            blankLabel="All roles"
            onChange={(value) => (roleId = value)}
          />
          <label class="field"
            ><span>Task filter</span><select class="select" bind:value={taskId}
              ><option value="">All tasks</option
              >{#each tasks as task (taskIdOf(task))}<option
                  value={taskIdOf(task)}>{taskLabel(task)}</option
                >{/each}</select
            ></label
          >
        {/if}
        {#if mode === "Single"}
          <RoleSelect
            id="single-email-role"
            label="Role ID"
            value={roleId}
            includeBlank
            blankLabel="No role"
            onChange={(value) => (roleId = value)}
          />
          <label class="field"
            ><span>Task ID</span><select class="select" bind:value={taskId}
              ><option value="">No task</option
              >{#each tasks as task (taskIdOf(task))}<option
                  value={taskIdOf(task)}
                  >{taskLabel(task)} · {taskIdOf(task)}</option
                >{/each}</select
            ></label
          >
        {/if}
      </div>
      {#if mode === "Bulk"}
        <section
          class="bulk-recipient-picker"
          aria-label="Optional specific candidate selection"
        >
          <div class="bulk-picker-heading">
            <div>
              <strong>Specific candidates</strong>
              <p>
                Leave the selection empty to include everyone matching the
                filters. Drag candidates into Selected or use the add button.
              </p>
            </div>
            <span>{selectedCandidateIds.length} selected</span>
          </div>
          <div class="bulk-picker-grid">
            <div class="candidate-source">
              <label class="searchbox"
                ><Search size={15} /><input
                  class="input"
                  placeholder="Find candidates"
                  aria-label="Search candidates"
                  bind:value={candidateSearch}
                /></label
              >
              <div class="candidate-drag-list">
                {#each availableCandidates as candidate (candidateIdOf(candidate))}
                  {@const candidateKey = candidateIdOf(candidate)}
                  <div
                    class="candidate-drag-item"
                    role="listitem"
                    aria-label={`Draggable candidate ${candidateName(candidate)}`}
                    draggable="true"
                    ondragstart={(event) => {
                      dragCandidateId = candidateKey;
                      event.dataTransfer?.setData("text/plain", candidateKey);
                      if (event.dataTransfer)
                        event.dataTransfer.effectAllowed = "copy";
                    }}
                  >
                    <GripVertical size={14} /><span
                      ><strong>{candidateName(candidate)}</strong><small
                        >{candidateKey}</small
                      ></span
                    ><button
                      class="icon-button"
                      type="button"
                      onclick={() => addCandidate(candidateKey)}
                      aria-label={`Add ${candidateName(candidate)}`}
                      ><Plus size={14} /></button
                    >
                  </div>
                {:else}<div class="candidate-list-empty">
                    {candidates.length
                      ? "No matching candidates."
                      : "Candidate list unavailable."}
                  </div>{/each}
              </div>
            </div>
            <div
              class:drop-active={candidateDropActive}
              class="candidate-drop-zone"
              role="region"
              aria-label="Selected candidate drop zone"
              ondragover={(event) => {
                event.preventDefault();
                candidateDropActive = true;
              }}
              ondragleave={() => (candidateDropActive = false)}
              ondrop={onCandidateDrop}
            >
              <strong>Selected recipients</strong>
              {#if selectedCandidateIds.length}
                <div class="selected-candidate-list">
                  {#each selectedCandidateIds as selectedId (selectedId)}<div
                      class="selected-candidate"
                    >
                      <span
                        >{candidateName(
                          candidates.find(
                            (candidate) =>
                              candidateIdOf(candidate) === selectedId,
                          ) ?? { _id: selectedId },
                        )}</span
                      ><button
                        class="icon-button"
                        type="button"
                        onclick={() => removeCandidate(selectedId)}
                        aria-label={`Remove ${selectedId}`}
                        ><X size={13} /></button
                      >
                    </div>{/each}
                </div>
              {:else}<div class="drop-placeholder">
                  Drop candidates here, or leave empty to use all matching
                  candidates.
                </div>{/if}
            </div>
          </div>
        </section>
        <div class="email-field-grid bulk-score-filters">
          <label class="field"
            ><span>Minimum match score</span><input
              class="input"
              type="number"
              min="0"
              max="100"
              step="0.1"
              placeholder="0"
              bind:value={minScore}
            /></label
          >
          <label class="field"
            ><span>Maximum match score</span><input
              class="input"
              type="number"
              min="0"
              max="100"
              step="0.1"
              placeholder="100"
              bind:value={maxScore}
            /></label
          >
        </div>
      {/if}
      <div class="email-field-grid email-overrides">
        <label class="field"
          ><span>Subject override</span><input
            class="input"
            maxlength="500"
            placeholder="Use template subject"
            bind:value={subject}
          /></label
        >
        <label class="field email-body-field"
          ><span>Body override</span><textarea
            class="textarea"
            rows="5"
            placeholder="Use template body"
            bind:value={body}
          ></textarea></label
        >
      </div>
      <div class="email-compose-actions">
        <span class="field-hint"
          >Optional subject and body override the selected template. Requests
          are queued by the email agent.</span
        ><button
          class="button primary"
          onclick={() => submit(mode)}
          disabled={busy}
          ><Send size={14} />
          {busy ? "Submitting…" : `Send ${mode.toLowerCase()}`}</button
        >
      </div>
      {#if response !== null}<div class="email-response">
          <strong>Accepted by API</strong>
          <pre>{JSON.stringify(response, null, 2) ??
              "Request accepted (202)."}</pre>
        </div>{/if}
    </div>
  </section>
{:else if tab === "Jobs"}
  <section class="panel email-jobs-panel">
    <div class="panel-head email-jobs-head">
      <div>
        <div class="panel-title">Email jobs</div>
        <div class="panel-subtitle">
          {jobTotal.toLocaleString()} jobs · page {jobPage} of {jobPages}
        </div>
      </div>
      <div class="filters email-filters">
        <input
          class="input extra-filter"
          placeholder="Status"
          aria-label="Filter job status"
          bind:value={statusFilter}
        /><select
          class="select extra-filter"
          aria-label="Filter action"
          bind:value={actionFilter}
          ><option value="">All actions</option
          >{#each ["interview", "task_assigned", "rejected", "hired", "custom"] as action}<option
              value={action}>{action}</option
            >{/each}</select
        ><button
          class="button"
          onclick={() => {
            jobPage = 1;
            void loadJobs();
          }}>Apply</button
        ><button
          class="icon-button"
          onclick={resetJobFilters}
          aria-label="Clear filters"
          title="Clear filters"><X size={14} /></button
        >
      </div>
    </div>
    {#if loading}<div class="loading">Loading email jobs…</div>
    {:else if jobs.length === 0}<div class="empty">No email jobs found.</div>
    {:else}<div class="table-wrap">
        <table class="email-jobs-table">
          <thead
            ><tr
              ><th>Job ID</th><th>Action</th><th>Status</th><th>Recipients</th
              ><th>Created</th><th>Completed</th><th>Manage</th></tr
            ></thead
          ><tbody>
            {#each jobs as job, index (`${idOf(job)}-${index}`)}<tr
                ><td><code>{idOf(job) || "—"}</code></td><td
                  >{displayValue(job.action)}</td
                ><td
                  ><span
                    class="badge"
                    class:good={String(job.status).toLowerCase() ===
                      "completed" ||
                      String(job.status).toLowerCase() === "done"}
                    class:warn={String(job.status).toLowerCase() ===
                      "pending" ||
                      String(job.status).toLowerCase() === "running"}
                    class:bad={String(job.status).toLowerCase() === "failed"}
                    >{displayValue(job.status)}</span
                  ></td
                ><td
                  >{displayValue(
                    job.recipient_count ??
                      job.total_recipients ??
                      job.recipients_count ??
                      job.total,
                  )}</td
                ><td>{displayValue(job.created_at ?? job.started_at)}</td><td
                  >{displayValue(job.completed_at ?? job.finished_at)}</td
                ><td
                  ><div class="role-actions">
                    <button
                      class="icon-button"
                      onclick={() => inspectJob(job)}
                      aria-label="Inspect job"
                      title="Inspect job and delivery log"
                      ><Eye size={14} /></button
                    ><button
                      class="icon-button"
                      onclick={() => removeJob(job)}
                      disabled={busy}
                      aria-label="Delete job"
                      title="Delete job"><Trash2 size={14} /></button
                    >
                  </div></td
                ></tr
              >{/each}
          </tbody>
        </table>
      </div>{/if}
    <footer class="table-footer">
      <span
        >Showing {jobTotal ? (jobPage - 1) * pageSize + 1 : 0}–{Math.min(
          jobPage * pageSize,
          jobTotal,
        )} of {jobTotal}</span
      >
      <div class="pagination">
        <label for="email-page-size">Rows</label><select
          class="select"
          id="email-page-size"
          bind:value={pageSize}
          onchange={() => {
            jobPage = 1;
            void loadJobs();
            if (selectedJob) {
              logPage = 1;
              void loadLog();
            }
          }}
          ><option value={10}>10</option><option value={20}>20</option><option
            value={50}>50</option
          ><option value={100}>100</option></select
        ><button
          onclick={() => {
            jobPage = Math.max(1, jobPage - 1);
            void loadJobs();
          }}
          disabled={jobPage <= 1}
          aria-label="Previous jobs page"><ArrowLeft size={14} /></button
        ><span>{jobPage} / {jobPages}</span><button
          onclick={() => {
            jobPage = Math.min(jobPages, jobPage + 1);
            void loadJobs();
          }}
          disabled={jobPage >= jobPages}
          aria-label="Next jobs page"><ArrowRight size={14} /></button
        >
      </div>
    </footer>
  </section>
  {#if selectedJob}
    <section class="panel email-job-detail">
      <div class="panel-head">
        <div>
          <div class="panel-title">Job details</div>
          <div class="panel-subtitle"><code>{idOf(selectedJob)}</code></div>
        </div>
        <button
          class="icon-button"
          onclick={() => {
            selectedJob = null;
            jobLog = [];
          }}
          aria-label="Close job details"><X size={15} /></button
        >
      </div>
      <div class="email-job-summary">
        <pre>{JSON.stringify(selectedJob, null, 2)}</pre>
      </div>
      <div class="panel-head email-log-head">
        <div>
          <div class="panel-title">Delivery log</div>
          <div class="panel-subtitle">{logTotal.toLocaleString()} records</div>
        </div>
        <div class="filters">
          <input
            class="input extra-filter"
            placeholder="Log status"
            aria-label="Filter delivery log status"
            bind:value={logStatus}
          /><button
            class="button"
            onclick={() => {
              logPage = 1;
              void loadLog();
            }}>Filter</button
          >
        </div>
      </div>
      {#if jobLog.length}<div class="table-wrap">
          <table>
            <thead
              ><tr
                ><th>Recipient</th><th>Status</th><th>Action</th><th>Sent</th
                ><th>Detail</th></tr
              ></thead
            ><tbody
              >{#each jobLog as log, index (`${String(log._id ?? log.id ?? index)}`)}<tr
                  ><td
                    >{displayValue(
                      log.recipient ??
                        log.candidate_email ??
                        log.email ??
                        log.to,
                    )}</td
                  ><td>{displayValue(log.status)}</td><td
                    >{displayValue(log.action)}</td
                  ><td>{displayValue(log.sent_at ?? log.created_at)}</td><td
                    >{displayValue(
                      log.message ?? log.subject ?? log.error ?? log.detail,
                    )}</td
                  ></tr
                >{/each}</tbody
            >
          </table>
        </div>{:else}<div class="empty">
          No delivery log entries found.
        </div>{/if}
      <footer class="table-footer">
        <span
          >Showing {logTotal ? (logPage - 1) * pageSize + 1 : 0}–{Math.min(
            logPage * pageSize,
            logTotal,
          )} of {logTotal}</span
        >
        <div class="pagination">
          <button
            onclick={() => {
              logPage = Math.max(1, logPage - 1);
              void loadLog();
            }}
            disabled={logPage <= 1}
            aria-label="Previous log page"><ArrowLeft size={14} /></button
          ><span>{logPage} / {logPages}</span><button
            onclick={() => {
              logPage = Math.min(logPages, logPage + 1);
              void loadLog();
            }}
            disabled={logPage >= logPages}
            aria-label="Next log page"><ArrowRight size={14} /></button
          >
        </div>
      </footer>
    </section>
  {/if}
{:else}
  <section class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Available templates</div>
        <div class="panel-subtitle">
          Preview renders a template with server-provided sample data.
        </div>
      </div>
    </div>
    {#if loading}<div class="loading">Loading templates…</div>
    {:else if templates.length === 0}<div class="empty">
        No email templates found.
      </div>
    {:else}<div class="table-wrap">
        <table>
          <thead
            ><tr
              ><th>Action</th><th>Subject</th><th>Description</th><th
                >Preview</th
              ></tr
            ></thead
          ><tbody
            >{#each templates as template, index (`${String(template.action ?? template._id ?? index)}`)}<tr
                ><td>{displayValue(template.action ?? template._id)}</td><td
                  >{displayValue(template.subject)}</td
                ><td>{displayValue(template.description)}</td><td
                  ><button
                    class="button"
                    onclick={() => showTemplatePreview(template)}
                    ><Eye size={14} /> Preview</button
                  ></td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>{/if}
  </section>
{/if}

{#if templatePreview}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={(event) => {
      if (event.target === event.currentTarget) templatePreview = null;
    }}
  >
    <dialog
      open
      class="modal email-preview"
      aria-labelledby="email-template-preview-title"
    >
      <div class="modal-head">
        <h2 id="email-template-preview-title">
          {displayValue(templatePreview.subject)}
        </h2>
        <button
          class="icon-button"
          onclick={() => (templatePreview = null)}
          aria-label="Close template preview"><X size={16} /></button
        >
      </div>
      <div class="preview-content">
        <div class="preview-subject">
          <span>Action</span>{displayValue(templatePreview.action)}
        </div>
        <iframe
          class="preview-frame"
          title="Rendered email template"
          sandbox=""
          srcdoc={String(
            templatePreview.html ??
              templatePreview.body ??
              templatePreview.rendered ??
              "",
          )}
        ></iframe>
        <details>
          <summary>Raw preview data</summary>
          <pre>{JSON.stringify(templatePreview, null, 2)}</pre>
        </details>
      </div>
    </dialog>
  </div>
{/if}
