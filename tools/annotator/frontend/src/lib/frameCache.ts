/**
 * FrameCache manages fetching, decoding via createImageBitmap,
 * and maintaining an LRU of 60 ImageBitmaps per clip.
 * Also handles prefetching frames [n-3 .. n+10] and aborting stale fetches.
 */

import { frameUrl } from '../api';

const MAX_FRAMES_PER_CLIP = 60;

export class FrameCache {
  private clipCaches = new Map<string, Map<number, ImageBitmap>>();
  private inFlight = new Map<string, Promise<ImageBitmap | null>>();
  private abortControllers = new Map<string, Set<AbortController>>();
  private currentClipId: string | null = null;
  private listeners = new Set<() => void>();

  public setClip(clipId: string): void {
    if (this.currentClipId === clipId) return;

    // Abort pending fetches for previous clip
    if (this.currentClipId) {
      const controllers = this.abortControllers.get(this.currentClipId);
      if (controllers) {
        controllers.forEach((ac) => ac.abort());
        controllers.clear();
      }
    }

    this.currentClipId = clipId;
    if (!this.clipCaches.has(clipId)) {
      this.clipCaches.set(clipId, new Map());
    }
    if (!this.abortControllers.has(clipId)) {
      this.abortControllers.set(clipId, new Set());
    }
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    this.listeners.forEach((listener) => {
      try {
        listener();
      } catch (err) {
        console.error('FrameCache listener error:', err);
      }
    });
  }

  public hasFrame(clipId: string, frame: number): boolean {
    const clipMap = this.clipCaches.get(clipId);
    return clipMap ? clipMap.has(frame) : false;
  }

  /**
   * Retrieves frame bitmap if available; otherwise starts loading and returns null.
   */
  public getFrame(clipId: string, frame: number): ImageBitmap | null {
    this.setClip(clipId);
    const clipMap = this.clipCaches.get(clipId);
    if (clipMap && clipMap.has(frame)) {
      // LRU refresh: re-insert at end
      const bitmap = clipMap.get(frame)!;
      clipMap.delete(frame);
      clipMap.set(frame, bitmap);
      return bitmap;
    }

    // Trigger load
    void this.loadFrame(clipId, frame);
    return null;
  }

  public async loadFrame(clipId: string, frame: number): Promise<ImageBitmap | null> {
    const clipMap = this.clipCaches.get(clipId);
    if (clipMap && clipMap.has(frame)) {
      return clipMap.get(frame)!;
    }

    const key = `${clipId}:${frame}`;
    if (this.inFlight.has(key)) {
      return this.inFlight.get(key)!;
    }

    const controller = new AbortController();
    const controllers = this.abortControllers.get(clipId);
    controllers?.add(controller);

    const promise = (async () => {
      try {
        const res = await fetch(frameUrl(clipId, frame), {
          signal: controller.signal,
        });
        if (!res.ok) {
          throw new Error(`Failed to load frame ${frame}: HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const bitmap = await createImageBitmap(blob);

        // Put in LRU cache
        let targetMap = this.clipCaches.get(clipId);
        if (!targetMap) {
          targetMap = new Map();
          this.clipCaches.set(clipId, targetMap);
        }

        if (targetMap.size >= MAX_FRAMES_PER_CLIP) {
          const oldestKey = targetMap.keys().next().value;
          if (oldestKey !== undefined) {
            const oldBitmap = targetMap.get(oldestKey);
            oldBitmap?.close();
            targetMap.delete(oldestKey);
          }
        }

        targetMap.set(frame, bitmap);
        this.notify();
        return bitmap;
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return null;
        }
        console.warn(`Error loading frame ${frame} of ${clipId}:`, err);
        return null;
      } finally {
        this.inFlight.delete(key);
        controllers?.delete(controller);
      }
    })();

    this.inFlight.set(key, promise);
    return promise;
  }

  /**
   * Prefetches frames around current frame [n-3 .. n+10].
   */
  public prefetch(clipId: string, currentFrame: number, totalFrames: number): void {
    this.setClip(clipId);
    const start = Math.max(0, currentFrame - 3);
    const end = Math.min(totalFrames - 1, currentFrame + 10);

    for (let f = start; f <= end; f++) {
      if (!this.hasFrame(clipId, f) && !this.inFlight.has(`${clipId}:${f}`)) {
        void this.loadFrame(clipId, f);
      }
    }
  }

  public clear(): void {
    this.clipCaches.forEach((clipMap) => {
      clipMap.forEach((bitmap) => bitmap.close());
      clipMap.clear();
    });
    this.clipCaches.clear();
    this.abortControllers.forEach((set) => set.forEach((ac) => ac.abort()));
    this.abortControllers.clear();
    this.inFlight.clear();
  }
}

export const frameCache = new FrameCache();
