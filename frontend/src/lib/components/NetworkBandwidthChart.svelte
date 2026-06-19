<script lang="ts">
  import { getNetworkBandwidth } from '$lib/api';
  import { formatBytes } from '$lib/utils';
  import { Card, CardHeader, CardContent } from '$lib/components/ui/card';
  import { Tabs, TabsList, TabsTrigger } from '$lib/components/ui/tabs';
  import { BarChart } from 'layerchart';
  import AlertTriangle from '@lucide/svelte/icons/alert-triangle';

  interface Bucket {
    bucket: string;
    bytes_rx: number;
    bytes_tx: number;
    total: number;
  }

  let view: 'daily' | 'weekly' | 'monthly' = $state('daily');
  let buckets: Bucket[] = $state([]);
  let loading = $state(false);
  let error = $state(false);

  $effect(() => {
    const currentView = view;
    let cancelled = false;

    async function load() {
      loading = true;
      error = false;
      try {
        const res = (await getNetworkBandwidth(currentView)) as {
          buckets: Array<{ bucket: string; bytes_rx: number; bytes_tx: number }>;
        };
        if (cancelled) return;
        buckets = res.buckets.map((b) => ({
          bucket: b.bucket,
          bytes_rx: b.bytes_rx,
          bytes_tx: b.bytes_tx,
          total: b.bytes_rx + b.bytes_tx,
        }));
      } catch {
        if (!cancelled) {
          error = true;
          buckets = [];
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

  const chartData = $derived(buckets.map((b) => ({ ...b, bucket: new Date(b.bucket) })));
</script>

<section style="margin-bottom: 24px;">
  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 8px;">
    <h2 style="font-size: 20px; font-weight: 600; line-height: 1.2; color: var(--color-fg); margin: 0;">
      Network-Wide Bandwidth
    </h2>
    <Tabs bind:value={view}>
      <TabsList>
        <TabsTrigger value="daily">Daily</TabsTrigger>
        <TabsTrigger value="weekly">Weekly</TabsTrigger>
        <TabsTrigger value="monthly">Monthly</TabsTrigger>
      </TabsList>
    </Tabs>
  </div>

  <Card>
    <CardHeader>
      <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
        {view === 'daily' ? 'Daily' : view === 'weekly' ? 'Weekly' : 'Monthly'}
      </span>
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
      {:else if buckets.length === 0}
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; height: 240px; justify-content: center; text-align: center;">
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin: 0;">
            No network activity recorded yet
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Bandwidth totals will appear here once traffic has been observed.
          </p>
        </div>
      {:else}
        <div style="height: 240px;">
          <BarChart
            data={chartData}
            x="bucket"
            y="total"
            series={[{ key: 'total', value: (d: Bucket) => d.total, color: 'var(--color-accent)' }]}
            props={{ yAxis: { format: (v: number) => formatBytes(v) } }}
          />
        </div>
      {/if}
    </CardContent>
  </Card>
</section>
