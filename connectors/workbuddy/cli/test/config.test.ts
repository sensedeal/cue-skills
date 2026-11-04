import { describe, expect, it } from 'vitest';
import { configDir, maskKey } from '../src/config.js';
import { normalizeTemplateId } from '../src/commands/research.js';

describe('config', () => {
  it('honours CUE_HOME, else ~/.cue', () => {
    const original = process.env.CUE_HOME;
    process.env.CUE_HOME = '/tmp/cue-home';
    expect(configDir()).toBe('/tmp/cue-home');
    if (original === undefined) delete process.env.CUE_HOME;
    else process.env.CUE_HOME = original;
  });

  it('masks keys keeping only head and tail', () => {
    const masked = maskKey('sk-abcdefghijklmnop');
    expect(masked.startsWith('sk-')).toBe(true);
    expect(masked.endsWith('mnop')).toBe(true);
    expect(masked).not.toContain('cdefghij');
  });
});

describe('normalizeTemplateId', () => {
  it('prepends the template_ prefix only when missing', () => {
    expect(normalizeTemplateId('fnig0i')).toBe('template_fnig0i');
    expect(normalizeTemplateId('template_fnig0i')).toBe('template_fnig0i');
  });
});
