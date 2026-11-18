/**
 * FrameCache manages fetching, decoding via createImageBitmap,
 * and maintaining an LRU of 60 ImageBitmaps per clip.
 * Also handles prefetching frames [n-3 .. n+10] and aborting stale fetches.
 */

import { frameUrl } from '../api';

const MAX_FRAMES_PER_CLIP = 60;
const RETRY_COOLDOWN_MS = 1500;

interface InFlightEntry {
  promise: Promise<ImageBitmap | null>;
  controller: AbortController;
}

export class FrameCache {
  private clipCaches = new Map<string, Map<number, ImageBitmap>>();
  private inFlight = new Map<string, InFlightEntry>();
  private abortControllers = new Map<string, Set<AbortController>>();
  private failedUntil = new Map<string, number>();
  private retryTimers = new Map<string, ReturnType<typeof setTimeout>>();
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

  private async fetchAndDecode(
    clipId: string,
    frame: number,
    signal: AbortSignal,
    cacheMode: RequestCache,
  ): Promise<ImageBitmap> {
    const res = await fetch(frameUrl(clipId, frame), { signal, cache: cacheMode });
    if (!res.ok) {
      throw new Error(`Failed to load frame ${frame}: HTTP ${res.status}`);
    }
    const blob = await res.blob();
    return await createImageBitmap(blob);
  }

  public async loadFrame(clipId: string, frame: number): Promise<ImageBitmap | null> {
    const clipMap = this.clipCaches.get(clipId);
    if (clipMap && clipMap.has(frame)) {
      return clipMap.get(frame)!;
    }

    const key = `${clipId}:${frame}`;
    const existing = this.inFlight.get(key);
    if (existing && !existing.controller.signal.aborted) {
      return existing.promise;
    }

    const retryAt = this.failedUntil.get(key);
    if (retryAt !== undefined && Date.now() < retryAt) {
      return null;
    }

    const controller = new AbortController();
    const controllers = this.abortControllers.get(clipId);
    controllers?.add(controller);

    const promise = (async () => {
      try {
        let bitmap: ImageBitmap;
        try {
          bitmap = await this.fetchAndDecode(clipId, frame, controller.signal, 'default');
        } catch (firstErr: unknown) {
          if (firstErr instanceof DOMException && firstErr.name === 'AbortError') {
            return null;
          }
          // Bypass a potentially poisoned browser HTTP cache entry (e.g. a truncated
          // JPEG cached earlier with immutable headers) and overwrite it on success.
          bitmap = await this.fetchAndDecode(clipId, frame, controller.signal, 'reload');
        }

        this.failedUntil.delete(key);
        const pendingTimer = this.retryTimers.get(key);
        if (pendingTimer !== undefined) {
          clearTimeout(pendingTimer);
          this.retryTimers.delete(key);
        }

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
        this.failedUntil.set(key, Date.now() + RETRY_COOLDOWN_MS);
        if (!this.retryTimers.has(key)) {
          const timer = setTimeout(() => {
            this.retryTimers.delete(key);
            this.failedUntil.delete(key);
            if (this.currentClipId === clipId) {
              this.notify();
            }
          }, RETRY_COOLDOWN_MS);
          this.retryTimers.set(key, timer);
        }
        return null;
      } finally {
        if (this.inFlight.get(key)?.controller === controller) {
          this.inFlight.delete(key);
        }
        controllers?.delete(controller);
      }
    })();

    this.inFlight.set(key, { promise, controller });
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
      const entry = this.inFlight.get(`${clipId}:${f}`);
      const active = entry !== undefined && !entry.controller.signal.aborted;
      if (!this.hasFrame(clipId, f) && !active) {
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
    this.failedUntil.clear();
    this.retryTimers.forEach((timer) => clearTimeout(timer));
    this.retryTimers.clear();
  }
}

export const frameCache = new FrameCache();
