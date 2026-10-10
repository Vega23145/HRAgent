<script lang="ts">
  import { onMount } from "svelte";
  import { Plus, X } from "@lucide/svelte";
  import {
    ApiError,
    clearTokens,
    getApiBase,
    getToken,
    login,
    request,
  } from "./lib/api";
  import { displayValue } from "./lib/format";
  import { fetchResourceDetail } from "./lib/api/resources";
  import { fetchResourcePage } from "./lib/api/resource-list";
  import { createEndpoint, createResourcePayload } from "./lib/forms/payloads";
  import { resources } from "./lib/resources";
  import type { ApiRecord, ResourceDefinition } from "./lib/types";
  import LoginView from "./lib/components/LoginView.svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Overview from "./lib/components/Overview.svelte";
  import ResourceTable from "./lib/components/ResourceTable.svelte";
  import RoleTable from "./lib/components/RoleTable.svelte";
  import CandidateTable from "./lib/components/CandidateTable.svelte";
  import CandidatePreview from "./lib/components/CandidatePreview.svelte";
  import ResourceRecordDetail from "./lib/components/ResourceRecordDetail.svelte";
  import RolePreview from "./lib/components/RolePreview.svelte";
  import ResourceForm from "./lib/components/ResourceForm.svelte";
  import MatchingWorkspace from "./lib/components/MatchingWorkspace.svelte";
  import EmailAgentWorkspace from "./lib/components/EmailAgentWorkspace.svelte";

  let active = $state("Overview");
  let token = $state<string | null>(null);
  let profile = $state<ApiRecord | null>(null);
  let stats = $state<ApiRecord | null>(null);
  let manifest = $state<ApiRecord | null>(null);
  let items = $state<ApiRecord[]>([]);
  let selectedRecord = $state<ApiRecord | null>(null);
  let editingRecord = $state<ApiRecord | null>(null);
  let page = $state(1);
  let size = $state(10);
  let total = $state(0);
  let filters = $state<Record<string, string>>({});
  let loading = $state(false);
  let online = $state(false);
  let error = $state("");
  let busy = $state(false);
  let showForm = $state(false);
  let collapsed = $state(false);
  let matchingInitialTab = $state("Match candidate");
  let filterTimers: Record<string, ReturnType<typeof setTimeout>> = {};

  const resource = $derived(
    resources.find((item) => item.label === active) ?? null,
  );
  const pageCount = $derived(Math.max(1, Math.ceil(total / size)));

  onMount(() => {
    token = getToken();
    if (token) void loadOverview();
  });

  function expireSession(cause: unknown) {
    if (cause instanceof ApiError && cause.status === 401) {
      clearTokens();
      token = null;
      profile = null;
      online = false;
      error = "";
      return true;
    }
    return false;
  }

  function message(cause: unknown) {
    return cause instanceof Error ? cause.message : "Something went wrong.";
  }

  async function loadOverview() {
    loading = true;
    error = "";
    try {
      const [manifestData, statsData, meData] = await Promise.all([
        request<ApiRecord>("/api/v1/admin/manifest"),
        request<ApiRecord>("/api/v1/admin/stats"),
        request<ApiRecord>("/api/v1/auth/me"),
      ]);
      manifest = manifestData;
      stats = statsData;
      profile =
        meData.user && typeof meData.user === "object"
          ? (meData.user as ApiRecord)
          : meData;
      online = true;
    } catch (cause) {
      if (expireSession(cause)) return;
      online = false;
      error = message(cause);
    } finally {
      loading = false;
    }
  }

  async function loadResource() {
    if (!resource) return;
    loading = true;
    error = "";
    try {
      const normalized = await fetchResourcePage(resource, {
        page,
        size,
        filters,
      });
      items = normalized.items;
      total = normalized.total;
      online = true;
    } catch (cause) {
      if (expireSession(cause)) return;
      error = message(cause);
      items = [];
      total = 0;
    } finally {
      loading = false;
    }
  }

  function selectSection(label: string) {
    if (label === "Email jobs" || label === "Email templates")
      label = "Email agent";
    active = label;
    page = 1;
    total = 0;
    items = [];
    selectedRecord = null;
    editingRecord = null;
    showForm = false;
    filters = {};
    error = "";
    if (label === "Overview") void loadOverview();
    else if (label === "Submissions") filters = { candidate_id: "" };
    else if (label === "Matching") matchingInitialTab = "Match candidate";
    else void loadResource();
  }

  function updateFilter(name: string, value: string) {
    filters = { ...filters, [name]: value };
    page = 1;
    clearTimeout(filterTimers[name]);
    filterTimers[name] = setTimeout(
      () => void loadResource(),
      name === "q" ? 300 : 0,
    );
  }

  async function changePage(next: number) {
    page = Math.max(1, Math.min(pageCount, next));
    await loadResource();
  }

  async function changeSize(next: number) {
    size = next;
    page = 1;
    await loadResource();
  }

  async function submitLogin(
    event: SubmitEvent,
    username: string,
    password: string,
  ) {
    event.preventDefault();
    busy = true;
    error = "";
    try {
      await login(username, password);
      token = getToken();
      await loadOverview();
    } catch (cause) {
      error = message(cause);
    } finally {
      busy = false;
    }
  }

  async function signOut() {
    try {
      await request("/api/v1/auth/logout", { method: "POST" });
    } catch {
      /* local sign-out must work if the API is unavailable */
    }
    clearTokens();
    token = null;
    profile = null;
    manifest = null;
    stats = null;
    items = [];
  }

  async function submitCreate(event: SubmitEvent, form: HTMLFormElement) {
    event.preventDefault();
    if (!resource) return;
    busy = true;
    error = "";
    try {
      const payload = createResourcePayload(
        resource,
        new FormData(form),
        editingRecord ?? undefined,
      );
      if (!payload) return;
      const endpoint =
        editingRecord && resource.id === "resumes"
          ? `${resource.endpoint}/${encodeURIComponent(String(editingRecord._id ?? editingRecord.id))}`
          : editingRecord && resource.id === "roles"
            ? `${resource.endpoint}/${encodeURIComponent(String(editingRecord._id ?? editingRecord.id))}`
            : createEndpoint(resource, payload);
      await request(endpoint, {
        method: editingRecord ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      showForm = false;
      editingRecord = null;
      form.reset();
      await loadResource();
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
    } finally {
      busy = false;
    }
  }

  async function runAllMatches() {
    try {
      await request("/api/v1/matching/run-all", { method: "POST" });
      error = "";
      active = "Matching";
      matchingInitialTab = "Jobs";
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
    }
  }

  function openResource(label: string) {
    selectSection(label);
  }

  async function inspectRecord(record: ApiRecord) {
    selectedRecord = record;
    if (!resource) return;
    try {
      selectedRecord = await fetchResourceDetail(resource, record);
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
    }
  }

  async function loadCandidateDetail(record: ApiRecord) {
    const resumeResource = resources.find((item) => item.id === "resumes");
    if (!resumeResource) return record;
    try {
      return await fetchResourceDetail(resumeResource, record);
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
      return record;
    }
  }

  async function previewCandidate(record: ApiRecord) {
    selectedRecord = await loadCandidateDetail(record);
  }

  async function discardCandidate(record: ApiRecord) {
    const candidateId = String(record._id ?? record.id ?? "");
    if (!candidateId) return;
    const candidateName = String(
      (record.resume as ApiRecord | undefined)?.name ??
        record.name ??
        candidateId,
    );
    if (
      !window.confirm(
        `Discard ${candidateName}? Its resume, role matches, and task submissions will be deleted.`,
      )
    )
      return;
    busy = true;
    error = "";
    try {
      await request(`/api/v1/resumes/${encodeURIComponent(candidateId)}`, {
        method: "DELETE",
      });
      if (
        String(selectedRecord?._id ?? selectedRecord?.id ?? "") === candidateId
      )
        selectedRecord = null;
      await loadResource();
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
    } finally {
      busy = false;
    }
  }

  async function editCandidate(record: ApiRecord) {
    selectedRecord = null;
    editingRecord = await loadCandidateDetail(record);
    showForm = true;
  }

  async function editRole(record: ApiRecord) {
    selectedRecord = null;
    editingRecord = await inspectResourceRecord(record);
    showForm = true;
  }

  async function inspectResourceRecord(record: ApiRecord) {
    if (!resource) return record;
    try {
      return await fetchResourceDetail(resource, record);
    } catch (cause) {
      if (!expireSession(cause)) error = message(cause);
      return record;
    }
  }
</script>

{#if !token}
  <LoginView {error} apiBase={getApiBase()} {busy} onSubmit={submitLogin} />
{:else}
  <div class="app-shell">
    <Sidebar
      {active}
      {collapsed}
      apiHost={new URL(getApiBase()).host}
      onSelect={selectSection}
      onToggle={() => (collapsed = !collapsed)}
      onLogout={signOut}
    />
    <main class="main-area">
      <header class="topbar">
        <div class="crumb">
          Workspace <span aria-hidden="true">/</span> <strong>{active}</strong>
        </div>
        <div class="top-actions">
          <div class="api-pill">
            <span class:online class="api-dot"></span><span
              >{online ? "API connected" : "API unavailable"}</span
            >
          </div>
          <div
            class="avatar"
            title={displayValue(profile?.full_name ?? profile?.email)}
          >
            {displayValue(profile?.full_name ?? profile?.email)
              .slice(0, 1)
              .toUpperCase()}
          </div>
        </div>
      </header>
      <section class="content">
        {#if error}<div class="error-banner">
            <span>{error}</span><button
              class="icon-button"
              onclick={() => (error = "")}
              aria-label="Dismiss error"><X size={15} /></button
            >
          </div>{/if}
        {#if active === "Overview"}
          <Overview
            {stats}
            {manifest}
            {loading}
            onRunMatches={runAllMatches}
            onOpen={openResource}
          />
        {:else if active === "Matching"}
          <MatchingWorkspace
            initialTab={matchingInitialTab}
            onError={(value) => (error = value)}
          />
        {:else if active === "Email agent"}
          <EmailAgentWorkspace
            onError={(value, status) => {
              if (status === 401) expireSession(new ApiError(value, status));
              else error = value;
            }}
          />
        {:else if resource}
          <div class="page-heading">
            <div>
              <p class="eyebrow">Workspace / {active}</p>
              <h1>{active}</h1>
              <p class="subheading">
                Browse and inspect {active.toLowerCase()} records.
              </p>
            </div>
            {#if resource.create}<button
                class="button primary"
                onclick={() => {
                  editingRecord = null;
                  showForm = true;
                }}
                ><Plus size={15} /> New {resource.id === "roles"
                  ? "role"
                  : resource.noun}</button
              >{/if}
          </div>
          {#if resource.id === "submissions" && !filters.candidate_id}<div
              class="info-banner"
            >
              Enter a candidate resume ID in the filters to list their
              submissions.
            </div>{/if}
          {#if resource.id === "resumes"}
            <CandidateTable
              {resource}
              {items}
              {page}
              {size}
              {total}
              {filters}
              {loading}
              onFilter={updateFilter}
              onPage={changePage}
              onSize={changeSize}
              onEdit={editCandidate}
              onPreview={previewCandidate}
              onDiscard={discardCandidate}
            />
          {:else if resource.id === "roles"}
            <RoleTable
              {resource}
              {items}
              {page}
              {size}
              {total}
              {filters}
              {loading}
              onFilter={updateFilter}
              onPage={changePage}
              onSize={changeSize}
              onSelect={inspectRecord}
              onEdit={editRole}
            />
          {:else}
            <ResourceTable
              {resource}
              {items}
              {page}
              {size}
              {total}
              {filters}
              {loading}
              onFilter={updateFilter}
              onPage={changePage}
              onSize={changeSize}
              onSelect={inspectRecord}
            />
          {/if}
        {/if}
      </section>
    </main>
  </div>
{/if}

{#if showForm && resource}
  <ResourceForm
    {resource}
    record={editingRecord}
    {busy}
    onClose={() => {
      showForm = false;
      editingRecord = null;
    }}
    onSubmit={submitCreate}
  />
{/if}

{#if selectedRecord && resource?.id === "roles"}
  <RolePreview
    role={selectedRecord}
    onClose={() => (selectedRecord = null)}
    onEdit={() => editRole(selectedRecord!)}
  />
{:else if selectedRecord && resource?.id === "resumes"}
  <CandidatePreview
    record={selectedRecord}
    onClose={() => (selectedRecord = null)}
    onEdit={() => editCandidate(selectedRecord!)}
  />
{:else if selectedRecord && resource}
  <ResourceRecordDetail
    record={selectedRecord}
    title={resource.noun}
    onClose={() => (selectedRecord = null)}
  />
{/if}
