import { create } from 'zustand';
import { ClipItem, PrefillData, fetchClips, fetchPrefill } from './api';
import { Viewport } from './lib/viewport';
import { frameCache } from './lib/frameCache';
import { LabelStatus } from './lib/labelModel';
import { ToolKind } from './lib/hotkeys';

export interface OverlayToggles {
  ghostTrajectory: boolean;
  ghostEvents: boolean;
  showAllEvents: boolean;
  calibration: boolean;
}

export interface AnnotatorState {
  clips: ClipItem[];
  selectedClipId: string | null;
  prefill: PrefillData | null;
  currentFrame: number;
  playing: boolean;
  viewport: Viewport;
  overlays: OverlayToggles;
  ghostAllowed: boolean;
  blindToggle: boolean;
  loupeEnabled: boolean;
  altHeld: boolean;
  loadingClips: boolean;
  loadingPrefill: boolean;
  error: string | null;
  armedTool: ToolKind | null;
  selectedPin: { kind: ToolKind } | null;
  autoAdvance: boolean;
  annotatorName: string;

  // Actions
  loadClips: (retries?: number) => Promise<void>;
  selectClip: (clipId: string) => Promise<void>;
  setCurrentFrame: (frame: number | ((prev: number) => number)) => void;
  setPlaying: (playing: boolean) => void;
  togglePlaying: () => void;
  setViewport: (vp: Viewport | ((prev: Viewport) => Viewport)) => void;
  toggleOverlay: (key: keyof OverlayToggles) => void;
  setGhostAllowed: (allowed: boolean) => void;
  setBlindToggle: (blind: boolean) => void;
  toggleLoupe: () => void;
  setAltHeld: (held: boolean) => void;
  setArmedTool: (tool: ToolKind | null) => void;
  setSelectedPin: (pin: { kind: ToolKind } | null) => void;
  setAutoAdvance: (enabled: boolean) => void;
  setAnnotatorName: (name: string) => void;
  updateClipLabelStatus: (clipId: string, status: LabelStatus) => void;
  selectPrevClip: () => void;
  selectNextClip: () => void;
}

export const useAnnotatorStore = create<AnnotatorState>((set, get) => ({
  clips: [],
  selectedClipId: null,
  prefill: null,
  currentFrame: 0,
  playing: false,
  viewport: { scale: 1.0, offsetX: 0, offsetY: 0 },
  overlays: {
    ghostTrajectory: true,
    ghostEvents: true,
    showAllEvents: false,
    calibration: true,
  },
  ghostAllowed: true, // Default true; later prompt uses it for blind mode
  blindToggle: false,
  loupeEnabled: false,
  altHeld: false,
  loadingClips: false,
  loadingPrefill: false,
  error: null,
  armedTool: null,
  selectedPin: null,
  autoAdvance: true,
  annotatorName: 'vedant',

  setArmedTool: (tool) => set({ armedTool: tool }),
  setSelectedPin: (pin) => set({ selectedPin: pin }),
  setBlindToggle: (blindToggle) => set({ blindToggle }),
  setAutoAdvance: (autoAdvance) => set({ autoAdvance }),
  setAnnotatorName: (annotatorName) => set({ annotatorName }),
  updateClipLabelStatus: (clipId, status) =>
    set((state) => ({
      clips: state.clips.map((c) =>
        c.clip_id === clipId ? { ...c, label_status: status } : c
      ),
    })),

  loadClips: async (retries = 5) => {
    set({ loadingClips: true, error: null });
    try {
      const clips = await fetchClips();
      set({ clips, loadingClips: false, error: null });
      // Automatically select first clip if none selected
      const currentSelected = get().selectedClipId;
      if (!currentSelected && clips.length > 0) {
        void get().selectClip(clips[0].clip_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (retries > 0) {
        // Retry in 1.5s in case backend is still starting up
        setTimeout(() => {
          void get().loadClips(retries - 1);
        }, 1500);
      } else {
        set({ error: msg, loadingClips: false });
      }
    }
  },

  selectClip: async (clipId: string) => {
    const { clips, selectedClipId } = get();
    if (selectedClipId === clipId) return;

    frameCache.setClip(clipId);
    set({
      selectedClipId: clipId,
      currentFrame: 0,
      playing: false,
      prefill: null,
      loadingPrefill: true,
    });

    const clip = clips.find((c) => c.clip_id === clipId);
    if (clip) {
      frameCache.prefetch(clipId, 0, clip.frame_count);
    }

    try {
      const prefill = await fetchPrefill(clipId);
      // Ensure we haven't switched clips while waiting
      if (get().selectedClipId === clipId) {
        set({ prefill, loadingPrefill: false });
      }
    } catch (err) {
      console.warn(`Failed to fetch prefill for ${clipId}:`, err);
      if (get().selectedClipId === clipId) {
        set({ prefill: null, loadingPrefill: false });
      }
    }
  },

  setCurrentFrame: (updater) => {
    const { currentFrame, selectedClipId, clips } = get();
    const clip = clips.find((c) => c.clip_id === selectedClipId);
    const maxFrame = clip ? clip.frame_count - 1 : 0;

    let target = typeof updater === 'function' ? updater(currentFrame) : updater;
    target = Math.max(0, Math.min(maxFrame, target));

    if (target !== currentFrame) {
      set({ currentFrame: target });
      if (selectedClipId && clip) {
        frameCache.prefetch(selectedClipId, target, clip.frame_count);
      }
    }
  },

  setPlaying: (playing) => set({ playing }),

  togglePlaying: () => set((state) => ({ playing: !state.playing })),

  setViewport: (updater) =>
    set((state) => ({
      viewport: typeof updater === 'function' ? updater(state.viewport) : updater,
    })),

  toggleOverlay: (key) =>
    set((state) => ({
      overlays: {
        ...state.overlays,
        [key]: !state.overlays[key],
      },
    })),

  setGhostAllowed: (ghostAllowed) => set({ ghostAllowed }),

  toggleLoupe: () => set((state) => ({ loupeEnabled: !state.loupeEnabled })),

  setAltHeld: (altHeld) => set({ altHeld }),

  selectPrevClip: () => {
    const { clips, selectedClipId, selectClip } = get();
    if (clips.length === 0) return;
    const currentIndex = clips.findIndex((c) => c.clip_id === selectedClipId);
    const prevIndex = currentIndex <= 0 ? clips.length - 1 : currentIndex - 1;
    void selectClip(clips[prevIndex].clip_id);
  },

  selectNextClip: () => {
    const { clips, selectedClipId, selectClip } = get();
    if (clips.length === 0) return;
    const currentIndex = clips.findIndex((c) => c.clip_id === selectedClipId);
    const nextIndex = currentIndex >= clips.length - 1 ? 0 : currentIndex + 1;
    void selectClip(clips[nextIndex].clip_id);
  },
}));
