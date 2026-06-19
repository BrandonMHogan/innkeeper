<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { openTrafficStream } from '$lib/api';
  import { formatBytes } from '$lib/utils';
  import { ScrollArea } from '$lib/components/ui/scroll-area';
  import { Card, CardHeader, CardContent } from '$lib/components/ui/card';
  import AlertTriangle from '@lucide/svelte/icons/alert-triangle';

  interface TopTalker {
    device: string;
    bytes: number;
    [key: string]: unknown;
  }

  interface ActiveConnection {
    device: string;
    dst_ip: string;
    dst_hostname?: string | null;
    dst_port?: number | null;
    protocol?: string | number | null;
    bytes: number;
    [key: string]: unknown;
  }

  interface Snapshot {
    top_talkers: TopTalker[];
    active_connections: ActiveConnection[];
    computed_at: string;
  }

  let source: EventSource | null = $state(null);
  let snapshot: Snapshot | null = $state(null);
  let connectionState: 'live' | 'reconnecting' | 'error' = $state('reconnecting');
  let consecutiveErrors = 0;

  const hasNoData = $derived.by(() => {
    const s = snapshot;
    if (s === null) return false;
    return s.top_talkers.length === 0 && s.active_connections.length === 0;
  });

  onMount(() => {
    const es = openTrafficStream();
    source = es;

    es.addEventListener('snapshot', (e: MessageEvent) => {
      try {
        snapshot = JSON.parse(e.data) as Snapshot;
        consecutiveErrors = 0;
        connectionState = 'live';
      } catch {
        // malformed snapshot payload — ignore this tick, keep prior data
      }
    });

    es.onopen = () => {
      consecutiveErrors = 0;
      connectionState = 'live';
    };

    es.onerror = () => {
      consecutiveErrors += 1;
      if (consecutiveErrors >= 3) {
        connectionState = 'error';
      } else if (connectionState === 'live') {
        connectionState = 'reconnecting';
      }
    };
  });

  onDestroy(() => {
    source?.close();
  });
</script>

<section style="margin-bottom: 24px;">
  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 24px;">
    <span
      aria-hidden="true"
      class={connectionState === 'live' ? 'live-pulse-dot' : ''}
      style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {connectionState ===
      'live'
        ? 'var(--color-accent)'
        : 'var(--color-muted)'};"
    ></span>
    <h2 style="font-size: 20px; font-weight: 600; line-height: 1.2; color: var(--color-fg); margin: 0;">
      Live Traffic
    </h2>
    <span aria-live="polite" style="font-size: 14px; font-weight: 500; line-height: 1.4; color: {connectionState === 'live' ? 'var(--color-fg)' : 'var(--color-muted)'};">
      {connectionState === 'live' ? 'Live' : connectionState === 'reconnecting' ? 'Reconnecting…' : ''}
    </span>
  </div>

  {#if connectionState === 'error'}
    <Card>
      <CardContent>
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;">
          <AlertTriangle size={20} color="var(--color-destructive)" />
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-destructive); margin: 0;">
            Live traffic feed unavailable
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Couldn't connect to the live traffic stream. Check that the capture service is running, then refresh the
            page.
          </p>
        </div>
      </CardContent>
    </Card>
  {:else if hasNoData}
    <Card>
      <CardContent>
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;">
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin: 0;">
            No active connections
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Nothing to show right now — this updates automatically as devices send and receive traffic.
          </p>
        </div>
      </CardContent>
    </Card>
  {:else}
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;">
      <Card>
        <CardHeader>
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">Top Talkers</span>
        </CardHeader>
        <CardContent>
          <ScrollArea style="max-height: 280px;">
            <ol style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px;">
              {#each snapshot?.top_talkers ?? [] as talker, i (talker.device + i)}
                <li style="display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 40px; padding: 8px 16px;">
                  <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
                    {talker.device}
                  </span>
                  <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted);">
                    {formatBytes(talker.bytes)}
                  </span>
                </li>
              {/each}
            </ol>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
            Active Connections
          </span>
        </CardHeader>
        <CardContent>
          <ScrollArea style="max-height: 280px;">
            <ul style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px;">
              {#each snapshot?.active_connections ?? [] as conn, i (conn.device + conn.dst_ip + i)}
                <li style="display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 40px; padding: 8px 16px;">
                  <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg);">
                    {conn.device} → {conn.dst_hostname ?? conn.dst_ip}
                  </span>
                  <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted);">
                    {conn.protocol ?? ''}{conn.dst_port ? `:${conn.dst_port}` : ''} · {formatBytes(conn.bytes)}
                  </span>
                </li>
              {/each}
            </ul>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  {/if}
</section>

<style>
  .live-pulse-dot {
    animation: pulse-opacity 2s ease-in-out infinite;
  }

  @keyframes pulse-opacity {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.4;
    }
  }
</style>
