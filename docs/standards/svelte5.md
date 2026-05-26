# Svelte 5 Coding Standards — Innkeeper

HOW to write Svelte 5 and TypeScript code in this project. For library versions and quality gate commands, see `docs/architecture/tech-stack.md`.

---

## Runes

### `$state`
- Use for all reactive variables. Never use `writable()` stores or legacy `let` reactivity.
- Declare at the top of `<script>`, before `$derived` and `$effect`.
- Use `$state` only for values that genuinely change. Use `const` for values that never change.

```svelte
<script lang="ts">
  let count = $state(0);              // ✅ reactive
  const MAX = 100;                    // ✅ constant, not $state
  let items = $state<string[]>([]);   // ✅ typed array
</script>
```

### `$derived`
- Use for values computed from other state. Never compute in template expressions.
- If a value is used more than once in a template, it belongs in `$derived`.

```svelte
let filtered = $derived(items.filter(i => i.active));   // ✅ compute once
// ❌ never: {items.filter(i => i.active).map(...)}     // recomputes on every render
```

### `$effect`
- Minimize effects. If you can express it as `$derived`, use `$derived`.
- Use only for: DOM interactions, subscriptions, external side effects.
- Always return a cleanup function when the effect opens a connection or sets a listener.

```svelte
$effect(() => {
  const source = new EventSource('/api/events');
  source.onmessage = (e) => { data = JSON.parse(e.data); };
  return () => source.close();   // ✅ cleanup
});
```

### `$props`
- Destructure immediately with defaults.
- Mark bindable props explicitly with `$bindable()`.
- Do not mutate `$props` directly — they are read-only unless bound.

```svelte
let { label, value = $bindable(''), disabled = false } = $props<{
  label: string;
  value?: string;
  disabled?: boolean;
}>();
```

---

## Component Structure

Order within `<script lang="ts">`:
1. Imports
2. `$props()` destructuring
3. `$state` declarations
4. `$derived` declarations
5. `$effect` blocks
6. Event handlers and functions

Order in the file:
1. `<script lang="ts">`
2. Template markup
3. `<style>`

---

## State Sharing

- Colocate `$state` in the component if it is only used there.
- For state shared between components, create a module-level store in a `.svelte.ts` file.
- Never use `writable()`, `readable()`, or `derived()` from `svelte/store`.

**Store pattern:**
```typescript
// src/stores/devices.svelte.ts
let _devices = $state<Device[]>([]);
let _loading = $state(false);

export const deviceStore = {
    get devices() { return _devices; },
    get loading() { return _loading; },
    set(devices: Device[]) { _devices = devices; },
    setLoading(v: boolean) { _loading = v; },
};
```

```svelte
<!-- Usage in a component -->
<script lang="ts">
  import { deviceStore } from '$stores/devices.svelte';
</script>
{#each deviceStore.devices as device}...{/each}
```

---

## CSS

- Use Svelte `<style>` blocks for component-scoped styles.
- Global rules (resets, theme tokens, typography) go in `src/app.css`. Never repeat global rules in component styles.
- Use CSS custom properties for all theme values. Define all tokens in `src/app.css`.
- Prefer `rem` and `em` over `px` for sizes. Use `px` only for borders and shadows.
- Layout: CSS Grid for page-level layout; Flexbox for component-level alignment.
- No inline `style=` attributes. All styles in `<style>` blocks.

**Theming pattern:**
```css
/* src/app.css — define tokens once */
:root {
  --color-bg: hsl(220, 15%, 10%);
  --color-surface: hsl(220, 12%, 16%);
  --color-text: hsl(220, 10%, 90%);
  --color-accent: hsl(210, 90%, 60%);
  --radius-md: 8px;
  --shadow-sm: 0 1px 3px hsla(0, 0%, 0%, 0.3);
}

/* component — use tokens, never hardcode */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
```

**Visual standards:** Components must implement dark mode by default using the token system. Apply subtle micro-animations on interactive elements (`transition: opacity 0.15s ease`, `transform` on hover). Use glassmorphism (`backdrop-filter: blur(...)`) sparingly for modals and overlays. Style all inputs, scrollbars, and buttons — never use default browser elements.

---

## SSE (Server-Sent Events)

- Open SSE connections in `$effect`. Close them in the effect's cleanup.
- Always handle the `error` event. Reconnect with exponential backoff on unexpected close.
- Never open more than one SSE connection per data type.

```svelte
$effect(() => {
  let retryDelay = 1000;
  let source: EventSource;

  function connect() {
    source = new EventSource('/api/stream/devices');
    source.onmessage = (e) => { devices = JSON.parse(e.data); };
    source.onerror = () => {
      source.close();
      setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30_000);
    };
  }

  connect();
  return () => source?.close();
});
```

---

## API Calls

- Use `fetch` with `async/await`. No `.then()` chaining.
- Always manage loading and error state explicitly as `$state` variables alongside the data.
- Define TypeScript interfaces for all API response shapes before writing the fetch call.

```svelte
<script lang="ts">
  let data = $state<Device[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  async function loadDevices() {
    loading = true;
    error = null;
    try {
      const res = await fetch('/api/devices');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (e) {
      error = 'Failed to load devices. Please try again.';
    } finally {
      loading = false;
    }
  }
</script>
```

---

## Naming Conventions

| Thing | Convention | Example |
| :--- | :--- | :--- |
| Component files | `PascalCase.svelte` | `DeviceCard.svelte` |
| Store files | `camelCase.svelte.ts` | `deviceStore.svelte.ts` |
| Props | `camelCase` | `deviceId`, `isLoading` |
| Event handlers | `handle<Action>` | `handleSubmit`, `handleDelete` |
| CSS classes | `kebab-case` | `device-card`, `status-badge` |
| CSS custom properties | `--kebab-case` | `--color-primary`, `--radius-lg` |
| TypeScript interfaces | `PascalCase` | `Device`, `ApiResponse<T>` |

---

## TypeScript

- Enable strict mode. Never use `any` — use `unknown` and narrow, or define a type.
- Type all `$state` and `$derived` declarations: `let items = $state<Item[]>([])`.
- Type all function parameters and return values on exported functions.
- Prefer interfaces over type aliases for object shapes. Use type aliases for unions and primitives.

---

## Anti-Patterns

| ❌ Anti-Pattern | ✅ Correct Approach |
| :--- | :--- |
| `writable()` / `readable()` Svelte stores | Module-level rune stores (`.svelte.ts`) |
| `$effect` for state transforms | `$derived` |
| Inline event handler with logic: `onclick={() => { a(); b(); }}` | Extract to named `handleClick` function |
| Hardcoded colors/sizes in CSS | CSS custom property tokens |
| Mutating `$props` directly | Use `$bindable` for two-way binding |
| `<div style="...">` | CSS class in `<style>` block |
| TailwindCSS | Vanilla CSS unless user explicitly requests Tailwind |
| Multiple SSE connections for the same data | Single connection per data type |
