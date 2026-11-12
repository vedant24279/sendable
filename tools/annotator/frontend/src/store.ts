import { create } from 'zustand';
import {
  ClipItem,
  PrefillData,
  fetchClips,
  fetchPrefill,
  fetchLibraryInfo,
  markClipOpened,
  hideClip,
  uploadVideoFile,
} from './api';
import { Viewport } from './lib/viewport';
import { frameCache } from './lib/frameCache';
import { LabelStatus } from './lib/labelModel';
import { ToolKind } from './lib/hotkeys';
import { CalibrationPointName } from './lib/calibConstants';
import { filterAllowedVideoFile } from './lib/libraryUtils';

export interface OverlayToggles {
  ghostTrajectory: boolean;
  ghostEvents: boolean;
  showAllEvents: boolean;
  calibration: boolean;
}

export interface UploadResultItem {
  name: string;
  status: 'added' | 'duplicate' | 'error';
  message: string;
}

export interface UploadState {
  uploading: boolean;
  currentIdx: number;
  total: number;
  currentFile: string;
  progressPct: number;
  results: UploadResultItem[];
  showResultsModal: boolean;
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
  calibrationMode: boolean;
  selectedCalibPoint: CalibrationPointName | null;
  loupeMag: 8 | 16;
  libraryFolder: string;
  libraryCount: number;
  activeTab: 'recents' | 'library' | 'debug';
  showAllRecents: boolean;
  filePickerTrigger: number;
  isDraggingFiles: boolean;
  uploadState: UploadState;

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
  updateClipHasGtCalibration: (clipId: string, hasGt: boolean) => void;
  selectPrevClip: () => void;
  selectNextClip: () => void;
  toggleCalibrationMode: () => void;
  setCalibrationMode: (enabled: boolean) => void;
  setSelectedCalibPoint: (point: CalibrationPointName | null) => void;
  cycleCalibLoupe: () => void;
  setActiveTab: (tab: 'recents' | 'library' | 'debug') => void;
  setShowAllRecents: (showAll: boolean) => void;
  hideClipAction: (clipId: string) => Promise<void>;
  triggerOpenFilePicker: () => void;
  setIsDraggingFiles: (isDragging: boolean) => void;
  uploadFiles: (files: File[]) => Promise<void>;
  dismissUploadModal: () => void;
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
  calibrationMode: false,
  selectedCalibPoint: 'bat_L',
  loupeMag: 8,
  libraryFolder: '',
  libraryCount: 0,
  activeTab: 'recents',
  showAllRecents: false,
  filePickerTrigger: 0,
  isDraggingFiles: false,
  uploadState: {
    uploading: false,
    currentIdx: 0,
    total: 0,
    currentFile: '',
    progressPct: 0,
    results: [],
    showResultsModal: false,
  },

  setActiveTab: (activeTab) => set({ activeTab }),
  setShowAllRecents: (showAllRecents) => set({ showAllRecents }),
  setIsDraggingFiles: (isDraggingFiles) => set({ isDraggingFiles }),
  dismissUploadModal: () =>
    set((state) => ({
      uploadState: { ...state.uploadState, showResultsModal: false },
    })),
  triggerOpenFilePicker: () =>
    set((state) => ({ filePickerTrigger: state.filePickerTrigger + 1 })),
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
  updateClipHasGtCalibration: (clipId, hasGt) =>
    set((state) => ({
      clips: state.clips.map((c) =>
        c.clip_id === clipId ? { ...c, has_gt_calibration: hasGt } : c
      ),
    })),
  toggleCalibrationMode: () =>
    set((state) => {
      const nextMode = !state.calibrationMode;
      return {
        calibrationMode: nextMode,
        armedTool: null,
        selectedPin: null,
        loupeEnabled: nextMode ? true : state.loupeEnabled,
        loupeMag: nextMode ? 8 : state.loupeMag,
        selectedCalibPoint: nextMode
          ? (state.selectedCalibPoint || 'bat_L')
          : state.selectedCalibPoint,
      };
    }),
  setCalibrationMode: (calibrationMode) =>
    set((state) => ({
      calibrationMode,
      armedTool: null,
      selectedPin: null,
      loupeEnabled: calibrationMode ? true : state.loupeEnabled,
      loupeMag: calibrationMode ? 8 : state.loupeMag,
      selectedCalibPoint: calibrationMode
        ? (state.selectedCalibPoint || 'bat_L')
        : state.selectedCalibPoint,
    })),
  setSelectedCalibPoint: (selectedCalibPoint) => set({ selectedCalibPoint }),
  cycleCalibLoupe: () =>
    set((state) => {
      if (!state.loupeEnabled) {
        return { loupeEnabled: true, loupeMag: 8 };
      }
      if (state.loupeMag === 8) {
        return { loupeEnabled: true, loupeMag: 16 };
      }
      return { loupeEnabled: false, loupeMag: 8 };
    }),

