/**
 * `cue playbook` — list / inspect research templates (搭子).
 * Mirrors GET /templates and GET /templates/{id} of the Python client.
 */

import { loadConfig } from '../config.js';
import { EXIT } from '../errors.js';
import { requestJson } from '../http.js';
import { normalizeTemplateId } from './research.js';

export interface PlaybookOptions {
  base?: string;
  json?: boolean;
  mode?: string;
  includeSystem?: boolean;
}

interface ListResponse {
  data?: { items?: unknown[] } | unknown[];
  templates?: unknown[];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

export async function listTemplates(opts: PlaybookOptions = {}): Promise<number> {
  const cfg = loadConfig();
  const base = opts.base?.trim() || cfg.base;
  const mode = opts.mode ?? 'is_me';
  const includeSystem = opts.includeSystem ? 'true' : 'false';

  const data = await requestJson<ListResponse>({
    method: 'GET',
    endpoint: `/templates?mode=${encodeURIComponent(mode)}&include_system=${includeSystem}`,
    apiKey: cfg.apiKey || undefined,
    base,
    timeoutMs: 30_000,
  });

  let items: unknown[] = [];
  if (Array.isArray(data)) items = data;
  else {
    const payload = asRecord(data?.data);
    if (Array.isArray(data?.data)) items = data?.data as unknown[];
    else if (payload && Array.isArray(payload.items)) items = payload.items;
    else if (Array.isArray(data?.templates)) items = data?.templates as unknown[];
  }

  if (opts.json) {
    console.log(JSON.stringify(items, null, 2));
    return EXIT.OK;
  }

  if (items.length === 0) {
    console.log('(没有搭子)');
    return EXIT.OK;
  }

  for (const item of items) {
    const rec = asRecord(item);
    if (!rec) continue;
    const id = typeof rec.template_id === 'string' ? rec.template_id : String(rec.id ?? '?');
    const title = typeof rec.title === 'string' ? rec.title : '(无标题)';
    console.log(`${id}\t${title}`);
  }
  return EXIT.OK;
}

export async function getTemplate(id: string, opts: PlaybookOptions = {}): Promise<number> {
  const cfg = loadConfig();
  const base = opts.base?.trim() || cfg.base;
  const templateId = normalizeTemplateId(id);
  const data = await requestJson<unknown>({
    method: 'GET',
    endpoint: `/templates/${encodeURIComponent(templateId)}`,
    apiKey: cfg.apiKey || undefined,
    base,
    timeoutMs: 30_000,
  });
  const payload = asRecord(data);
  const body = payload && asRecord(payload.data) ? payload.data : data;
  console.log(opts.json ? JSON.stringify(body, null, 2) : JSON.stringify(body, null, 2));
  return EXIT.OK;
}
