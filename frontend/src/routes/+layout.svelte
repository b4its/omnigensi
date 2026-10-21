<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { themeStore } from '$lib/stores/theme.svelte';
  import { deviceBridge } from '$lib/stores/deviceBridge.svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { auth } from '$lib/stores/auth.svelte';
  import ThemeToggle from '$lib/components/ui/ThemeToggle.svelte';
  import NotifyHost from '$lib/components/ui/NotifyHost.svelte';
  import {
    Activity,
    Server,
    Bot,
    Network,
    Terminal,
    HardDrive,
    ShieldCheck,
    FolderSync,
    Layers,
    Menu,
    X,
    LogOut,
    Loader2,
    History,
  } from 'lucide-svelte';

  let { children } = $props();

  let backendOnline = $state<boolean>(false);
  let mobileMenuOpen = $state<boolean>(false);

  const navItems = [
    { name: '[01] COMMAND CENTER', href: '/', icon: Activity },
    { name: '[02] OMNIROUTER VAULT', href: '/providers', icon: Server },
    { name: '[03] AGENT STUDIO', href: '/agents', icon: Bot },
    { name: '[04] GRAPH BUILDER', href: '/workflows', icon: Network },
    { name: '[05] EXECUTION DECK', href: '/playground', icon: Terminal },
    { name: '[06] RUN HISTORY', href: '/executions', icon: History },
  ];

  const isLoginRoute = $derived(page.url.pathname.startsWith('/login'));

  onMount(async () => {
    if (auth.authenticated === null) await auth.check();

    if (!auth.authenticated && !isLoginRoute) {
      const target = page.url.pathname + page.url.search;
      goto(`/login?redirect=${encodeURIComponent(target)}`, { replaceState: true });
    }
  });

  // A 401 from any request means the token is gone or expired.
  $effect(() => {
    const onUnauthorized = () => {
      auth.authenticated = false;
      if (!isLoginRoute) {
        const target = page.url.pathname + page.url.search;
        goto(`/login?redirect=${encodeURIComponent(target)}`, { replaceState: true });
      }
    };
    window.addEventListener('omnigensi:unauthorized', onUnauthorized);
    return () => window.removeEventListener('omnigensi:unauthorized', onUnauthorized);
  });

  async function handleLogout() {
    await auth.logout();
    goto('/login', { replaceState: true });
  }

  onMount(() => {
    const checkStatus = async () => {
      try {
        await api.checkHealth();
        backendOnline = true;
      } catch (e) {
        backendOnline = false;
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 8000);
    return () => clearInterval(interval);
  });
</script>

<div class="min-h-screen bg-blueprint flex flex-col {themeStore.crtScanlines ? 'crt-overlay' : ''}">
  <!-- Topbar HUD Header -->
  <header class="sticky top-0 z-40 border-b border-[var(--border-color)] bg-[var(--bg-surface)]/90 backdrop-blur-md px-4 py-2.5 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <!-- Mobile Menu Button -->
      {#if !isLoginRoute}
      <button
        type="button"
        onclick={() => mobileMenuOpen = !mobileMenuOpen}
        class="md:hidden p-2.5 border border-[var(--border-color)] text-[var(--accent-primary)] chamfer-sm"
        aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={mobileMenuOpen}
      >
        {#if mobileMenuOpen}<X class="w-4 h-4" />{:else}<Menu class="w-4 h-4" />{/if}
      </button>
      {/if}

      <!-- Logo & Branding -->
      <a href="/" class="flex items-center gap-2 group">
        <div class="w-8 h-8 chamfer-sm bg-[var(--accent-primary)] text-[var(--on-accent)] flex items-center justify-center font-hud font-black text-sm shadow-[var(--border-glow)]">
          Ω
        </div>
        <div class="flex flex-col">
          <span class="font-hud font-black text-sm md:text-base tracking-widest text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] transition-colors">
            OMNIGENSI
          </span>
          <span class="text-[9px] font-code tracking-wider text-[var(--accent-primary)]">
            AIaaS // DEVICE ORCHESTRATOR
          </span>
        </div>
      </a>
    </div>

    <!-- HUD Center & Status Badges -->
    <div class="flex items-center gap-3 font-code text-xs">
      <!-- Backend Status (compact on mobile, full label on lg) -->
      <div class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-sm border border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
        <span class="w-2 h-2 rounded-full {backendOnline ? 'bg-[var(--status-success)] animate-pulse' : 'bg-[var(--status-danger)]'}"></span>
        <span class="hidden lg:inline text-[11px] text-[var(--text-muted)]">CORE BACKEND:</span>
        <span class="font-bold text-[11px] {backendOnline ? 'text-[var(--status-success)]' : 'text-[var(--status-danger)]'}">
          {backendOnline ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      <!-- Local Device Bridge Status (desktop only: needs File System Access API) -->
      <div class="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-sm border border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
        <HardDrive class="w-3.5 h-3.5 {deviceBridge.directoryHandle ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}" />
        <span class="text-[11px] text-[var(--text-muted)]">HARDWARE BRIDGE:</span>
        {#if deviceBridge.directoryHandle}
          <span class="font-bold text-[var(--status-success)]">
            [{deviceBridge.mountedFolderName}]
          </span>
          <button
            type="button"
            onclick={() => deviceBridge.disconnectDirectory()}
            class="text-[10px] text-[var(--status-danger)] hover:underline ml-1"
          >
            DISCONNECT
          </button>
        {:else}
          <button
            type="button"
            onclick={() => deviceBridge.mountLocalDirectory()}
            class="text-[10px] font-bold text-[var(--accent-primary)] hover:underline"
          >
            [+ MOUNT LOCAL DISK]
          </button>
        {/if}
      </div>
    </div>

    <!-- Right Controls: Optical Mode Toggle -->
    <div class="flex items-center gap-2">
      <ThemeToggle />

      {#if auth.authenticated}
        <button
          type="button"
          onclick={handleLogout}
          class="p-2 border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--status-danger)] hover:border-[var(--status-danger)]/50 chamfer-sm"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut class="w-4 h-4" />
        </button>
      {/if}
    </div>
  </header>

  <div class="flex-1 flex">
    <!-- Cyberdeck Navigation Sidebar (Desktop) -->
    {#if !isLoginRoute}
    <aside class="hidden md:flex flex-col w-64 border-r border-[var(--border-color)] bg-[var(--bg-surface)]/80 backdrop-blur-sm p-3 gap-1">
      <div class="px-3 py-2 text-[10px] font-hud text-[var(--text-muted)] tracking-wider border-b border-[var(--border-color)]/50 mb-2">
        COMMAND DECK // NAVIGATION
      </div>

      {#each navItems as item}
        {@const isActive = page.url.pathname === item.href || (page.url.pathname.startsWith(item.href) && item.href !== '/')}
        <a
          href={item.href}
          class="flex items-center gap-2.5 px-3 py-2.5 rounded-sm font-hud text-xs tracking-wider transition-all duration-150 {isActive ? 'bg-[var(--accent-primary)] text-[var(--on-accent)] font-bold shadow-[var(--border-glow)] chamfer-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]'}"
        >
          <item.icon class="w-4 h-4 {isActive ? 'text-[var(--on-accent)]' : 'text-[var(--accent-primary)]'}" />
          <span>{item.name}</span>
        </a>
      {/each}

      <!-- Local Device Bridge Quick Panel in Sidebar -->
      <div class="mt-auto border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 p-3 chamfer-sm space-y-2">
        <div class="flex items-center justify-between text-[10px] font-hud text-[var(--text-primary)]">
          <span class="flex items-center gap-1.5 font-bold">
            <FolderSync class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
            DEVICE BRIDGE
          </span>
          <span class="text-[9px] font-code {deviceBridge.directoryHandle ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}">
            {deviceBridge.directoryHandle ? 'MOUNTED' : 'OFFLINE'}
          </span>
        </div>

        <p class="text-[11px] text-[var(--text-muted)] leading-tight">
          {#if deviceBridge.directoryHandle}
            Direct browser write active to <span class="text-[var(--text-primary)] font-semibold">{deviceBridge.mountedFolderName}</span>.
          {:else}
            Connect your local hard drive for autonomous .md, .docx & .pdf export.
          {/if}
        </p>

        <button
          type="button"
          onclick={() => deviceBridge.directoryHandle ? deviceBridge.disconnectDirectory() : deviceBridge.mountLocalDirectory()}
          class="w-full py-1.5 px-2 text-[10px] font-hud tracking-wider text-center border chamfer-sm transition-all {deviceBridge.directoryHandle ? 'border-[var(--status-danger)]/50 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10' : 'border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10'}"
        >
          {deviceBridge.directoryHandle ? 'DISCONNECT DISK' : 'MOUNT LOCAL FOLDER'}
        </button>
      </div>
    </aside>
    {/if}

    <!-- Mobile Drawer -->
    {#if mobileMenuOpen}
      <!-- Backdrop: tap outside to close -->
      <button
        type="button"
        aria-label="Close navigation menu"
        onclick={() => mobileMenuOpen = false}
        class="md:hidden fixed inset-0 top-0 z-40 bg-black/60 backdrop-blur-sm cursor-default"
      ></button>

      <div class="md:hidden fixed top-0 right-0 bottom-0 z-50 w-[85%] max-w-sm overflow-y-auto bg-[var(--bg-surface)] border-l border-[var(--border-color)] shadow-2xl">
        <div class="sticky top-0 flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
          <span class="font-hud font-bold text-xs tracking-wider text-[var(--text-primary)]">COMMAND DECK // NAVIGATION</span>
          <button
            type="button"
            onclick={() => (mobileMenuOpen = false)}
            class="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label="Close navigation menu"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <nav class="p-3 space-y-2">
          {#each navItems as item}
            <a
              href={item.href}
              onclick={() => (mobileMenuOpen = false)}
              class="flex items-center gap-3 p-3.5 rounded-sm font-hud text-xs border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 text-[var(--text-primary)] active:bg-[var(--accent-primary)]/15"
            >
              <item.icon class="w-4 h-4 text-[var(--accent-primary)]" />
              <span>{item.name}</span>
            </a>
          {/each}

          <!-- Mobile device bridge: download-only fallback on touch devices -->
          {#if !deviceBridge.isSupported}
            <div class="mt-2 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 p-3 chamfer-sm space-y-1.5">
              <div class="flex items-center gap-1.5 text-[10px] font-hud font-bold text-[var(--text-primary)]">
                <FolderSync class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                DEVICE BRIDGE
              </div>
              <p class="text-[11px] text-[var(--text-muted)] leading-tight">
                Direct disk write is unavailable on this device. Generated artifacts download via the browser instead.
              </p>
            </div>
          {/if}
        </nav>
      </div>
    {/if}

    <!-- Main Content Stage -->
    <main class="flex-1 p-4 md:p-6 overflow-y-auto max-w-7xl mx-auto w-full">
      {#if isLoginRoute || auth.authenticated}
        {@render children()}
      {:else}
        <!-- Do not mount pages before the session is known: each page fetches
             data on mount and would emit avoidable 401s. -->
        <div class="flex items-center justify-center py-24 gap-2 font-code text-xs text-[var(--text-muted)]">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>{auth.loading ? 'CHECKING SESSION...' : 'REDIRECTING TO SIGN IN...'}</span>
        </div>
      {/if}
    </main>
  </div>

  <!-- Global toast + confirmation layer (replaces alert/confirm) -->
  <NotifyHost />
</div>
