<script lang="ts">
  import { getDeviceDestinations } from '$lib/api';
  import { formatBytes } from '$lib/utils';
  import { Card, CardHeader, CardContent } from '$lib/components/ui/card';

  interface Destination {
    label: string;
    bytes: number;
  }

  let { deviceId }: { deviceId: number } = $props();

  let destinations: Destination[] = $state([]);
  let loading = $state(false);
  let error = $state(false);

  $effect(() => {
    const currentDeviceId = deviceId;
    let cancelled = false;

    async function load() {
      loading = true;
      error = false;
      try {
        const res = (await getDeviceDestinations(currentDeviceId)) as {
          destinations: Destination[];
        };
        if (cancelled) return;
        destinations = res.destinations ?? [];
      } catch {
        if (!cancelled) {
          error = true;
          destinations = [];
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
</script>

<section style="margin-bottom: 24px;">
  <h2 style="font-size: 20px; font-weight: 600; line-height: 1.2; color: var(--color-fg); margin: 0 0 24px 0;">
    Destinations
  </h2>

  <Card>
    <CardHeader>
      <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">Destinations</span>
    </CardHeader>
    <CardContent>
      {#if loading}
        <div style="display: flex; align-items: center; justify-content: center; padding: 32px 16px;">
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Loading…
          </p>
        </div>
      {:else if error}
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;">
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-destructive); margin: 0;">
            Couldn't load bandwidth history
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            Something went wrong loading this chart. Try again, or check the server logs if this keeps happening.
          </p>
        </div>
      {:else if destinations.length === 0}
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; text-align: center;">
          <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin: 0;">
            No destinations recorded
          </p>
          <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
            This device hasn't been observed talking to anything yet.
          </p>
        </div>
      {:else}
        <ul style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px;">
          {#each destinations as dest, i (dest.label + i)}
            <li style="display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 40px; padding: 8px 16px;">
              <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg);">
                {dest.label}
              </span>
              <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted);">
                {formatBytes(dest.bytes)}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </CardContent>
  </Card>
</section>
