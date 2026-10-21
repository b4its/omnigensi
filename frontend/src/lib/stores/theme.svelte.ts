const browser = typeof window !== 'undefined';

class ThemeStore {
  mode = $state<'dark' | 'light'>('dark');
  crtScanlines = $state<boolean>(true);

  constructor() {
    if (browser) {
      const savedTheme = localStorage.getItem('omnigensi_theme') as 'dark' | 'light' | null;
      if (savedTheme === 'light' || savedTheme === 'dark') {
        this.mode = savedTheme;
      } else {
        this.mode = 'dark'; // Default to Cyber-Abyss
      }

      const savedCrt = localStorage.getItem('omnigensi_crt');
      if (savedCrt !== null) {
        this.crtScanlines = savedCrt === 'true';
      }

      this.applyTheme();
    }
  }

  toggleTheme() {
    this.mode = this.mode === 'dark' ? 'light' : 'dark';
    if (browser) {
      localStorage.setItem('omnigensi_theme', this.mode);
      this.applyTheme();
    }
  }

  toggleCrt() {
    this.crtScanlines = !this.crtScanlines;
    if (browser) {
      localStorage.setItem('omnigensi_crt', String(this.crtScanlines));
    }
  }

  private applyTheme() {
    if (browser) {
      document.documentElement.setAttribute('data-theme', this.mode);
    }
  }
}

export const themeStore = new ThemeStore();
