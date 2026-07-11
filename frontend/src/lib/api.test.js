import { afterEach, describe, expect, test } from 'bun:test';

import {
  getForecast,
  getForecastResult,
  getLatestForecast,
  resumeForecast,
  submitForecast
} from './api.js';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('forecast API client', () => {
  test('submits every generated Markdown file as a repeated files multipart field', async () => {
    let captured;
    globalThis.fetch = async (url, options) => {
      captured = { url, options };
      return Response.json({
        success: true,
        data: { job_id: 'forecast_abcdef123456', status: 'queued' }
      }, { status: 202 });
    };

    const job = await submitForecast(
      [
        new File(['# Performance'], 'daily.md'),
        new File(['# Properties'], 'properties.md')
      ],
      { sourceNames: ['daily.xlsx', 'properties.csv'] }
    );

    expect(captured.url).toBe('/api/forecast');
    expect(captured.options.method).toBe('POST');
    expect(captured.options.headers).toBeUndefined();
    expect(captured.options.body.getAll('files').map((file) => file.name)).toEqual([
      'daily.md',
      'properties.md'
    ]);
    expect(captured.options.body.get('data_profile')).toBe('hotel');
    expect(captured.options.body.get('additional_context')).toContain('daily.xlsx');
    expect(captured.options.body.get('additional_context')).toContain('properties.csv');
    expect(job.job_id).toBe('forecast_abcdef123456');
  });

  test('keeps the single-file submit call compatible', async () => {
    let captured;
    globalThis.fetch = async (url, options) => {
      captured = { url, options };
      return Response.json({ success: true, data: { job_id: 'forecast_single' } }, { status: 202 });
    };

    await submitForecast(new File(['# Data'], 'daily.md'));

    expect(captured.options.body.getAll('files')).toHaveLength(1);
    expect(captured.options.body.get('project_name')).toContain('daily.md');
  });

  test('reads status and pending result responses', async () => {
    globalThis.fetch = async (url) => {
      if (url.endsWith('/result')) {
        return Response.json({ success: true, data: { status: 'running' } }, { status: 202 });
      }
      return Response.json({ success: true, data: { status: 'running', progress: 42 } });
    };

    expect((await getForecast('forecast_abcdef123456')).progress).toBe(42);
    expect((await getForecastResult('forecast_abcdef123456')).status).toBe(202);
  });

  test('loads the most recent completed forecast after a page reload', async () => {
    let capturedUrl;
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return Response.json({
        success: true,
        data: { job_id: 'forecast_latest1234', status: 'completed' }
      });
    };

    const job = await getLatestForecast();

    expect(capturedUrl).toBe('/api/forecast/latest');
    expect(job.status).toBe('completed');
  });

  test('resumes the existing forecast job without uploading another file', async () => {
    let captured;
    globalThis.fetch = async (url, options) => {
      captured = { url, options };
      return Response.json({
        success: true,
        data: { job_id: 'forecast_abcdef123456', status: 'queued' }
      }, { status: 202 });
    };

    const job = await resumeForecast('forecast_abcdef123456');

    expect(captured.url).toBe('/api/forecast/forecast_abcdef123456/resume');
    expect(captured.options).toEqual({ method: 'POST' });
    expect(job.status).toBe('queued');
  });

  test('surfaces backend error messages and status codes', async () => {
    globalThis.fetch = async () => Response.json(
      { success: false, error: 'Unauthorized' },
      { status: 401 }
    );

    try {
      await getForecast('forecast_abcdef123456');
      throw new Error('Expected request to fail');
    } catch (error) {
      expect(error.message).toBe('Unauthorized');
      expect(error.status).toBe(401);
    }
  });
});
