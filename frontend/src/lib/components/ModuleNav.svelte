<script lang="ts">
  import { onMount } from 'svelte';
  import { listModules } from '$lib/api';

  interface ModuleListItem {
    id: string;
    display_name: string;
    enabled: boolean;
    ui_route?: string | null;
  }

  let modules = $state<ModuleListItem[]>([]);

  async function load() {
    try {
      modules = (await listModules()) as ModuleListItem[];
    } catch {
      modules = [];
    }
  }

  onMount(load);

  // Only enabled modules that declare a ui_route get a nav entry — disabled
  // modules render nothing at all (never grayed-out, per UI-SPEC's locked
  // interaction contract; their routes 404 so there is nothing to link to).
  const navEntries = $derived(modules.filter((m) => m.enabled && m.ui_route));
</script>

{#if navEntries.length > 0}
  <nav style="display: flex; flex-direction: column; gap: 4px;">
    {#each navEntries as module (module.id)}
      <a
        href={module.ui_route}
        style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); text-decoration: none; padding: 8px 0;"
      >
        {module.display_name}
      </a>
    {/each}
  </nav>
{/if}
