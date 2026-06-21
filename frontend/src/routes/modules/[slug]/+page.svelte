<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { apiGet, listModules } from '$lib/api';
  import { goto } from '$app/navigation';

  interface ModuleListItem {
    id: string;
    display_name: string;
    enabled: boolean;
    ui_route?: string | null;
  }

  let authenticated = $state(false);
  let checking = $state(true);
  let displayName = $state<string | null>(null);

  const slug = $derived($page.params.slug);

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
      try {
        const modules = (await listModules()) as ModuleListItem[];
        displayName = modules.find((m) => m.id === slug)?.display_name ?? null;
      } catch {
        displayName = null;
      }
    }
  });
</script>

<svelte:head>
  <title>{displayName ?? slug} · Innkeeper</title>
</svelte:head>

{#if authenticated}
  <main style="padding: 24px;">
    <h1 style="font-size: 28px; font-weight: 700; line-height: 1.15; color: var(--color-fg); margin: 0;">
      {displayName ?? slug}
    </h1>
  </main>
{/if}
