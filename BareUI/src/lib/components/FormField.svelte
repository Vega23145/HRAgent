<script lang="ts">
  let {
    id,
    name,
    label,
    required = false,
    type = 'text',
    placeholder = '',
    maxlength,
    minlength,
    min,
    max,
    step,
    value,
  }: {
    id: string
    name: string
    label: string
    required?: boolean
    type?: string
    placeholder?: string
    maxlength?: number
    minlength?: number
    min?: number | string
    max?: number | string
    step?: number | string
    value?: string
  } = $props()
</script>

<div class="field">
  <label for={id}>{label}</label>
  <input class="input" {id} {name} {type} {placeholder} {required} {maxlength} {minlength} {min} {max} {step} {value} />
</div>