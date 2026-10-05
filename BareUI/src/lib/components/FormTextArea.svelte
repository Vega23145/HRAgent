<script lang="ts">
  let { id, name, label, required = false, maxlength, value = '' }: {
    id: string
    name: string
    label: string
    required?: boolean
    maxlength?: number
    value?: string
  } = $props()
</script>

<div class="field">
  <label for={id}>{label}</label>
  <textarea class="textarea" {id} {name} {required} {maxlength}>{value}</textarea>
</div>