import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getLabel, putLabel, ApiValidationError } from './api';
import { emptyLabel } from './lib/labelModel';

describe('api client label endpoints', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('getLabel returns null on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    const res = await getLabel('missing_clip');
    expect(res).toBeNull();
  });

  it('getLabel returns label data on 200', async () => {
    const mockLabel = emptyLabel({ clip_id: 'c1' }, null, 'tester');
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockLabel,
    } as Response);

    const res = await getLabel('c1');
    expect(res).toEqual(mockLabel);
  });

  it('putLabel returns saved label on 200', async () => {
    const mockLabel = emptyLabel({ clip_id: 'c1' }, null, 'tester');
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', label: mockLabel }),
    } as Response);

    const res = await putLabel('c1', mockLabel);
    expect(res).toEqual(mockLabel);
  });

  it('putLabel throws ApiValidationError on 422 with parsed detail array', async () => {
    const pydanticErrors = {
      detail: [
        {
          type: 'value_error',
          loc: ['body', 'release'],
          msg: "release is required for status 'final'",
        },
        {
          type: 'value_error',
          loc: ['body', 'bounce'],
          msg: "bounce is required for status 'final'",
        },
      ],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => pydanticErrors,
    } as Response);

    const mockLabel = emptyLabel({ clip_id: 'c1' }, null, 'tester');

    try {
      await putLabel('c1', mockLabel);
      expect.unreachable('Should have thrown ApiValidationError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiValidationError);
      const apiErr = err as ApiValidationError;
      expect(apiErr.issues.length).toBe(2);
      expect(apiErr.issues[0]).toContain("release is required for status 'final'");
      expect(apiErr.issues[1]).toContain("bounce is required for status 'final'");
    }
  });

  it('putLabel throws ApiValidationError on 422 with string detail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Custom validation failed' }),
    } as Response);

    const mockLabel = emptyLabel({ clip_id: 'c1' }, null, 'tester');

    try {
      await putLabel('c1', mockLabel);
      expect.unreachable('Should have thrown ApiValidationError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiValidationError);
      const apiErr = err as ApiValidationError;
      expect(apiErr.issues).toEqual(['Custom validation failed']);
      expect(apiErr.message).toBe('Custom validation failed');
    }
  });
});
