/**
 * `cue doctor` — environment self-check (no side effects).
 * Prints a JSON report: runtime, credential source, connectivity to
 * GET /tools/capabilities. Exit 0 when key present AND API reachable.
 */

import { API_KEY_PAGE, configPath, loadConfig, maskKey } from '../config.js';
import { requestJson } from '../http.js';

export interface DoctorOptions {
  base?: string;
}

export async function doctor(opts: DoctorOptions = {}): Promise<number> {
  const cfg = loadConfig();
  const base = opts.base?.trim() || cfg.base;
  const started = Date.now();
  let connectivity: Record<string, unknown>;

  try {
    await requestJson({
      method: 'GET',
      endpoint: '/tools/capabilities',
      apiKey: cfg.apiKey || undefined,
      base,
      timeoutMs: 15_000,
    });
    connectivity = { ok: true, latencyMs: Date.now() - started };
  } catch (err) {
    connectivity = { ok: false, latencyMs: Date.now() - started, error: err instanceof Error ? err.message : String(err) };
  }

  const report = {
    node: process.version,
    platform: process.platform,
    cliVersion: '1.0.0',
    configFile: cfg.filePath ?? configPath(),
    apiKey: cfg.apiKey ? maskKey(cfg.apiKey) : null,
    base,
    connectivity,
    apiKeyPage: API_KEY_PAGE,
  };
  console.log(JSON.stringify(report, null, 2));
  return cfg.apiKey && connectivity.ok === true ? 0 : 1;
}
