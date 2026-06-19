const API_BASE = import.meta.env.PUBLIC_API_URL ?? '';

export async function apiPost(path: string, body: unknown): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  });
  return res;
}

export async function apiGet(path: string): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
  });
  return res;
}

export async function listDevices(): Promise<unknown[]> {
  const res = await apiGet('/api/devices/');
  if (!res.ok) throw new Error('Failed to load devices');
  return res.json();
}

export async function registerDevice(payload: {
  identity_id: number;
  name: string;
  owner: string;
  type: string;
  trusted: boolean;
}): Promise<Response> {
  return apiPost('/api/devices/', payload);
}

export async function mergeDevice(identityId: number, targetDeviceId: number): Promise<Response> {
  return apiPost(`/api/devices/${identityId}/merge`, { target_device_id: targetDeviceId });
}

export function openTrafficStream(): EventSource {
  return new EventSource(`${API_BASE}/api/traffic/stream`, { withCredentials: true });
}

export async function getDeviceBandwidth(
  deviceId: number,
  start: string,
  end: string
): Promise<unknown> {
  const res = await apiGet(
    `/api/traffic/bandwidth/${deviceId}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  );
  if (!res.ok) throw new Error('Failed to load device bandwidth');
  return res.json();
}

export async function getNetworkBandwidth(view: 'daily' | 'weekly' | 'monthly'): Promise<unknown> {
  const res = await apiGet(`/api/traffic/bandwidth/network?view=${view}`);
  if (!res.ok) throw new Error('Failed to load network bandwidth');
  return res.json();
}

export async function getDeviceDestinations(deviceId: number): Promise<unknown> {
  const res = await apiGet(`/api/traffic/devices/${deviceId}/destinations`);
  if (!res.ok) throw new Error('Failed to load device destinations');
  return res.json();
}