  loadClips: async (retries = 5) => {
    set({ loadingClips: true, error: null });
    try {
      const [clips, libInfo] = await Promise.all([
        fetchClips(),
        fetchLibraryInfo().catch(() => ({ folder: '', count: 0 })),
      ]);
      set({
        clips,
        libraryFolder: libInfo.folder,
        libraryCount: libInfo.count,
        loadingClips: false,
        error: null,
      });
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

  hideClipAction: async (clipId: string) => {
    try {
      await hideClip(clipId);
      set((state) => ({
        clips: state.clips.filter((c) => c.clip_id !== clipId),
      }));
      const { selectedClipId, clips, selectClip } = get();
      if (selectedClipId === clipId) {
        const remaining = clips.filter((c) => c.clip_id !== clipId);
        if (remaining.length > 0) {
          void selectClip(remaining[0].clip_id);
        } else {
          set({ selectedClipId: null, prefill: null });
        }
      }
    } catch (err) {
      console.error(`Failed to hide clip ${clipId}:`, err);
    }
  },

  selectClip: async (clipId: string) => {
    const { clips, selectedClipId } = get();
    if (selectedClipId === clipId) return;

    // Mark opened on backend
    void markClipOpened(clipId);

    const nowIso = new Date().toISOString();
    frameCache.setClip(clipId);
    set((state) => ({
      selectedClipId: clipId,
      currentFrame: 0,
      playing: false,
      prefill: null,
      loadingPrefill: true,
      clips: state.clips.map((c) =>
        c.clip_id === clipId ? { ...c, last_opened_at: nowIso } : c
      ),
    }));

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

  uploadFiles: async (files: File[]) => {
    if (files.length === 0) return;

    set({
      uploadState: {
        uploading: true,
        currentIdx: 0,
        total: files.length,
        currentFile: files[0].name,
        progressPct: 0,
        results: [],
        showResultsModal: true,
      },
    });

    let firstClipId: string | null = null;
    const results: UploadResultItem[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      set((state) => ({
        uploadState: {
          ...state.uploadState,
          currentIdx: i + 1,
          currentFile: file.name,
          progressPct: 0,
        },
      }));

      if (!filterAllowedVideoFile(file.name)) {
        results.push({
          name: file.name,
          status: 'error',
          message: 'Unsupported video extension (allowed: mp4, mov, mkv, avi, m4v, webm)',
        });
        set((state) => ({
          uploadState: {
            ...state.uploadState,
            results: [...results],
          },
        }));
        continue;
      }

      try {
        const res = await uploadVideoFile(file, (pct) => {
          set((state) => ({
            uploadState: {
              ...state.uploadState,
              progressPct: pct,
            },
          }));
        });

        if (res.status === 'added') {
          results.push({ name: file.name, status: 'added', message: 'Added' });
        } else {
          results.push({ name: file.name, status: 'duplicate', message: 'Already in library' });
        }

        if (!firstClipId && res.entry?.clip_id) {
          firstClipId = res.entry.clip_id;
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        results.push({ name: file.name, status: 'error', message: msg });
      }

      set((state) => ({
        uploadState: {
          ...state.uploadState,
          results: [...results],
        },
      }));
    }

    set((state) => ({
      uploadState: {
        ...state.uploadState,
        uploading: false,
      },
      activeTab: 'recents',
    }));

    // Refresh clips and recents
    await get().loadClips();

    // When all uploads finish, open the first added or duplicate clip and refresh Recents
    if (firstClipId) {
      void get().selectClip(firstClipId);
    }
  },
}));
