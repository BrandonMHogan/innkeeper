<script lang="ts">
  import { getDeviceBandwidth } from '$lib/api';
  import { formatBytes } from '$lib/utils';
  import { Card, CardHeader, CardContent } from '$lib/components/ui/card';
  import { Input } from '$lib/components/ui/input';
  import { LineChart } from 'layerchart';
  import AlertTriangle from '@lucide/svelte/icons/alert-triangle';

  interface BandwidthPoint {
    time: string;
    bytes_rx: number;
    bytes_tx: number;
    total: number;
  }

  let { deviceId }: { deviceId: number } = $props();

  function defaultStart(): string {
    return new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  }
  function defaultEnd(): string {
    return new Date().toISOString();
  }

  let start = $state(defaultStart());
  let end = $state(defaultEnd());
  let points: BandwidthPoint[] = $state([]);
  let loading = $state(false);
  let error = $state(false);

  $effect(() => {
    const currentDeviceId = deviceId;
    const currentStart = start;
    const currentEnd = end;

    let cancelled = false;
    async function load() {
      loading = true;
      error = false;
      try {
        const res = (await getDeviceBandwidth(currentDeviceId, currentStart, currentEnd)) as {
          points: Array<{ time: string; bytes_rx: number; bytes_tx: number }>;
        };
        if (cancelled) return;
        points = res.points.map((p) => ({
          time: p.time,
          bytes_rx: p.bytes_rx,
          bytes_tx: p.bytes_tx,
          total: p.bytes_rx + p.bytes_tx,
        }));
      } catch {
        if (!cancelled) {
          error = true;
          points = [];
        }
      } finally {
        if (!cancelled) loading = false;
      }
    }
    load();

    return () => {
      cancelled = true;
    };
  });

  const chartData = $derived(points.map((p) => ({ ...p, time: new Date(p.time) })));
</script>

<section style="margin-bottom: 48px;">
  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;">
    <h2 style="font-size: 20px; font-weight: 600; line-height: 1.2; color: var(--color-fg); margin: 0;">
      Bandwidth History
    </h2>
  </div>

  <Card>
    <CardHeader>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <label style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted);" for="bandwidth-start">
          From
        </label>
        <Input id="bandwidth-start" type="datetime-local" bind:value={start} style="width: auto;" />
        <label style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted);" for="bandwidth-end">
          To
        </label>
        <Input id="bandwidth-end" type="datetime-local" bind:value={end} style="width: auto;" />
      </div>
    </CardHeader>
    <CardContent>
      {#if loading}
        <div style="display: flex; align-items: center; justify-content: center; height: 240px;">
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Loading…
          </p>
        </div>
      {:else if error}
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; height: 240px; justify-content: center; text-align: center;">
          <AlertTriangle size={20} color="var(--color-destructive)" />
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-destructive); margin: 0;">
            Couldn't load bandwidth history
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Something went wrong loading this chart. Try again, or check the server logs if this keeps happening.
          </p>
        </div>
      {:else if points.length === 0}
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; height: 240px; justify-content: center; text-align: center;">
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin: 0;">
            No bandwidth data yet
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            This device hasn't been observed sending or receiving traffic. Data will appear here once it does.
          </p>
        </div>
      {:else}
        <div style="height: 240px;">
          <LineChart
            data={chartData}
            x="time"
            y="total"
            series={[{ key: 'total', value: (d: BandwidthPoint) => d.total, color: 'var(--color-accent)' }]}
            props={{ yAxis: { format: (v: number) => formatBytes(v) } }}
          />
        </div>
      {/if}
    </CardContent>
  </Card>
</section>
