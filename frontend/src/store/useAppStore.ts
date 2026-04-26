import { create } from 'zustand';
import type { ActorRole, Issue } from '../types';

const STORAGE_KEYS = {
  darkMode: 'isDarkMode',
  actorRole: 'actorRole',
  actorId: 'actorId',
};

const DEFAULT_ACTOR_IDS: Record<ActorRole, string> = {
  admin: '3b0d4d88-2f30-4e97-81d3-2bb8d0a55a11',
  volunteer: '9dc43c4f-7c3d-4fc2-8564-89e8e96abfa2',
};

export interface AppStore {
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  actorRole: ActorRole;
  actorId: string;
  setActor: (role: ActorRole, id: string) => void;
  lastExtractedIssue: Issue | null;
  setLastExtractedIssue: (issue: Issue | null) => void;
}

function readStoredRole(): ActorRole {
  const storedRole = localStorage.getItem(STORAGE_KEYS.actorRole);
  return storedRole === 'admin' ? 'admin' : 'volunteer';
}

function readStoredActorId(role: ActorRole): string {
  return localStorage.getItem(STORAGE_KEYS.actorId) || DEFAULT_ACTOR_IDS[role];
}

function readStoredDarkMode(): boolean {
  return localStorage.getItem(STORAGE_KEYS.darkMode) === 'true';
}

function applyDarkMode(isDarkMode: boolean): void {
  if (isDarkMode) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

function syncActorStorage(role: ActorRole, actorId: string): void {
  localStorage.setItem(STORAGE_KEYS.actorRole, role);
  localStorage.setItem(STORAGE_KEYS.actorId, actorId);
}

const initialRole = readStoredRole();
const initialActorId = readStoredActorId(initialRole);
const initialDarkMode = readStoredDarkMode();

syncActorStorage(initialRole, initialActorId);
applyDarkMode(initialDarkMode);

export const useAppStore = create<AppStore>((set) => ({
  isDarkMode: initialDarkMode,
  actorRole: initialRole,
  actorId: initialActorId,
  lastExtractedIssue: null,
  toggleDarkMode: () =>
    set((state) => {
      const nextDarkMode = !state.isDarkMode;
      localStorage.setItem(STORAGE_KEYS.darkMode, String(nextDarkMode));
      applyDarkMode(nextDarkMode);
      return { isDarkMode: nextDarkMode };
    }),
  setActor: (role, id) => {
    const nextActorId = id.trim() || DEFAULT_ACTOR_IDS[role];
    syncActorStorage(role, nextActorId);
    set({ actorRole: role, actorId: nextActorId });
  },
  setLastExtractedIssue: (issue) => set({ lastExtractedIssue: issue }),
}));

export function getDefaultActorId(role: ActorRole): string {
  return DEFAULT_ACTOR_IDS[role];
}
