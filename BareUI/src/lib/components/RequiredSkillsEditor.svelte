<script lang="ts">
  import { Plus, Trash2 } from '@lucide/svelte'

  let skills = $state([{ name: '', weight: '1' }])

  function addSkill() {
    skills = [...skills, { name: '', weight: '1' }]
  }

  function removeSkill(index: number) {
    skills = skills.filter((_, position) => position !== index)
    if (!skills.length) skills = [{ name: '', weight: '1' }]
  }
</script>

<fieldset class="field skill-editor">
  <legend>Required skills and importance</legend>
  <p class="field-hint">Weight is a relative importance from 0.1 to 10.</p>
  {#each skills as skill, index (index)}
    <div class="skill-row">
      <input class="input" name={`skill_name_${index}`} aria-label={`Skill ${index + 1}`} placeholder="e.g. Python" maxlength="60" bind:value={skill.name} required />
      <input class="input skill-weight" name={`skill_weight_${index}`} aria-label={`Weight for skill ${index + 1}`} type="number" min="0.1" max="10" step="0.1" bind:value={skill.weight} required />
      <button class="icon-button" type="button" onclick={() => removeSkill(index)} aria-label="Remove skill"><Trash2 size={14} /></button>
    </div>
  {/each}
  <button class="button skill-add" type="button" onclick={addSkill}><Plus size={14} /> Add skill</button>
</fieldset>