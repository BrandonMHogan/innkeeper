<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet } from '$lib/api';

  onMount(async () => {
    try {
      const res = await apiGet('/api/auth/me');
      if (res.ok) {
        await goto('/dashboard');
        return;
      }
    } catch {
      // fall through to /login
    }
    await goto('/login');
  });
</script>
