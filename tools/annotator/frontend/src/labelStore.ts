/**
 * Zustand store managing Label state, undo/redo history, issues, and debounced autosave.
 */

import { create } from 'zustand';
import { ClipMetaInput, Label, ReferenceDecision, emptyLabel } from './lib/labelModel';
import { validateLabel, Issue, ClipDimensions } from './lib/validate';
import { HistoryStack } from './lib/history';
import { getLabel, putLabel } from './api';
import { useAnnotatorStore } from './store';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export interface LabelStoreState {
  label: Label | null;
  savedLabel: Label | null;
  dirty: boolean;
  saveState: SaveState;
  saveError: string | null;
  issues: Issue[];
  canUndo: boolean;
  canRedo: boolean;

  // Actions
  load: (clipId: string, annotator?: string) => Promise<void>;
  apply: (fn: (prev: Label) => Label) => void;
  undo: () => void;
  redo: () => void;
  saveDraft: () => Promise<void>;
  finalize: () => Promise<boolean>;
  flag: (note: string) => void;
  reopen: () => void;
  flushPendingAutosave: () => Promise<void>;
  executeAutosave: (rev: number) => Promise<void>;
  syncReferenceDecision: (clipId: string, decision: ReferenceDecision | null) => void;
}

let localRevision = 0;
let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
let historyStack = new HistoryStack<Label>({} as Label);

