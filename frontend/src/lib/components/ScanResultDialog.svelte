<script lang="ts">
  import { Dialog, DialogContent, DialogHeader, DialogTitle } from '$lib/components/ui/dialog';
  import { getScanResult } from '$lib/api';

  interface ScanResultPort {
    port: number;
    flag: 'risky' | 'unexpected' | 'expected';
  }

  interface ScanResult {
    scanned_at: string | null;
    ports: ScanResultPort[];
  }

  let {
    device,
    open = $bindable(false),
  }: {
    device: { id: number; name: string };
    open: boolean;
  } = $props();

  let scanResult = $state<ScanResult | null>(null);
  let loadError = $state(false);

  const SERVICE_NAME_BY_PORT: Record<number, string> = {
    21: 'FTP',
    22: 'SSH',
    23: 'Telnet',
    53: 'DNS',
    80: 'HTTP',
    135: 'RPC',
    139: 'NetBIOS',
    443: 'HTTPS',
    445: 'SMB',
    512: 'rexec',
    513: 'rlogin',
    514: 'syslog',
    1433: 'MSSQL',
    1900: 'UPnP',
    3306: 'MySQL',
    3389: 'RDP',
    5900: 'VNC',
    7000: 'AirPlay',
    8008: 'Chromecast',
    8009: 'Chromecast',
  };

  function serviceName(port: number): string {
    return SERVICE_NAME_BY_PORT[port] ?? 'Unknown service';
  }

  const flagCopy: Record<ScanResultPort['flag'], string> = {
    risky: 'Risky — commonly exploited',
    unexpected: 'Unexpected for this device type',
    expected: 'Expected',
  };

  const flagColorVar: Record<ScanResultPort['flag'], string> = {
    risky: '--color-destructive',
    unexpected: '--color-warning',
    expected: '--color-muted',
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

  async function load() {
    loadError = false;
    scanResult = null;
    try {
      scanResult = await getScanResult(device.id);
    } catch {
      loadError = true;
    }
  }

  $effect(() => {
    if (open) {
      load();
    } else {
      scanResult = null;
      loadError = false;
    }
  });
</script>

<Dialog bind:open>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Scan Results — {device.name}</DialogTitle>
    </DialogHeader>

    {#if loadError}
      <div role="alert">
        <p style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin: 0 0 4px 0;">
          Scan couldn't complete
        </p>
        <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
          The device may be offline or unreachable. Try again, or check the capture service logs if this keeps
          happening.
        </p>
      </div>
    {:else if scanResult === null}
      <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
        Loading…
      </p>
    {:else if scanResult.ports.length === 0}
      <div>
        <p style="font-size: 20px; font-weight: 600; line-height: 1.2; color: var(--color-fg); margin: 0 0 8px 0;">
          Not yet scanned
        </p>
        <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0;">
          Run a scan to check this device for open ports and security issues.
        </p>
      </div>
    {:else}
      <div style="display: flex; flex-direction: column; gap: 4px;">
        {#each scanResult.ports as portInfo (portInfo.port)}
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 40px; border-bottom: 1px solid var(--color-border); padding: 4px 0;">
            <span style="font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
              {portInfo.port} ({serviceName(portInfo.port)})
            </span>
            <span style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var({flagColorVar[portInfo.flag]});">
              {flagCopy[portInfo.flag]}
            </span>
          </div>
        {/each}
      </div>
      {#if scanResult.scanned_at}
        <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 16px 0 0 0;">
          Last scanned {formatRelativeTime(scanResult.scanned_at)}
        </p>
      {/if}
    {/if}
  </DialogContent>
</Dialog>
