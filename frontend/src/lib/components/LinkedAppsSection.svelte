<script lang="ts">
  import { onMount } from 'svelte';
  import { getLinkedApps } from '$lib/api';

  interface LinkedApp {
    id: string;
    name: string;
    icon_url: string;
    target_url: string;
    [key: string]: unknown;
  }

  let linkedApps = $state<LinkedApp[]>([]);

  onMount(async () => {
    try {
      linkedApps = (await getLinkedApps()) as LinkedApp[];
    } catch {
      linkedApps = [];
    }
  });
</script>

<section style="margin-top: 24px; margin-bottom: 48px;">
  {#if linkedApps.length > 0}
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px;">
      {#each linkedApps as app (app.id)}
        <a
          href={app.target_url}
          target="_blank"
          rel="noopener noreferrer"
          style="display: flex; align-items: center; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px; text-decoration: none; color: var(--color-fg);"
        >
          <img src={app.icon_url} alt="" style="width: 40px; height: 40px; border-radius: 6px;" />
          <span style="font-size: 14px; font-weight: 500; line-height: 1.4;">{app.name}</span>
        </a>
      {/each}
    </div>
  {:else}
    <div
      style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px;"
    >
      <h2 style="font-size: 28px; font-weight: 700; line-height: 1.15; color: var(--color-fg); margin: 0 0 16px 0;">
        No linked apps yet
      </h2>
      <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted); margin: 0;">
        Linked apps will appear here once a third-party module is configured.
      </p>
    </div>
  {/if}
</section>
