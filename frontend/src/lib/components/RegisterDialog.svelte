<script lang="ts">
  import { Select as SelectPrimitive } from 'bits-ui';
  import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '$lib/components/ui/dialog';
  import { Label } from '$lib/components/ui/label';
  import { Input } from '$lib/components/ui/input';
  import { Button } from '$lib/components/ui/button';
  import {
    Select,
    SelectTrigger,
    SelectContent,
    SelectItem,
  } from '$lib/components/ui/select';
  import { Loader2 } from '@lucide/svelte';
  import { registerDevice } from '$lib/api';

  let {
    identityId,
    open = $bindable(false),
    onRegistered,
    nameGuess = null,
    typeGuess = null,
  }: {
    identityId: number | null;
    open: boolean;
    onRegistered: () => void;
    nameGuess?: string | null;
    typeGuess?: string | null;
  } = $props();

  const deviceTypeOptions: { value: string; label: string }[] = [
    { value: 'phone', label: 'Phone' },
    { value: 'laptop', label: 'Laptop' },
    { value: 'desktop', label: 'Desktop' },
    { value: 'tablet', label: 'Tablet' },
    { value: 'iot_smart_home', label: 'IoT/Smart Home' },
    { value: 'tv_streaming', label: 'TV/Streaming' },
    { value: 'game_console', label: 'Game Console' },
    { value: 'router_network', label: 'Router/Network' },
    { value: 'other', label: 'Other' },
  ];

  let name = $state(nameGuess ?? '');
  let owner = $state('');
  let type = $state<string | undefined>(typeGuess ?? undefined);
  let trusted = $state(false);
  let loading = $state(false);
  let errorMessage = $state('');

  function resetForm() {
    name = nameGuess ?? '';
    owner = '';
    type = typeGuess ?? undefined;
    trusted = false;
    errorMessage = '';
  }

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (identityId === null || !type) return;
    errorMessage = '';
    loading = true;
    try {
      const res = await registerDevice({
        identity_id: identityId,
        name,
        owner,
        type,
        trusted,
      });
      if (!res.ok) {
        errorMessage = 'Could not register device. Check that the API is reachable and try again.';
        loading = false;
        return;
      }
      loading = false;
      open = false;
      resetForm();
      onRegistered();
    } catch {
      errorMessage = 'Could not register device. Check that the API is reachable and try again.';
      loading = false;
    }
  }

  function handleCancel() {
    open = false;
    resetForm();
  }
</script>

<Dialog bind:open>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Register Device</DialogTitle>
    </DialogHeader>

    <form onsubmit={handleSubmit} style="display: flex; flex-direction: column; gap: 16px;">
      <div>
        <Label for="register-name">Name</Label>
        <Input id="register-name" placeholder="e.g. Brandon's MacBook" bind:value={name} required />
        {#if nameGuess}
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 4px 0 0 0;">
            Guessed from device signals — feel free to change
          </p>
        {/if}
      </div>

      <div>
        <Label for="register-owner">Owner</Label>
        <Input id="register-owner" placeholder="e.g. Brandon, Guest, Shared" bind:value={owner} />
      </div>

      <div>
        <Label for="register-type">Device Type</Label>
        <Select type="single" bind:value={type}>
          <SelectTrigger id="register-type">
            <SelectPrimitive.Value placeholder="Select a type" />
          </SelectTrigger>
          <SelectContent>
            {#each deviceTypeOptions as option (option.value)}
              <SelectItem value={option.value} label={option.label}>{option.label}</SelectItem>
            {/each}
          </SelectContent>
        </Select>
        {#if typeGuess}
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 4px 0 0 0;">
            Guessed from device signals — feel free to change
          </p>
        {/if}
      </div>

      <div style="display: flex; align-items: flex-start; gap: 8px;">
        <input
          type="checkbox"
          id="register-trusted"
          bind:checked={trusted}
          style="margin-top: 4px;"
        />
        <div>
          <Label for="register-trusted">Trusted device</Label>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 4px 0 0 0;">
            Trusted devices are informational for now — future features will use this.
          </p>
        </div>
      </div>

      {#if errorMessage}
        <div
          role="alert"
          style="border: 1px solid var(--color-destructive); color: var(--color-destructive); border-radius: 6px; padding: 8px 12px; font-size: 14px;"
        >
          {errorMessage}
        </div>
      {/if}

      <DialogFooter>
        <Button type="button" variant="outline" onclick={handleCancel}>Cancel</Button>
        <Button type="submit" disabled={loading} aria-busy={loading}>
          {#if loading}
            <Loader2 size={16} class="animate-spin" />
          {:else}
            Register Device
          {/if}
        </Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
