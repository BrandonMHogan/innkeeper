<script lang="ts">
  import { goto } from '$app/navigation';
  import { Eye, EyeOff, Loader2 } from '@lucide/svelte';
  import { apiPost } from '$lib/api';

  let password = $state('');
  let showPassword = $state(false);
  let loading = $state(false);
  let errorMessage = $state('');

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    errorMessage = '';

    loading = true;
    try {
      const res = await apiPost('/api/auth/login', { password });
      if (res.status === 401) {
        errorMessage = 'Incorrect password. Try again.';
        loading = false;
        return;
      }
      if (!res.ok) {
        errorMessage = 'Could not reach the Innkeeper API. Make sure the stack is running.';
        loading = false;
        return;
      }
      await goto('/dashboard');
    } catch {
      errorMessage = 'Could not reach the Innkeeper API. Make sure the stack is running.';
      loading = false;
    }
  }

  function toggleShowPassword() {
    showPassword = !showPassword;
  }
</script>

<svelte:head>
  <title>Innkeeper — Sign In</title>
</svelte:head>

<div
  style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100dvh; background: var(--color-background);"
>
  <div
    style="width: 400px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px;"
  >
    <h1 style="font-size: 28px; font-weight: 700; line-height: 1.15; margin: 0 0 8px 0; color: var(--color-fg);">
      Sign In
    </h1>
    <p style="font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--color-muted); margin: 0 0 16px 0;">
      Enter your dashboard password to continue.
    </p>

    <form onsubmit={handleSubmit}>
      <label
        for="password"
        style="display: block; font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg); margin-bottom: 8px;"
      >
        Password
      </label>
      <div style="position: relative; margin-bottom: 16px;">
        <input
          id="password"
          type={showPassword ? 'text' : 'password'}
          placeholder="Your dashboard password"
          bind:value={password}
          style="width: 100%; box-sizing: border-box; height: 44px; padding: 8px 40px 8px 12px; background: var(--color-background); border: 1px solid var(--color-border); border-radius: 6px; color: var(--color-fg); font-size: 14px;"
        />
        <button
          type="button"
          onclick={toggleShowPassword}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center;"
        >
          {#if showPassword}
            <EyeOff size={16} color="var(--color-muted)" />
          {:else}
            <Eye size={16} color="var(--color-muted)" />
          {/if}
        </button>
      </div>

      {#if errorMessage}
        <div
          role="alert"
          style="border: 1px solid var(--color-destructive); color: var(--color-destructive); border-radius: 6px; padding: 8px 12px; margin-bottom: 16px; font-size: 14px;"
        >
          {errorMessage}
        </div>
      {/if}

      <button
        type="submit"
        disabled={loading}
        aria-busy={loading}
        style="width: 100%; height: 44px; background: var(--color-accent-button-bg); color: var(--color-accent-fg); border: none; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; display: flex; align-items: center; justify-content: center;"
      >
        {#if loading}
          <Loader2 size={16} class="animate-spin" />
        {:else}
          Sign In
        {/if}
      </button>
    </form>
  </div>
</div>

<style>
  :global(.animate-spin) {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
</style>