export const useLabelStore = create<LabelStoreState>((set, get) => ({
  label: null,
  savedLabel: null,
  dirty: false,
  saveState: 'idle',
  saveError: null,
  issues: [],
  canUndo: false,
  canRedo: false,

  load: async (clipId: string, annotator = 'annotator_1') => {
    // 1. Flush any pending autosave for the current clip first
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    const currentLabel = get().label;
    if (currentLabel && currentLabel.status === 'draft' && get().dirty) {
      try {
        await putLabel(currentLabel.clip_id, currentLabel);
      } catch (err) {
        console.warn('Failed to flush autosave on clip switch:', err);
      }
    }

    // 2. Fetch existing label or create empty
    let loaded: Label | null = null;
    try {
      loaded = await getLabel(clipId);
    } catch (err) {
      console.warn(`Failed to fetch label for ${clipId}:`, err);
    }

    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === clipId);
    const prefill = useAnnotatorStore.getState().prefill;

    const clipMeta: ClipDimensions & ClipMetaInput = {
      clip_id: clipId,
      split: clip?.split,
      ball_type: clip?.ball_type,
      ball_colour_hint: clip?.ball_colour_hint,
      reference_decision: clip?.reference_decision,
      source_group: clip?.source_group,
      frame_count: clip?.frame_count,
      width: clip?.width,
      height: clip?.height,
    };

    const initialLabel: Label = loaded
      ? (clip?.reference_decision !== undefined
          ? { ...loaded, reference_decision: clip.reference_decision ?? null }
          : loaded)
      : emptyLabel(clipMeta, prefill, annotator);

    historyStack = new HistoryStack<Label>(initialLabel);
    localRevision = 0;

    const issues = validateLabel(initialLabel, clipMeta, initialLabel.status);

    set({
      label: initialLabel,
      savedLabel: loaded,
      dirty: false,
      saveState: 'idle',
      saveError: null,
      issues,
      canUndo: false,
      canRedo: false,
    });
  },

  apply: (fn: (prev: Label) => Label) => {
    const current = get().label;
    if (!current) return;

    const next = fn(current);
    if (next === current) return;

    historyStack.push(next);
    localRevision++;
    const rev = localRevision;

    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === next.clip_id);
    const issues = validateLabel(next, clip, next.status);

    set({
      label: next,
      dirty: true,
      issues,
      saveState: 'idle',
      saveError: null,
      canUndo: historyStack.canUndo,
      canRedo: historyStack.canRedo,
    });

    // Autosave: debounced 1500ms, only while status is draft
    if (next.status === 'draft') {
      if (autosaveTimer) {
        clearTimeout(autosaveTimer);
      }
      autosaveTimer = setTimeout(() => {
        void get().executeAutosave(rev);
      }, 1500);
    }
  },

  undo: () => {
    const previous = historyStack.undo();
    if (!previous) return;

    localRevision++;
    const rev = localRevision;

    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === previous.clip_id);
    const issues = validateLabel(previous, clip, previous.status);

    set({
      label: previous,
      dirty: true,
      issues,
      saveState: 'idle',
      saveError: null,
      canUndo: historyStack.canUndo,
      canRedo: historyStack.canRedo,
    });

    if (previous.status === 'draft') {
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = setTimeout(() => {
        void get().executeAutosave(rev);
      }, 1500);
    }
  },

  redo: () => {
    const next = historyStack.redo();
    if (!next) return;

    localRevision++;
    const rev = localRevision;

    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === next.clip_id);
    const issues = validateLabel(next, clip, next.status);

    set({
      label: next,
      dirty: true,
      issues,
      saveState: 'idle',
      saveError: null,
      canUndo: historyStack.canUndo,
      canRedo: historyStack.canRedo,
    });

    if (next.status === 'draft') {
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = setTimeout(() => {
        void get().executeAutosave(rev);
      }, 1500);
    }
  },

  saveDraft: async () => {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    const current = get().label;
    if (!current) return;

    set({ saveState: 'saving', saveError: null });
    localRevision++;
    const rev = localRevision;

    try {
      const saved = await putLabel(current.clip_id, current);
      if (localRevision === rev) {
        set({
          savedLabel: saved,
          dirty: false,
          saveState: 'saved',
        });
        useAnnotatorStore.getState().updateClipLabelStatus(saved.clip_id, saved.status);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        saveState: 'error',
        saveError: msg,
        dirty: true,
      });
    }
  },

  finalize: async () => {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    const current = get().label;
    if (!current) return false;

    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === current.clip_id);
    const issues = validateLabel(current, clip, 'final');
    const hasErrors = issues.some((i) => i.severity === 'error');

    if (hasErrors) {
      // With any error it makes NO API call and keeps the issues
      set({
        issues,
        saveError: 'Validation errors prevent finalizing label',
      });
      return false;
    }

    const finalLabel: Label = {
      ...current,
      status: 'final',
      updated_at: new Date().toISOString(),
    };

    set({ saveState: 'saving', saveError: null });
    localRevision++;
    const rev = localRevision;

    try {
      const saved = await putLabel(finalLabel.clip_id, finalLabel);
      historyStack.push(saved);
      if (localRevision === rev) {
        set({
          label: saved,
          savedLabel: saved,
          dirty: false,
          saveState: 'saved',
          issues,
          canUndo: historyStack.canUndo,
          canRedo: historyStack.canRedo,
        });
        useAnnotatorStore.getState().updateClipLabelStatus(saved.clip_id, saved.status);
      }
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        saveState: 'error',
        saveError: msg,
        dirty: true,
      });
      return false;
    }
  },

  flag: (note: string) => {
    const current = get().label;
    if (!current) return;

    const updatedNotes = current.notes
      ? `${current.notes}\n${note}`
      : note;

    const flagged: Label = {
      ...current,
      status: 'flagged',
      notes: updatedNotes,
      updated_at: new Date().toISOString(),
    };

    get().apply(() => flagged);
  },

  reopen: () => {
    const current = get().label;
    if (!current || current.status !== 'final') return;

    const reopened: Label = {
      ...current,
      status: 'draft',
      updated_at: new Date().toISOString(),
    };

    get().apply(() => reopened);
  },

  flushPendingAutosave: async () => {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    const current = get().label;
    if (current && current.status === 'draft' && get().dirty) {
      await get().saveDraft();
    }
  },

  executeAutosave: async (rev: number) => {
    const state = get();
    if (!state.label || state.label.status !== 'draft' || !state.dirty) {
      return;
    }

    set({ saveState: 'saving', saveError: null });
    const labelToSave = state.label;

    try {
      const saved = await putLabel(labelToSave.clip_id, labelToSave);
      if (localRevision === rev) {
        set({
          savedLabel: saved,
          dirty: false,
          saveState: 'saved',
        });
        useAnnotatorStore.getState().updateClipLabelStatus(saved.clip_id, saved.status);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        saveState: 'error',
        saveError: msg,
        dirty: true,
      });
    }
  },

  syncReferenceDecision: (clipId: string, decision: ReferenceDecision | null) => {
    const current = get().label;
    if (!current || current.clip_id !== clipId) return;
    const next: Label = {
      ...current,
      reference_decision: decision,
    };
    const clips = useAnnotatorStore.getState().clips;
    const clip = clips.find((c) => c.clip_id === clipId);
    const issues = validateLabel(next, clip, next.status);
    set({
      label: next,
      issues,
    });
  },
}));
