/** Exit codes used across commands so callers (and agents) can branch. */
export const EXIT = {
  OK: 0,
  ERROR: 1,
  NO_CREDENTIALS: 2,
  BAD_INPUT: 3,
  NETWORK: 4,
  TIMEOUT: 5,
} as const;

export class CueError extends Error {
  readonly code: number;

  constructor(message: string, code: number = EXIT.ERROR) {
    super(message);
    this.name = 'CueError';
    this.code = code;
  }
}

export class CueApiError extends CueError {
  readonly status: number;
  readonly detail: string;
  readonly endpoint: string;

  constructor(status: number, detail: string, endpoint: string) {
    super(`Cue API ${status} on ${endpoint}: ${detail}`, status === 401 || status === 403 ? EXIT.NO_CREDENTIALS : EXIT.ERROR);
    this.name = 'CueApiError';
    this.status = status;
    this.detail = detail;
    this.endpoint = endpoint;
  }
}
