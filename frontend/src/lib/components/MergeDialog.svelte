<script lang="ts">
  import { Select as SelectPrimitive } from 'bits-ui';
  import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '$lib/components/ui/dialog';
  import { Label } from '$lib/components/ui/label';
  import { Button } from '$lib/components/ui/button';
  import {
    Select,
    SelectTrigger,
    SelectContent,
    SelectItem,
  } from '$lib/components/ui/select';
  import { Loader2 } from '@lucide/svelte';
  import { mergeDevice } from '$lib/api';

  let {
    identityId,
    existingDevices,
    open = $bindable(false),
    onMerged,
  }: {
    identityId: number | null;
    existingDevices: Array<{ id: number; name: string }>;
    open: boolean;
    onMerged: () => void;
  } = $props();

  let targetDeviceId = $state<string | undefined>(undefined);
  let loading = $state(false);
  let errorMessage = $state('');

  function resetForm() {
    targetDeviceId = undefined;
    errorMessage = '';
  }

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (identityId === null || !targetDeviceId) return;
    errorMessage = '';
    loading = true;
    try {
      const res = await mergeDevice(identityId, Number(targetDeviceId));
      if (!res.ok) {
        errorMessage = 'Could not merge devices. Check that the API is reachable and try again.';
        loading = false;
        return;
      }
      loading = false;
      open = false;
      resetForm();
      onMerged();
    } catch {
      errorMessage = 'Could not merge devices. Check that the API is reachable and try again.';
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
      <DialogTitle>Merge with Existing Device</DialogTitle>
    </DialogHeader>

    <form onsubmit={handleSubmit} style="display: flex; flex-direction: column; gap: 16px;">
      <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg); margin: 0;">
        This will combine the unknown device's activity into the device you choose below. This cannot be undone.
      </p>

      <div>
        <Label for="merge-target">Merge into</Label>
        <Select type="single" bind:value={targetDeviceId}>
          <SelectTrigger id="merge-target">
            <SelectPrimitive.Value placeholder="Choose an existing device" />
          </SelectTrigger>
          <SelectContent>
            {#each existingDevices as device (device.id)}
              <SelectItem value={String(device.id)} label={device.name}>{device.name}</SelectItem>
            {/each}
          </SelectContent>
        </Select>
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
        <Button
          type="submit"
          variant="outline"
          disabled={loading}
          aria-busy={loading}
          style="color: var(--color-destructive); border-color: var(--color-destructive);"
        >
          {#if loading}
            <Loader2 size={16} class="animate-spin" />
          {:else}
            Merge Devices
          {/if}
        </Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
