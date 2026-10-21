const browser = typeof window !== 'undefined';

export interface DeviceFileRecord {
  filename: string;
  timestamp: string;
  status: 'SYNCED_TO_DISK' | 'DOWNLOADED_FALLBACK' | 'ERROR';
  sizeBytes?: number;
  mimeType?: string;
  message?: string;
}

class DeviceBridgeStore {
  directoryHandle = $state<any | null>(null);
  mountedFolderName = $state<string | null>(null);
  autoWriteEnabled = $state<boolean>(true);
  isSupported = $state<boolean>(false);
  writeHistory = $state<DeviceFileRecord[]>([]);

  constructor() {
    if (browser) {
      this.isSupported = 'showDirectoryPicker' in window;
    }
  }

  async mountLocalDirectory(): Promise<boolean> {
    if (!browser) return false;
    if (!this.isSupported) {
      alert("Browser does not support File System Access API. Standard file download will be used instead.");
      return false;
    }

    try {
      // @ts-ignore
      const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
      this.directoryHandle = handle;
      this.mountedFolderName = handle.name || 'Local Workspace';
      return true;
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error("Error mounting directory:", err);
      }
      return false;
    }
  }

  disconnectDirectory(): void {
    this.directoryHandle = null;
    this.mountedFolderName = null;
  }

  toggleAutoWrite(): void {
    this.autoWriteEnabled = !this.autoWriteEnabled;
  }

  async saveAgentFileToDevice(
    filename: string,
    base64Data: string,
    mimeType: string = 'application/octet-stream'
  ): Promise<{ success: boolean; mode: string; filename: string }> {
    if (!browser) return { success: false, mode: 'none', filename };

    const byteCharacters = atob(base64Data);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: mimeType });

    // Mode 1: Direct File System Access API
    if (this.directoryHandle && this.autoWriteEnabled) {
      try {
        const fileHandle = await this.directoryHandle.getFileHandle(filename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(byteArray);
        await writable.close();

        this.writeHistory.unshift({
          filename,
          timestamp: new Date().toLocaleTimeString(),
          status: 'SYNCED_TO_DISK',
          sizeBytes: byteArray.length,
          mimeType,
          message: `Directly synced to mounted folder [${this.mountedFolderName}]`,
        });

        return { success: true, mode: 'local_disk', filename };
      } catch (err: any) {
        console.warn("Direct disk write failed, reverting to browser download fallback:", err);
      }
    }

    // Mode 2: Browser download fallback
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      this.writeHistory.unshift({
        filename,
        timestamp: new Date().toLocaleTimeString(),
        status: 'DOWNLOADED_FALLBACK',
        sizeBytes: byteArray.length,
        mimeType,
        message: 'Saved via browser download trigger',
      });

      return { success: true, mode: 'browser_download', filename };
    } catch (err: any) {
      this.writeHistory.unshift({
        filename,
        timestamp: new Date().toLocaleTimeString(),
        status: 'ERROR',
        message: String(err),
      });
      return { success: false, mode: 'error', filename };
    }
  }

  clearHistory(): void {
    this.writeHistory = [];
  }
}

export const deviceBridge = new DeviceBridgeStore();
