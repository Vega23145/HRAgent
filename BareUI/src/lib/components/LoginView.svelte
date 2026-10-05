<script lang="ts">
  import { FileText, ArrowRight } from '@lucide/svelte'

  let { error = '', apiBase, busy = false, onSubmit }: {
    error?: string
    apiBase: string
    busy?: boolean
    onSubmit: (event: SubmitEvent, username: string, password: string) => void
  } = $props()

  let username = $state('')
  let password = $state('')
</script>

<main class="login-page">
  <section class="login-box">
    <div class="brand"><span class="brand-mark"><FileText size={18} /></span><span>Resume Hub</span></div>
    <h1>Welcome back</h1>
    <p class="login-note">Sign in with your Resume Hub account.</p>
    {#if error}<div class="error-banner" style="margin-top:16px">{error}</div>{/if}
    <form class="form" onsubmit={(event) => onSubmit(event, username, password)}>
      <div class="field"><label for="username">Email or username</label><input class="input" id="username" name="username" autocomplete="username" bind:value={username} required /></div>
      <div class="field"><label for="password">Password</label><input class="input" id="password" name="password" type="password" autocomplete="current-password" bind:value={password} required /></div>
      <button class="button primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={15} /></button>
    </form>
    <p class="login-note">API: {apiBase}</p>
  </section>
</main>