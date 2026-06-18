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

  interface DeviceCardDevice {
    id: number;
    unknown: boolean;
    name?: string | null;
    type?: string | null;
    last_seen: string;
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
      <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0 0 16px 0;">
        Last seen {formatRelativeTime(device.last_seen)}
      </p>
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
</style>
