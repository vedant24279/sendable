import { useEffect, useRef } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import { frameCache } from '../lib/frameCache';
import { keyToAction } from '../lib/hotkeys';
import { computeGhostVisible } from '../lib/ghost';
import { placeEvent, setImpactType, setLastVisible, round1 } from '../lib/labelModel';

export function useHotkeys(): void {
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const clips = useAnnotatorStore((s) => s.clips);
  const currentFrame = useAnnotatorStore((s) => s.currentFrame);
  const setCurrentFrame = useAnnotatorStore((s) => s.setCurrentFrame);
  const playing = useAnnotatorStore((s) => s.playing);
  const togglePlaying = useAnnotatorStore((s) => s.togglePlaying);
  const setPlaying = useAnnotatorStore((s) => s.setPlaying);
  const toggleLoupe = useAnnotatorStore((s) => s.toggleLoupe);
  const setAltHeld = useAnnotatorStore((s) => s.setAltHeld);
  const selectPrevClip = useAnnotatorStore((s) => s.selectPrevClip);
  const selectNextClip = useAnnotatorStore((s) => s.selectNextClip);
  const setArmedTool = useAnnotatorStore((s) => s.setArmedTool);
  const setSelectedPin = useAnnotatorStore((s) => s.setSelectedPin);

  const clip = clips.find((c) => c.clip_id === selectedClipId);
  const frameCount = clip ? clip.frame_count : 0;
  const fps = clip ? clip.fps : 30.0;

  const currentFrameRef = useRef(currentFrame);
  currentFrameRef.current = currentFrame;

  const selectedClipIdRef = useRef(selectedClipId);
  selectedClipIdRef.current = selectedClipId;

  const frameCountRef = useRef(frameCount);
  frameCountRef.current = frameCount;

  // 1. Keyboard event listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName;

      // 1. Check annotation actions via keyToAction helper
      const action = keyToAction({
        key: e.key,
        code: e.code,
        ctrlKey: e.ctrlKey,
        shiftKey: e.shiftKey,
        altKey: e.altKey,
        targetTag,
      });

      if (action) {
        e.preventDefault();
        const aStore = useAnnotatorStore.getState();
        const lStore = useLabelStore.getState();
        const gv = computeGhostVisible(aStore);

        switch (action.type) {
          case 'armTool':
            setArmedTool(action.tool);
            break;
          case 'disarm':
            setArmedTool(null);
            setSelectedPin(null);
            break;
          case 'setLastVisible':
            lStore.apply((prev) => setLastVisible(prev, currentFrameRef.current, { ghostVisible: gv }));
            break;
          case 'setImpactType':
            lStore.apply((prev) => setImpactType(prev, action.impactType, { ghostVisible: gv }));
            break;
          case 'undo':
            lStore.undo();
            break;
          case 'redo':
            lStore.redo();
            break;
          case 'saveDraft':
            void lStore.saveDraft();
            break;
          case 'finalize':
            void (async () => {
              const ok = await lStore.finalize();
              if (ok && useAnnotatorStore.getState().autoAdvance) {
                const { clips: allClips, selectedClipId: currId, selectClip } = useAnnotatorStore.getState();
                const currIdx = allClips.findIndex((c) => c.clip_id === currId);
                for (let i = 1; i < allClips.length; i++) {
                  const nextIdx = (currIdx + i) % allClips.length;
                  if (allClips[nextIdx].label_status !== 'final') {
                    void selectClip(allClips[nextIdx].clip_id);
                    break;
                  }
                }
              }
            })();
            break;
          case 'nudge': {
            const pin = aStore.selectedPin;
            if (pin && lStore.label) {
              const pt = lStore.label[pin.kind];
              const f = pt?.frame;
              if (pt && typeof f === 'number' && pt.x != null && pt.y != null) {
                const nx = round1(pt.x + action.dx);
                const ny = round1(pt.y + action.dy);
                lStore.apply((prev) => placeEvent(prev, pin.kind, f, nx, ny, { ghostVisible: gv }));
              }
            }
            break;
          }
        }
        return;
      }

      // Ignore if user is typing in an input or select
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      // Alt key hold for loupe
      if (e.key === 'Alt') {
        setAltHeld(true);
        return;
      }

      // Loupe toggle
      if (e.key === 'l' || e.key === 'L') {
        toggleLoupe();
        return;
      }

      // Clip navigation
      if (e.key === '[') {
        e.preventDefault();
        selectPrevClip();
        return;
      }
      if (e.key === ']') {
        e.preventDefault();
        selectNextClip();
        return;
      }

      // Space = play/pause at 0.25x speed
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlaying();
        return;
      }

      const total = frameCountRef.current;
      if (total <= 0) return;

      const curr = currentFrameRef.current;
      const cid = selectedClipIdRef.current;

      let delta = 0;
      if (e.key === 'ArrowLeft') {
        delta = e.shiftKey ? -5 : -1;
      } else if (e.key === 'ArrowRight') {
        delta = e.shiftKey ? 5 : 1;
      } else if (e.key === 'Home') {
        e.preventDefault();
        setCurrentFrame(0);
        return;
      } else if (e.key === 'End') {
        e.preventDefault();
        setCurrentFrame(total - 1);
        return;
      }

      if (delta !== 0) {
        e.preventDefault();
        const target = Math.max(0, Math.min(total - 1, curr + delta));

        // When key repeating, do not skip frames that are not loaded yet
        if (e.repeat && cid) {
          if (!frameCache.hasFrame(cid, target)) {
            // Still waiting for frame to load; don't skip ahead
            return;
          }
        }

        setCurrentFrame(target);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Alt') {
        setAltHeld(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [
    setCurrentFrame,
    togglePlaying,
    toggleLoupe,
    setAltHeld,
    selectPrevClip,
    selectNextClip,
    setArmedTool,
    setSelectedPin,
  ]);

  // 2. Playback loop at 0.25x speed
  useEffect(() => {
    if (!playing || frameCount <= 0 || !selectedClipId) return;

    // 0.25x playback speed: interval = 1000 / (fps * 0.25)
    const intervalMs = 1000 / (fps * 0.25);

    const timer = setInterval(() => {
      const curr = currentFrameRef.current;
      const next = curr + 1;
      if (next >= frameCountRef.current) {
        setPlaying(false);
      } else {
        // If next frame is loaded in cache, advance; otherwise wait for next tick
        if (frameCache.hasFrame(selectedClipId, next)) {
          setCurrentFrame(next);
        } else {
          // Trigger prefetch
          frameCache.prefetch(selectedClipId, next, frameCountRef.current);
        }
      }
    }, intervalMs);

    return () => clearInterval(timer);
  }, [playing, fps, frameCount, selectedClipId, setCurrentFrame, setPlaying]);
}
