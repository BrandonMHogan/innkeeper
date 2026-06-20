<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet, listDevices, triggerScan } from '$lib/api';
  import DeviceCard from '$lib/components/DeviceCard.svelte';
  import RegisterDialog from '$lib/components/RegisterDialog.svelte';
  import MergeDialog from '$lib/components/MergeDialog.svelte';
  import LiveTrafficFeed from '$lib/components/LiveTrafficFeed.svelte';
  import BandwidthHistoryChart from '$lib/components/BandwidthHistoryChart.svelte';
  import DestinationsBreakdown from '$lib/components/DestinationsBreakdown.svelte';
  import NetworkBandwidthChart from '$lib/components/NetworkBandwidthChart.svelte';
  import SecurityAlertsBanner from '$lib/components/SecurityAlertsBanner.svelte';
  import ScanResultDialog from '$lib/components/ScanResultDialog.svelte';

  interface DeviceListItem {
    id: number;
    unknown: boolean;
    name?: string | null;
    type?: string | null;
    last_seen: string;
    vendor?: string | null;
    type_guess?: string | null;
    name_guess?: string | null;
    security_status?: string | null;
    last_scanned_at?: string | null;
    [key: string]: unknown;
  }

  let authenticated = $state(false);
  let checking = $state(true);
  let devices = $state<DeviceListItem[]>([]);

  let registerDialogOpen = $state(false);
  let mergeDialogOpen = $state(false);
  let selectedIdentityId = $state<number | null>(null);

  let scanDialogOpen = $state(false);
  let selectedScanDeviceId = $state<number | null>(null);

  const unknownDevices = $derived(devices.filter((d) => d.unknown));
  const registeredDevices = $derived(devices.filter((d) => !d.unknown));
  const sortedDevices = $derived([...unknownDevices, ...registeredDevices]);
  const unknownCount = $derived(unknownDevices.length);
  const existingDevices = $derived(
    registeredDevices.map((d) => ({ id: d.id, name: d.name ?? '' }))
  );
  const selectedDeviceGuess = $derived(devices.find((d) => d.id === selectedIdentityId));
  const selectedScanDevice = $derived(devices.find((d) => d.id === selectedScanDeviceId) ?? null);

  let selectedDeviceId = $state<number | null>(null);

  async function loadDevices() {
    try {
      devices = (await listDevices()) as DeviceListItem[];
    } catch {
      devices = [];
    }
    if (selectedDeviceId === null && registeredDevices.length > 0) {
      selectedDeviceId = registeredDevices[0].id;
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

  async function handleScan(deviceId: number) {
    const res = await triggerScan(deviceId);
    if (!res.ok) throw new Error('Failed to trigger scan');

    const priorScannedAt = devices.find((d) => d.id === deviceId)?.last_scanned_at ?? null;
    const pollStart = Date.now();
    const pollIntervalMs = 5000;
    const pollTimeoutMs = 60000;

    const poll = setInterval(async () => {
      await loadDevices();
      const current = devices.find((d) => d.id === deviceId);
      const changed = current && current.last_scanned_at !== priorScannedAt;
      if (changed || Date.now() - pollStart >= pollTimeoutMs) {
        clearInterval(poll);
      }
    }, pollIntervalMs);
  }

  function handleShowResults(deviceId: number) {
    selectedScanDeviceId = deviceId;
    scanDialogOpen = true;
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

    <LiveTrafficFeed />

    <SecurityAlertsBanner />

    {#if registeredDevices.length > 0}
      <section style="margin-bottom: 48px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted);">
            Device
          </span>
          <select
            bind:value={selectedDeviceId}
            style="background: var(--color-surface); color: var(--color-fg); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 16px; font-size: 14px; min-height: 44px;"
          >
            {#each registeredDevices as device (device.id)}
              <option value={device.id}>{device.name}</option>
            {/each}
          </select>
        </div>
        {#if selectedDeviceId !== null}
          <BandwidthHistoryChart deviceId={selectedDeviceId} />
          <DestinationsBreakdown deviceId={selectedDeviceId} />
        {/if}
      </section>
    {/if}

    <NetworkBandwidthChart />

    <div
      style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px; margin-bottom: 24px; font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);"
    >
      {devices.length} device{devices.length === 1 ? '' : 's'}{#if unknownCount > 0}
        {' '}· <span style="color: var(--color-warning);">{unknownCount} unknown</span>
      {/if}
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px;">
      {#each sortedDevices as device (device.id + (device.unknown ? '-unknown' : '-registered'))}
        <DeviceCard
          {device}
          onRegister={handleRegister}
          onMerge={handleMerge}
          onScan={handleScan}
          onShowResults={handleShowResults}
        />
      {/each}
    </div>
  </main>

  <RegisterDialog
    identityId={selectedIdentityId}
    bind:open={registerDialogOpen}
    onRegistered={handleRegistered}
    nameGuess={selectedDeviceGuess?.name_guess ?? null}
    typeGuess={selectedDeviceGuess?.type_guess ?? null}
  />
  <MergeDialog
    identityId={selectedIdentityId}
    {existingDevices}
    bind:open={mergeDialogOpen}
    onMerged={handleMerged}
  />
  {#if selectedScanDevice}
    <ScanResultDialog
      device={{ id: selectedScanDevice.id, name: selectedScanDevice.name ?? '' }}
      bind:open={scanDialogOpen}
    />
  {/if}
{/if}
