<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet, listModules, toggleModule } from '$lib/api';
  import { Switch } from '$lib/components/ui/switch';
  import {
    AlertDialog,
    AlertDialogContent,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogAction,
    AlertDialogCancel,
  } from '$lib/components/ui/alert-dialog';

  interface ModuleListItem {
    id: string;
    display_name: string;
    enabled: boolean;
    ui_route?: string | null;
  }

  let authenticated = $state(false);
  let checking = $state(true);
  let modules = $state<ModuleListItem[]>([]);

  let confirmOpen = $state(false);
  let confirmModuleId = $state<string | null>(null);
  let confirmDisplayName = $state('');
  let confirmDependentCount = $state(0);

  async function load() {
    try {
      modules = (await listModules()) as ModuleListItem[];
    } catch {
      modules = [];
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
      await load();
    }
  });

  async function handleToggle(module: ModuleListItem) {
    if (module.enabled) {
      // Disabling — first call without confirm to check for dependents.
      const res = await toggleModule(module.id, false);
      if (!res.ok) return;
      const body = await res.json();
      if (body.requires_confirmation) {
        confirmModuleId = module.id;
        confirmDisplayName = module.display_name;
        confirmDependentCount = body.dependents?.length ?? 0;
        confirmOpen = true;
        return;
      }
      await load();
      return;
    }

    // Enabling never requires confirmation.
    await toggleModule(module.id, false);
    await load();
  }

  async function handleConfirmDisable() {
    confirmOpen = false;
    if (confirmModuleId === null) return;
    await toggleModule(confirmModuleId, true);
    confirmModuleId = null;
    await load();
  }
</script>

<svelte:head>
  <title>Module Settings · Innkeeper</title>
</svelte:head>

{#if authenticated}
  <main style="padding: 24px;">
    <h1 style="font-size: 28px; font-weight: 700; line-height: 1.15; color: var(--color-fg); margin: 0 0 16px 0;">
      Modules
    </h1>

    {#if modules.length === 0}
      <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted);">
        No modules installed
      </p>
    {:else}
      <div style="display: flex; flex-direction: column; gap: 8px;">
        {#each modules as module (module.id)}
          <div
            style="display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;"
          >
            <div style="display: flex; align-items: center; gap: 16px;">
              <Switch
                checked={module.enabled}
                onCheckedChange={() => handleToggle(module)}
                style={`--primary: ${module.enabled ? 'var(--color-accent)' : 'var(--color-muted)'};`}
              />
              <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
                {module.display_name}
              </span>
              <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: {module.enabled ? 'var(--color-accent)' : 'var(--color-muted)'};">
                {module.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <button
              type="button"
              onclick={() => handleToggle(module)}
              style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); background: var(--color-background); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 16px; min-height: 44px; cursor: pointer;"
            >
              {module.enabled ? 'Disable module' : 'Enable module'}
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </main>
{/if}

<AlertDialog bind:open={confirmOpen}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Disable {confirmDisplayName}?</AlertDialogTitle>
      <AlertDialogDescription>
        {confirmDependentCount} other module(s) depend on this and will also stop working. This won't delete any data.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel onclick={() => (confirmOpen = false)}>Cancel</AlertDialogCancel>
      <AlertDialogAction onclick={handleConfirmDisable}>Disable module</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
