<script lang="ts">
  import { onMount } from 'svelte';
  import { Alert, AlertTitle } from '$lib/components/ui/alert';
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
  import ShieldAlert from '@lucide/svelte/icons/shield-alert';
  import AlertTriangle from '@lucide/svelte/icons/alert-triangle';
  import Radio from '@lucide/svelte/icons/radio';
  import { listAlerts, ackAlert, ackAllAlerts } from '$lib/api';

  interface SecurityAlert {
    id: number;
    type: 'unknown_device' | 'malicious_ip' | 'suspicious_traffic' | 'unexpected_port';
    device_id: number | null;
    device_name?: string | null;
    created_at: string;
  }

  let alerts = $state<SecurityAlert[]>([]);
  let dismissAllOpen = $state(false);

  const iconByType: Record<SecurityAlert['type'], typeof ShieldAlert> = {
    unknown_device: Radio,
    malicious_ip: ShieldAlert,
    suspicious_traffic: AlertTriangle,
    unexpected_port: AlertTriangle,
  };

  function messageFor(alert: SecurityAlert): string {
    const name = alert.device_name ?? 'A device';
    switch (alert.type) {
      case 'unknown_device':
        return 'Unknown device joined the network';
      case 'malicious_ip':
        return `${name} contacted a known-malicious address`;
      case 'suspicious_traffic':
        return `${name} shows unusual traffic activity`;
      case 'unexpected_port':
        return `${name} has an unexpected open port`;
      default:
        return 'Security alert';
    }
  }

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

  async function load() {
    try {
      alerts = (await listAlerts()) as SecurityAlert[];
    } catch {
      alerts = [];
    }
  }

  onMount(load);

  async function handleDismiss(alertId: number) {
    alerts = alerts.filter((a) => a.id !== alertId);
    try {
      await ackAlert(alertId);
    } catch {
      // Best-effort: the row already left the local list; a reload will
      // re-surface it if the ack request actually failed server-side.
    }
  }

  async function handleDismissAllConfirm() {
    dismissAllOpen = false;
    alerts = [];
    try {
      await ackAllAlerts();
    } catch {
      // Best-effort, mirrors handleDismiss.
    }
  }
</script>

{#if alerts.length > 0}
  <Alert style="margin-bottom: 24px;">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px;">
      <AlertTitle style="font-size: 20px; font-weight: 600; line-height: 1.2;">Security Alerts</AlertTitle>
      {#if alerts.length >= 2}
        <button
          type="button"
          onclick={() => (dismissAllOpen = true)}
          style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-muted); background: none; border: none; cursor: pointer; min-height: 44px; min-width: 44px;"
        >
          Dismiss all
        </button>
      {/if}
    </div>
    <div style="display: flex; flex-direction: column; gap: 4px;">
      {#each alerts as alert (alert.id)}
        {@const Icon = iconByType[alert.type]}
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 40px; border-bottom: 1px solid var(--color-border); padding: 4px 0;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <Icon size={16} aria-hidden="true" color="var(--color-fg)" />
            <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-fg);">
              {messageFor(alert)}
            </span>
            <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted);">
              {formatRelativeTime(alert.created_at)}
            </span>
          </div>
          <button
            type="button"
            aria-label="Dismiss alert"
            onclick={() => handleDismiss(alert.id)}
            style="display: inline-flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; background: none; border: none; cursor: pointer; color: var(--color-muted);"
          >
            ×
          </button>
        </div>
      {/each}
    </div>
  </Alert>
{/if}

<AlertDialog bind:open={dismissAllOpen}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Dismiss all alerts?</AlertDialogTitle>
      <AlertDialogDescription>
        This marks all {alerts.length} current alerts as acknowledged. You can still find them in the activity log
        later.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel onclick={() => (dismissAllOpen = false)}>Cancel</AlertDialogCancel>
      <AlertDialogAction onclick={handleDismissAllConfirm}>Dismiss all</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
