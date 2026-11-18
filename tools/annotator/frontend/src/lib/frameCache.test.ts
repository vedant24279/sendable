import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FrameCache } from './frameCache';

describe('FrameCache recovery and abort isolation', () => {
  const originalFetch = globalThis.fetch;
  const originalCreateImageBitmap = globalThis.createImageBitmap;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.createImageBitmap = originalCreateImageBitmap;
  });

  it('retries with cache: reload when createImageBitmap fails on a corrupt cached response', async () => {
    const cache = new FrameCache();
    const fakeBitmap = { width: 100, height: 100, close: vi.fn() } as unknown as ImageBitmap;
    const cacheModes: Array<RequestCache | undefined> = [];

    globalThis.fetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      cacheModes.push(init?.cache);
      const bytes = init?.cache === 'reload' ? 'good' : 'corrupt';
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob([bytes], { type: 'image/jpeg' }),
      } as Response;
    }) as typeof fetch;

    globalThis.createImageBitmap = vi.fn(async (blob: ImageBitmapSource) => {
      const text = await (blob as Blob).text();
      if (text === 'corrupt') {
        throw new DOMException('Could not decode image', 'EncodingError');
      }
      return fakeBitmap;
    }) as typeof createImageBitmap;

    const loaded = await cache.loadFrame('c_6017cc47', 3);
    expect(loaded).toBe(fakeBitmap);
    expect(cacheModes).toEqual(['default', 'reload']);
    expect(cache.hasFrame('c_6017cc47', 3)).toBe(true);
  });

  it('retries with cache: reload when the first HTTP response is not ok', async () => {
    const cache = new FrameCache();
    const fakeBitmap = { width: 10, height: 10, close: vi.fn() } as unknown as ImageBitmap;

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500 } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(['ok'], { type: 'image/jpeg' }),
      } as Response) as typeof fetch;

    globalThis.createImageBitmap = vi.fn(async () => fakeBitmap) as typeof createImageBitmap;

    const loaded = await cache.loadFrame('c_6017cc47', 3);
    expect(loaded).toBe(fakeBitmap);
  });

  it('does not return a stale aborted in-flight entry when returning to a clip', async () => {
    const cache = new FrameCache();
    const fakeBitmap = { width: 10, height: 10, close: vi.fn() } as unknown as ImageBitmap;
    let firstReject!: (err: unknown) => void;

    globalThis.fetch = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            firstReject = reject;
          }),
      )
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(['ok'], { type: 'image/jpeg' }),
      } as Response) as typeof fetch;

    globalThis.createImageBitmap = vi.fn(async () => fakeBitmap) as typeof createImageBitmap;

    cache.setClip('clipA');
    const p1 = cache.loadFrame('clipA', 3);
    cache.setClip('clipB'); // aborts clipA's controller synchronously
    cache.setClip('clipA');
    const p2 = cache.loadFrame('clipA', 3);
    firstReject(new DOMException('Aborted', 'AbortError'));

    expect(await p1).toBeNull();
    expect(await p2).toBe(fakeBitmap);
  });
});
