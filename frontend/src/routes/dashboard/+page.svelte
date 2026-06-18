<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet, listDevices } from '$lib/api';
  import DeviceCard from '$lib/components/DeviceCard.svelte';
  import RegisterDialog from '$lib/components/RegisterDialog.svelte';
  import MergeDialog from '$lib/components/MergeDialog.svelte';

  interface DeviceListItem {
    id: number;
    unknown: boolean;
    name?: string | null;
    type?: string | null;
    last_seen: string;
    [key: string]: unknown;
  }

  let authenticated = $state(false);
  let checking = $state(true);
  let devices = $state<DeviceListItem[]>([]);

  let registerDialogOpen = $state(false);
  let mergeDialogOpen = $state(false);
  let selectedIdentityId = $state<number | null>(null);

  const unknownDevices = $derived(devices.filter((d) => d.unknown));
  const registeredDevices = $derived(devices.filter((d) => !d.unknown));
  const sortedDevices = $derived([...unknownDevices, ...registeredDevices]);
  const unknownCount = $derived(unknownDevices.length);
  const existingDevices = $derived(
    registeredDevices.map((d) => ({ id: d.id, name: d.name ?? '' }))
  );

  async function loadDevices() {
    try {
      devices = (await listDevices()) as DeviceListItem[];
    } catch {
      devices = [];
    }
  }

  onMount(async () => {
    try {
      const res = await apiGet('/api/auth/me');
      if (!res.ok) {
        await goto('/login');
        return;
      }
      authenticated = true;
    } catch {
      await goto('/login');
      return;
    } finally {
      checking = false;
    }

    if (authenticated) {
      await loadDevices();
    }
  });

  function handleRegister(identityId: number) {
    selectedIdentityId = identityId;
    registerDialogOpen = true;
  }

  function handleMerge(identityId: number) {
    selectedIdentityId = identityId;
    mergeDialogOpen = true;
  }

  async function handleRegistered() {
    await loadDevices();
  }

  async function handleMerged() {
    await loadDevices();
  }
</script>

<svelte:head>
  <title>Innkeeper</title>
</svelte:head>

{#if authenticated}
  <main style="padding: 24px;">
    <h1 style="font-size: 28px; font-weight: 700; line-height: 1.15; color: var(--color-fg); margin: 0 0 16px 0;">
      Dashboard
    </h1>

    <div
      style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px; margin-bottom: 24px; font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);"
    >
      {devices.length} device{devices.length === 1 ? '' : 's'}{#if unknownCount > 0}
        {' '}· <span style="color: var(--color-warning);">{unknownCount} unknown</span>
      {/if}
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px;">
      {#each sortedDevices as device (device.id + (device.unknown ? '-unknown' : '-registered'))}
        <DeviceCard {device} onRegister={handleRegister} onMerge={handleMerge} />
      {/each}
    </div>
  </main>

  <RegisterDialog
    identityId={selectedIdentityId}
    bind:open={registerDialogOpen}
    onRegistered={handleRegistered}
  />
  <MergeDialog
    identityId={selectedIdentityId}
    {existingDevices}
    bind:open={mergeDialogOpen}
    onMerged={handleMerged}
  />
{/if}
