<script lang="ts">
  import { Card, CardHeader, CardContent } from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import { Button } from '$lib/components/ui/button';
  import Smartphone from '@lucide/svelte/icons/smartphone';
  import Laptop from '@lucide/svelte/icons/laptop';
  import Monitor from '@lucide/svelte/icons/monitor';
  import Tablet from '@lucide/svelte/icons/tablet';
  import Lightbulb from '@lucide/svelte/icons/lightbulb';
  import Tv from '@lucide/svelte/icons/tv';
  import Gamepad2 from '@lucide/svelte/icons/gamepad-2';
  import Router from '@lucide/svelte/icons/router';
  import HelpCircle from '@lucide/svelte/icons/help-circle';
  import Info from '@lucide/svelte/icons/info';
  import { Popover, PopoverTrigger, PopoverContent } from '$lib/components/ui/popover';

  interface DeviceCardDevice {
    id: number;
    unknown: boolean;
    name?: string | null;
    type?: string | null;
    last_seen: string;
    vendor?: string | null;
    type_guess?: string | null;
    name_guess?: string | null;
    raw_signals?: {
      mac: string | null;
      raw_vendor: string | null;
      mdns_service_type: string | null;
      dhcp_vendor_class: string | null;
    } | null;
  }

  let {
    device,
    onRegister,
    onMerge,
  }: {
    device: DeviceCardDevice;
    onRegister: (identityId: number) => void;
    onMerge: (identityId: number) => void;
  } = $props();

  const typeIconMap: Record<string, typeof HelpCircle> = {
    phone: Smartphone,
    laptop: Laptop,
    desktop: Monitor,
    tablet: Tablet,
    iot_smart_home: Lightbulb,
    tv_streaming: Tv,
    game_console: Gamepad2,
    router_network: Router,
    other: HelpCircle,
  };

  const inferenceTypeLabelMap: Record<string, string> = {
    phone: 'phone',
    laptop: 'a laptop',
    desktop: 'a computer',
    tablet: 'a tablet',
    iot_smart_home: 'a smart-home device',
    tv_streaming: 'a TV/streaming device',
    game_console: 'a game console',
    router_network: 'a router',
    other: 'a device',
  };

  function formatRelativeTime(isoString: string): string {
    const then = new Date(isoString).getTime();
    const now = Date.now();
    const diffMs = Math.max(0, now - then);
    const diffMinutes = Math.floor(diffMs / 60000);
    if (diffMinutes < 1) return 'just now';
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  }

  const isOnline = $derived(Date.now() - new Date(device.last_seen).getTime() < 5 * 60 * 1000);
  const Icon = $derived(device.unknown ? HelpCircle : typeIconMap[device.type ?? 'other'] ?? HelpCircle);

  const inferenceLine = $derived.by(() => {
    const vendor = device.vendor ?? null;
    const typeGuess = device.type_guess ?? null;
    const typeLabel = typeGuess ? inferenceTypeLabelMap[typeGuess] ?? null : null;
    if (vendor && typeLabel) return `Looks like: ${vendor} · ${typeLabel}`;
    if (vendor) return `Looks like: ${vendor}`;
    if (typeLabel) return `Looks like: ${typeLabel}`;
    return null;
  });

  const rawSignalRows = $derived.by(() => {
    const raw = device.raw_signals;
    if (!raw) return [];
    const rows: { label: string; value: string }[] = [];
    if (raw.mac) rows.push({ label: 'MAC', value: raw.mac });
    if (raw.raw_vendor) rows.push({ label: 'Vendor (raw)', value: raw.raw_vendor });
    if (raw.mdns_service_type) rows.push({ label: 'mDNS', value: raw.mdns_service_type });
    if (raw.dhcp_vendor_class) rows.push({ label: 'DHCP class', value: raw.dhcp_vendor_class });
    return rows;
  });
</script>

{#if device.unknown}
  <Card style="border-style: dashed; border-color: var(--color-warning);">
    <CardHeader>
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <HelpCircle size={20} color="var(--color-muted)" />
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
            Unknown Device
          </span>
        </div>
        <Badge variant="outline" style="color: var(--color-warning); border-color: var(--color-warning);">
          Unknown
        </Badge>
      </div>
    </CardHeader>
    <CardContent>
      <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0 0 8px 0;">
        Last seen {formatRelativeTime(device.last_seen)}
      </p>
      {#if inferenceLine}
        <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); font-style: italic; margin: 0 0 16px 0;">
          {inferenceLine}
          <Popover>
            <PopoverTrigger
              class="info-trigger"
              style="display: inline-flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; margin-left: 4px; vertical-align: middle; background: none; border: none; cursor: pointer;"
              aria-label="Show raw signal data"
            >
              <Info size={14} color="var(--color-muted)" />
            </PopoverTrigger>
            <PopoverContent>
              {#if rawSignalRows.length > 0}
                <div style="display: flex; flex-direction: column; gap: 8px; padding: 0; max-width: 280px;">
                  {#each rawSignalRows as row (row.label)}
                    <div>
                      <div style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted);">
                        {row.label}
                      </div>
                      <div
                        style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; word-wrap: break-word; overflow-wrap: break-word;"
                      >
                        {row.value}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg); margin: 0;">
                  No raw signal data available.
                </p>
              {/if}
            </PopoverContent>
          </Popover>
        </p>
      {/if}
      <div style="display: flex; gap: 8px;">
        <Button onclick={() => onRegister(device.id)}>Register</Button>
        <Button variant="outline" onclick={() => onMerge(device.id)}>Merge with...</Button>
      </div>
    </CardContent>
  </Card>
{:else}
  <Card>
    <CardHeader>
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <Icon size={20} color="var(--color-fg)" />
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
            {device.name}
          </span>
        </div>
        <span
          aria-hidden="true"
          style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {isOnline
            ? 'var(--color-accent)'
            : 'var(--color-muted)'};"
        ></span>
        <span class="sr-only">{isOnline ? 'Online' : 'Offline'}</span>
      </div>
    </CardHeader>
    <CardContent>
      <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
        Last seen {formatRelativeTime(device.last_seen)}
      </p>
    </CardContent>
  </Card>
{/if}

<style>
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  :global(.info-trigger:hover svg),
  :global(.info-trigger:focus-visible svg) {
    color: var(--color-fg);
  }
</style>
