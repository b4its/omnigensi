/**
 * Non-blocking notifications and confirmations.
 *
 * `alert()`/`confirm()` block the JS thread and render as unstylable system
 * dialogs inside mobile WebViews, so every user-facing message goes through
 * this store instead.
 */

export type ToastKind = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

export interface ConfirmRequest {
  id: number;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  destructive: boolean;
  resolve: (value: boolean) => void;
}

const TOAST_TTL_MS = 5000;

class NotifyStore {
  toasts = $state<Toast[]>([]);
  confirmRequest = $state<ConfirmRequest | null>(null);

  private nextId = 1;
  private timers = new Map<number, ReturnType<typeof setTimeout>>();

  private push(kind: ToastKind, message: string): number {
    const id = this.nextId++;
    this.toasts = [...this.toasts, { id, kind, message }];
    const timer = setTimeout(() => this.dismiss(id), TOAST_TTL_MS);
    this.timers.set(id, timer);
    return id;
  }

  success(message: string): number {
    return this.push('success', message);
  }

  error(message: string): number {
    return this.push('error', message);
  }

  info(message: string): number {
    return this.push('info', message);
  }

  warning(message: string): number {
    return this.push('warning', message);
  }

  /** Surface an unknown thrown value without leaking "undefined". */
  fromError(err: unknown, fallback = 'Something went wrong'): number {
    const message =
      err instanceof Error && err.message ? err.message : typeof err === 'string' ? err : fallback;
    return this.error(message);
  }

  dismiss(id: number): void {
    const timer = this.timers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
    this.toasts = this.toasts.filter((t) => t.id !== id);
  }

  /**
   * Promise-based replacement for `window.confirm`.
   * Resolves false if another confirmation is already open (last wins is
   * worse: it would strand the first promise forever).
   */
  confirm(options: {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    destructive?: boolean;
  }): Promise<boolean> {
    if (this.confirmRequest) {
      this.settle(false);
    }
    return new Promise<boolean>((resolve) => {
      this.confirmRequest = {
        id: this.nextId++,
        title: options.title,
        message: options.message,
        confirmLabel: options.confirmLabel ?? 'CONFIRM',
        cancelLabel: options.cancelLabel ?? 'CANCEL',
        destructive: options.destructive ?? true,
        resolve
      };
    });
  }

  settle(value: boolean): void {
    const pending = this.confirmRequest;
    this.confirmRequest = null;
    pending?.resolve(value);
  }
}

export const notify = new NotifyStore();
