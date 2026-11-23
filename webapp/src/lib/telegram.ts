import type { TelegramUser } from '../types';

interface TelegramWebAppUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
}

interface TelegramBackButton {
  isVisible: boolean;
  show: () => void;
  hide: () => void;
  onClick: (callback: () => void) => void;
  offClick: (callback: () => void) => void;
}

interface TelegramHapticFeedback {
  impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
  notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
}

interface TelegramWebApp {
  initData?: string;
  initDataUnsafe?: {
    user?: TelegramWebAppUser;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  disableVerticalSwipes?: () => void;
  switchInlineQuery?: (query: string, chooseChatTypes?: string[]) => void;
  openTelegramLink?: (url: string) => void;
  BackButton?: TelegramBackButton;
  HapticFeedback?: TelegramHapticFeedback;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

function getWebApp(): TelegramWebApp | undefined {
  if (typeof window === 'undefined') return undefined;
  return window.Telegram?.WebApp;
}

export function initTelegramApp(): void {
  const webApp = getWebApp();
  if (!webApp) return;

  try {
    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor?.('#090f14');
    webApp.setBackgroundColor?.('#070b0e');
    webApp.disableVerticalSwipes?.();
  } catch {
    // Safely ignore if running in an older Telegram client or mock environment
  }
}

export function getTelegramUser(): TelegramUser {
  const user = getWebApp()?.initDataUnsafe?.user;
  if (!user || !user.first_name) {
    return {
      firstName: 'Олександр',
      initials: 'ОЛ',
      isTelegram: false,
    };
  }

  const firstChar = user.first_name.trim().charAt(0).toUpperCase();
  const secondChar = user.last_name
    ? user.last_name.trim().charAt(0).toUpperCase()
    : user.first_name.trim().charAt(1).toUpperCase();

  return {
    id: user.id,
    firstName: user.first_name,
    lastName: user.last_name,
    username: user.username,
    initials: `${firstChar}${secondChar}` || 'TG',
    isTelegram: true,
  };
}

export function hapticImpact(style: 'light' | 'medium' | 'heavy' = 'light'): void {
  try {
    getWebApp()?.HapticFeedback?.impactOccurred(style);
  } catch {
    // No-op outside Telegram
  }
}

export function hapticNotification(type: 'error' | 'success' | 'warning'): void {
  try {
    getWebApp()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    // No-op outside Telegram
  }
}

export function setBackButton(visible: boolean, onClick?: () => void): () => void {
  const backButton = getWebApp()?.BackButton;
  if (!backButton) {
    return () => {};
  }

  try {
    if (visible) {
      if (onClick) {
        backButton.onClick(onClick);
      }
      backButton.show();
    } else {
      backButton.hide();
    }
  } catch {
    // No-op outside Telegram
  }

  return () => {
    try {
      if (onClick) {
        backButton.offClick(onClick);
      }
      backButton.hide();
    } catch {
      // No-op outside Telegram
    }
  };
}

export function closeMiniApp(): void {
  const webApp = getWebApp();
  if (webApp) {
    try {
      webApp.close();
      return;
    } catch {
      // Fall through
    }
  }
}

export function shareChallenge(text: string): void {
  const webApp = getWebApp();
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(
    'https://t.me/DevOpsSandboxBot'
  )}&text=${encodeURIComponent(text)}`;

  if (webApp?.openTelegramLink) {
    try {
      webApp.openTelegramLink(shareUrl);
      return;
    } catch {
      // Fall through to browser fallback
    }
  }

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    void navigator.clipboard.writeText(text).catch(() => {});
  }
}
