import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLabelStore } from './labelStore';
import { useAnnotatorStore } from './store';
import * as api from './api';
import { emptyLabel, placeEvent, setImpactType, setLastVisible, Label } from './lib/labelModel';

describe('useLabelStore', () => {
  const mockClip = {
    clip_id: 'clip_01',
    path: 'backend/_tracker_work/jobs/clip_01/input.mp4',
    fps: 30,
    frame_count: 90,
    width: 1920,
    height: 1080,
    ball_type: 'white' as const,
    has_results: true,
    has_calibration: true,
    label_status: 'none' as const,
    split: 'dev' as const,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    useAnnotatorStore.setState({
      clips: [mockClip, { ...mockClip, clip_id: 'clip_02' }],
      prefill: null,
    });
    useLabelStore.setState({
      label: null,
      savedLabel: null,
      dirty: false,
      saveState: 'idle',
      saveError: null,
      issues: [],
      canUndo: false,
      canRedo: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads a clip: creates emptyLabel when no saved label exists', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);

    await useLabelStore.getState().load('clip_01', 'alice');

    const state = useLabelStore.getState();
    expect(state.label).toBeDefined();
    expect(state.label?.clip_id).toBe('clip_01');
    expect(state.label?.annotator).toBe('alice');
    expect(state.label?.ball_colour).toBe('white');
    expect(state.savedLabel).toBeNull();
    expect(state.dirty).toBe(false);
  });

  it('loads a clip: adopts existing saved label when present', async () => {
    const existing = emptyLabel(mockClip, null, 'bob');
    existing.status = 'draft';
    existing.release = { frame: 5, x: 800, y: 400 };
    vi.spyOn(api, 'getLabel').mockResolvedValue(existing);

    await useLabelStore.getState().load('clip_01');

    const state = useLabelStore.getState();
    expect(state.label).toEqual(existing);
    expect(state.savedLabel).toEqual(existing);
    expect(state.dirty).toBe(false);
  });

  it('applies edits, manages undo/redo stack, and marks dirty', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    await useLabelStore.getState().load('clip_01');

    expect(useLabelStore.getState().canUndo).toBe(false);

    // 1. Place release
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'release', 5, 800, 400, { ghostVisible: false })
    );

    expect(useLabelStore.getState().label?.release).toEqual({ frame: 5, x: 800, y: 400 });
    expect(useLabelStore.getState().dirty).toBe(true);
    expect(useLabelStore.getState().canUndo).toBe(true);
    expect(useLabelStore.getState().canRedo).toBe(false);

    // 2. Place bounce
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'bounce', 15, 850, 500, { ghostVisible: false })
    );
    expect(useLabelStore.getState().label?.bounce).toBeDefined();

    // 3. Undo
    useLabelStore.getState().undo();
    expect(useLabelStore.getState().label?.bounce).toBeNull();
    expect(useLabelStore.getState().label?.release).toBeDefined();
    expect(useLabelStore.getState().canRedo).toBe(true);

    // 4. Redo
    useLabelStore.getState().redo();
    expect(useLabelStore.getState().label?.bounce).toBeDefined();
    expect(useLabelStore.getState().canRedo).toBe(false);
  });

  it('debounces autosave (3 edits within 1s results in 1 save call after 1500ms)', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    const putSpy = vi.spyOn(api, 'putLabel').mockImplementation(async (_id, l) => l);

    await useLabelStore.getState().load('clip_01');

    // 3 edits within 1 second
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'release', 5, 800, 400, { ghostVisible: false })
    );
    vi.advanceTimersByTime(300);

    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'bounce', 15, 850, 500, { ghostVisible: false })
    );
    vi.advanceTimersByTime(300);

    useLabelStore.getState().apply((prev) => setLastVisible(prev, 30));
    vi.advanceTimersByTime(300); // 900ms total elapsed so far

    // At 900ms, no save should have happened yet (debounce is 1500ms from last edit)
    expect(putSpy).not.toHaveBeenCalled();

    // Advance by another 1500ms to trigger autosave
    await vi.advanceTimersByTimeAsync(1500);

    expect(putSpy).toHaveBeenCalledTimes(1);
    expect(useLabelStore.getState().saveState).toBe('saved');
    expect(useLabelStore.getState().dirty).toBe(false);
  });

  it('does NOT trigger autosave when status is "final"', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    const putSpy = vi.spyOn(api, 'putLabel').mockImplementation(async (_id, l) => l);

    await useLabelStore.getState().load('clip_01');

    // Make status final manually
    useLabelStore.getState().apply((prev) => ({ ...prev, status: 'final' }));
    putSpy.mockClear();

    // Make another edit while status is final
    useLabelStore.getState().apply((prev) => ({ ...prev, notes: 'Some final notes' }));

    await vi.advanceTimersByTimeAsync(3000);

    // Should NOT have run autosave
    expect(putSpy).not.toHaveBeenCalled();
  });

  it('flushes pending autosave on clip switch', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    const putSpy = vi.spyOn(api, 'putLabel').mockImplementation(async (_id, l) => l);

    await useLabelStore.getState().load('clip_01');

    // Edit clip_01
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'release', 5, 800, 400, { ghostVisible: false })
    );
    expect(useLabelStore.getState().dirty).toBe(true);

    // Switch to clip_02 immediately (before 1500ms debounce expires)
    await useLabelStore.getState().load('clip_02');

    // clip_01 pending changes should have been flushed!
    expect(putSpy).toHaveBeenCalledTimes(1);
    expect(putSpy).toHaveBeenCalledWith('clip_01', expect.objectContaining({ clip_id: 'clip_01' }));
    expect(useLabelStore.getState().label?.clip_id).toBe('clip_02');
  });

  it('revision counter prevents save response from overwriting newer local edits', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);

    let resolveSave: ((label: Label) => void) | null = null;
    vi.spyOn(api, 'putLabel').mockImplementation(() => {
      return new Promise((resolve) => {
        resolveSave = resolve;
      });
    });

    await useLabelStore.getState().load('clip_01');

    // 1. Edit 1
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'release', 5, 800, 400, { ghostVisible: false })
    );

    // Trigger saveDraft
    const savePromise = useLabelStore.getState().saveDraft();

    // 2. While save is in flight, user makes Edit 2
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'bounce', 15, 850, 500, { ghostVisible: false })
    );

    // Now resolve the in-flight save response from Edit 1
    const edit1Label = { ...useLabelStore.getState().label!, bounce: null };
    resolveSave!(edit1Label);
    await savePromise;

    // The newer local edit (with bounce) must NOT have been overwritten!
    expect(useLabelStore.getState().label?.bounce).toBeDefined();
    expect(useLabelStore.getState().dirty).toBe(true);
  });

  it('save failure sets saveState "error" and preserves dirty true', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    vi.spyOn(api, 'putLabel').mockRejectedValue(new Error('Network timeout'));

    await useLabelStore.getState().load('clip_01');
    useLabelStore.getState().apply((prev) =>
      placeEvent(prev, 'release', 5, 800, 400, { ghostVisible: false })
    );

    await useLabelStore.getState().saveDraft();

    expect(useLabelStore.getState().saveState).toBe('error');
    expect(useLabelStore.getState().saveError).toContain('Network timeout');
    expect(useLabelStore.getState().dirty).toBe(true);
  });

  it('finalize with validation errors makes NO API call and keeps issues', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    const putSpy = vi.spyOn(api, 'putLabel');

    await useLabelStore.getState().load('clip_01');

    // Incomplete draft (missing release, bounce, etc.)
    const success = await useLabelStore.getState().finalize();

    expect(success).toBe(false);
    expect(putSpy).not.toHaveBeenCalled();
    expect(useLabelStore.getState().issues.length).toBeGreaterThan(0);
    expect(useLabelStore.getState().issues.some((i) => i.severity === 'error')).toBe(true);
  });

  it('finalize with valid label and warnings does NOT block and calls PUT with status "final"', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    const putSpy = vi.spyOn(api, 'putLabel').mockImplementation(async (_id, l) => l);

    await useLabelStore.getState().load('clip_01');

    // Set up a complete label that has a warning (release frame > 20)
    useLabelStore.getState().apply((prev) => {
      let l: Label = {
        ...prev,
        split: 'dev',
        ball_colour: 'white',
        batter_hand: 'right',
        bowler_type: 'pace',
        lighting: 'bright',
        calibration_gt: {
          points: {
            bat_L: [778.0, 434.0],
            bat_R: [1083.0, 430.0],
            bowl_L: [739.0, 764.0],
            bowl_R: [1115.0, 768.0],
            bat_stump: [936.0, 426.0],
            bowl_stump: [922.0, 784.0],
          },
          source: 'system_verified',
          residual_px: 2.5,
          updated_at: new Date().toISOString(),
        },
      };
      l = placeEvent(l, 'release', 22, 800, 400, { ghostVisible: false }); // triggers release > 20 warning
      l = placeEvent(l, 'bounce', 30, 850, 500, { ghostVisible: false });
      l = setImpactType(l, 'bat');
      l = placeEvent(l, 'impact', 32, 900, 450, { ghostVisible: false });
      l = setLastVisible(l, 45);
      return l;
    });

    const issuesBefore = useLabelStore.getState().issues;
    expect(issuesBefore.some((i) => i.severity === 'warning')).toBe(true);
    expect(issuesBefore.some((i) => i.severity === 'error')).toBe(false);

    // Finalize should succeed despite the warning!
    const success = await useLabelStore.getState().finalize();

    expect(success).toBe(true);
    expect(putSpy).toHaveBeenCalledTimes(1);
    expect(putSpy).toHaveBeenCalledWith('clip_01', expect.objectContaining({ status: 'final' }));
    expect(useLabelStore.getState().label?.status).toBe('final');
  });

  it('flags label, appending note and setting status "flagged"', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    await useLabelStore.getState().load('clip_01');

    useLabelStore.getState().flag('Pitch calibration off');
    expect(useLabelStore.getState().label?.status).toBe('flagged');
    expect(useLabelStore.getState().label?.notes).toBe('Pitch calibration off');

    useLabelStore.getState().flag('Camera shook at release');
    expect(useLabelStore.getState().label?.notes).toBe('Pitch calibration off\nCamera shook at release');
  });

  it('reopens a finalized label back to draft', async () => {
    vi.spyOn(api, 'getLabel').mockResolvedValue(null);
    await useLabelStore.getState().load('clip_01');

    useLabelStore.getState().apply((prev) => ({ ...prev, status: 'final' }));
    expect(useLabelStore.getState().label?.status).toBe('final');

    useLabelStore.getState().reopen();
    expect(useLabelStore.getState().label?.status).toBe('draft');
  });
});
