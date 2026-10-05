<script lang="ts">
  import { ChevronDown, LogOut, FileText } from '@lucide/svelte'

  let { active, collapsed = false, apiHost, onSelect, onToggle, onLogout }: {
    active: string
    collapsed?: boolean
    apiHost: string
    onSelect: (label: string) => void
    onToggle: () => void
    onLogout: () => void
  } = $props()

  import { navigation } from '../resources'
</script>

<aside class:collapsed class="sidebar">
  <div class="brand"><span class="brand-mark"><FileText size={18} /></span><span class="brand-name">Resume Hub</span></div>
  <div class="nav-label">Workspace</div>
  <nav aria-label="Main navigation">
    {#each navigation as item (item.label)}
      <button class:active={active === item.label} class="nav-item" onclick={() => onSelect(item.label)} title={item.label}>
        <item.icon size={17} /><span>{item.label}</span>
      </button>
    {/each}
  </nav>
  <div class="sidebar-bottom">
    <button class="nav-item" onclick={onToggle} title={collapsed ? 'Expand navigation' : 'Collapse navigation'}><ChevronDown size={17} /><span>{collapsed ? 'Expand menu' : 'Collapse menu'}</span></button>
    <div class="connection"><strong>Workspace status</strong>API: {apiHost}</div>
    <button class="nav-item" onclick={onLogout}><LogOut size={17} /><span>Sign out</span></button>
  </div>
</aside>