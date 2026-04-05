import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  cn,
  formatDate,
  formatDateTime,
  formatRelativeTime,
  formatBytes,
  formatMemoryGB,
  formatStorageTB,
  formatPercentage,
  truncate,
  capitalize,
  debounce,
  sleep,
  generateId,
  isEmpty,
  getErrorMessage,
} from '@/lib/utils';

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
  });

  it('handles tailwind conflicts with twMerge', () => {
    expect(cn('p-4', 'p-2')).toBe('p-2');
  });

  it('handles empty input', () => {
    expect(cn()).toBe('');
  });

  it('handles objects and arrays', () => {
    expect(cn({ foo: true, bar: false }, ['baz'])).toContain('foo');
    expect(cn({ foo: true, bar: false }, ['baz'])).toContain('baz');
  });
});

describe('formatDate', () => {
  it('formats Date object', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    const result = formatDate(date);
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/15/);
    expect(result).toMatch(/2024/);
  });

  it('formats string date', () => {
    const result = formatDate('2024-01-15T10:30:00Z');
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/15/);
    expect(result).toMatch(/2024/);
  });

  it('accepts custom options', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    const result = formatDate(date, { month: 'long' });
    expect(result).toMatch(/January/);
  });

  it('handles edge dates', () => {
    const date = new Date('1970-01-01T00:00:00Z');
    const result = formatDate(date);
    expect(result).toBeTruthy();
  });
});

describe('formatDateTime', () => {
  it('formats Date object with time', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    const result = formatDateTime(date);
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/15/);
    expect(result).toMatch(/2024/);
    expect(result).toMatch(/:/);
  });

  it('formats string date with time', () => {
    const result = formatDateTime('2024-01-15T10:30:00Z');
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/:/);
  });

  it('includes hours and minutes', () => {
    const date = new Date('2024-01-15T14:45:00Z');
    const result = formatDateTime(date);
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "just now" for recent times', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const recent = new Date('2024-01-15T10:29:30Z');
    expect(formatRelativeTime(recent)).toBe('just now');
  });

  it('formats minutes ago (singular)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T10:29:00Z');
    expect(formatRelativeTime(past)).toBe('1 minute ago');
  });

  it('formats minutes ago (plural)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T10:15:00Z');
    expect(formatRelativeTime(past)).toBe('15 minutes ago');
  });

  it('formats hours ago (singular)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T09:30:00Z');
    expect(formatRelativeTime(past)).toBe('1 hour ago');
  });

  it('formats hours ago (plural)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T05:30:00Z');
    expect(formatRelativeTime(past)).toBe('5 hours ago');
  });

  it('formats days ago (singular)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-14T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('1 day ago');
  });

  it('formats days ago (plural)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-12T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('3 days ago');
  });

  it('formats weeks ago (singular)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-08T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('1 week ago');
  });

  it('formats weeks ago (plural)', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-01T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('2 weeks ago');
  });

  it('formats months ago (singular)', () => {
    const now = new Date('2024-02-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('1 month ago');
  });

  it('formats months ago (plural)', () => {
    const now = new Date('2024-04-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2024-01-15T10:30:00Z');
    expect(formatRelativeTime(past)).toBe('3 months ago');
  });

  it('falls back to formatDate for dates over 12 months', () => {
    const now = new Date('2025-01-15T10:30:00Z');
    vi.setSystemTime(now);
    const past = new Date('2023-01-15T10:30:00Z');
    const result = formatRelativeTime(past);
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/15/);
    expect(result).toMatch(/2023/);
  });

  it('handles string input', () => {
    const now = new Date('2024-01-15T10:30:00Z');
    vi.setSystemTime(now);
    expect(formatRelativeTime('2024-01-15T10:15:00Z')).toBe('15 minutes ago');
  });
});

describe('formatBytes', () => {
  it('formats 0 bytes', () => {
    expect(formatBytes(0)).toBe('0 B');
  });

  it('formats bytes', () => {
    expect(formatBytes(512)).toBe('512 B');
  });

  it('formats kilobytes', () => {
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(1536)).toBe('1.5 KB');
  });

  it('formats megabytes', () => {
    expect(formatBytes(1048576)).toBe('1 MB');
    expect(formatBytes(2097152)).toBe('2 MB');
  });

  it('formats gigabytes', () => {
    expect(formatBytes(1073741824)).toBe('1 GB');
    expect(formatBytes(5368709120)).toBe('5 GB');
  });

  it('formats terabytes', () => {
    expect(formatBytes(1099511627776)).toBe('1 TB');
  });

  it('formats petabytes', () => {
    expect(formatBytes(1125899906842624)).toBe('1 PB');
  });

  it('respects decimals parameter', () => {
    expect(formatBytes(1536, 0)).toBe('2 KB');
    expect(formatBytes(1536, 1)).toBe('1.5 KB');
    expect(formatBytes(1536, 3)).toBe('1.5 KB');
  });

  it('handles negative decimals', () => {
    expect(formatBytes(1536, -1)).toBe('2 KB');
  });

  it('handles large values', () => {
    const result = formatBytes(9999999999999);
    expect(result).toContain('TB');
  });
});

describe('formatMemoryGB', () => {
  it('formats values under 1024 GB', () => {
    expect(formatMemoryGB(0)).toBe('0.0 GB');
    expect(formatMemoryGB(16)).toBe('16.0 GB');
    expect(formatMemoryGB(128)).toBe('128.0 GB');
    expect(formatMemoryGB(512)).toBe('512.0 GB');
  });

  it('formats values at exactly 1024 GB', () => {
    expect(formatMemoryGB(1024)).toBe('1.0 TB');
  });

  it('formats values over 1024 GB as TB', () => {
    expect(formatMemoryGB(2048)).toBe('2.0 TB');
    expect(formatMemoryGB(3072)).toBe('3.0 TB');
  });

  it('formats fractional TB values', () => {
    expect(formatMemoryGB(1536)).toBe('1.5 TB');
    expect(formatMemoryGB(2560)).toBe('2.5 TB');
  });

  it('rounds to 1 decimal place', () => {
    expect(formatMemoryGB(1536.789)).toBe('1.5 TB');
    expect(formatMemoryGB(128.456)).toBe('128.5 GB');
  });
});

describe('formatStorageTB', () => {
  it('formats values under 1 TB as GB', () => {
    expect(formatStorageTB(0.5)).toBe('512 GB');
    expect(formatStorageTB(0.25)).toBe('256 GB');
    expect(formatStorageTB(0.75)).toBe('768 GB');
  });

  it('formats values at exactly 1 TB', () => {
    expect(formatStorageTB(1)).toBe('1.00 TB');
  });

  it('formats values over 1 TB', () => {
    expect(formatStorageTB(2)).toBe('2.00 TB');
    expect(formatStorageTB(5)).toBe('5.00 TB');
    expect(formatStorageTB(10.5)).toBe('10.50 TB');
  });

  it('rounds GB to 0 decimals', () => {
    expect(formatStorageTB(0.333)).toBe('341 GB');
  });

  it('rounds TB to 2 decimals', () => {
    expect(formatStorageTB(1.23456)).toBe('1.23 TB');
  });

  it('handles boundary values', () => {
    expect(formatStorageTB(0.999)).toBe('1023 GB');
    expect(formatStorageTB(1.001)).toBe('1.00 TB');
  });

  it('handles zero', () => {
    expect(formatStorageTB(0)).toBe('0 GB');
  });
});

describe('formatPercentage', () => {
  it('formats with default 1 decimal', () => {
    expect(formatPercentage(50)).toBe('50.0%');
    expect(formatPercentage(33.333)).toBe('33.3%');
  });

  it('formats with custom decimals', () => {
    expect(formatPercentage(50, 0)).toBe('50%');
    expect(formatPercentage(50, 2)).toBe('50.00%');
    expect(formatPercentage(33.333, 2)).toBe('33.33%');
  });

  it('handles edge values', () => {
    expect(formatPercentage(0)).toBe('0.0%');
    expect(formatPercentage(100)).toBe('100.0%');
  });

  it('handles values over 100', () => {
    expect(formatPercentage(150)).toBe('150.0%');
  });

  it('handles negative values', () => {
    expect(formatPercentage(-10)).toBe('-10.0%');
  });

  it('handles very small values', () => {
    expect(formatPercentage(0.001, 3)).toBe('0.001%');
  });
});

describe('truncate', () => {
  it('returns string as-is if under maxLength', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('returns string as-is if exactly maxLength', () => {
    expect(truncate('hello', 5)).toBe('hello');
  });

  it('truncates and adds ellipsis if over maxLength', () => {
    expect(truncate('hello world', 8)).toBe('hello...');
  });

  it('handles very short maxLength', () => {
    expect(truncate('hello', 4)).toBe('h...');
  });

  it('handles maxLength of 3 (edge case)', () => {
    expect(truncate('hello', 3)).toBe('...');
  });

  it('handles empty string', () => {
    expect(truncate('', 5)).toBe('');
  });

  it('handles long strings', () => {
    const long = 'a'.repeat(100);
    const result = truncate(long, 20);
    expect(result).toBe('a'.repeat(17) + '...');
    expect(result.length).toBe(20);
  });
});

describe('capitalize', () => {
  it('capitalizes first letter', () => {
    expect(capitalize('hello')).toBe('Hello');
  });

  it('keeps rest of string unchanged', () => {
    expect(capitalize('hello world')).toBe('Hello world');
    expect(capitalize('hELLO')).toBe('HELLO');
  });

  it('handles single character', () => {
    expect(capitalize('a')).toBe('A');
  });

  it('handles already capitalized', () => {
    expect(capitalize('Hello')).toBe('Hello');
  });

  it('handles empty string', () => {
    expect(capitalize('')).toBe('');
  });

  it('handles strings starting with numbers', () => {
    expect(capitalize('123abc')).toBe('123abc');
  });

  it('handles strings starting with special characters', () => {
    expect(capitalize('!hello')).toBe('!hello');
  });
});

describe('debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('delays function execution', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledOnce();
  });

  it('cancels previous calls', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    vi.advanceTimersByTime(50);
    debounced();
    vi.advanceTimersByTime(50);
    debounced();
    vi.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledOnce();
  });

  it('passes arguments correctly', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('arg1', 'arg2', 123);
    vi.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledWith('arg1', 'arg2', 123);
  });

  it('uses latest arguments when called multiple times', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('first');
    debounced('second');
    debounced('third');
    vi.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledOnce();
    expect(fn).toHaveBeenCalledWith('third');
  });

  it('handles zero delay', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 0);

    debounced();
    vi.advanceTimersByTime(0);

    expect(fn).toHaveBeenCalledOnce();
  });
});

describe('sleep', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns a promise', () => {
    const result = sleep(100);
    expect(result).toBeInstanceOf(Promise);
  });

  it('resolves after specified time', async () => {
    const promise = sleep(100);
    vi.advanceTimersByTime(99);

    let resolved = false;
    promise.then(() => { resolved = true; });

    await vi.advanceTimersByTimeAsync(1);
    expect(resolved).toBe(true);
  });

  it('handles zero milliseconds', async () => {
    const promise = sleep(0);
    await vi.advanceTimersByTimeAsync(0);
    await expect(promise).resolves.toBeUndefined();
  });
});

describe('generateId', () => {
  it('generates a string', () => {
    const id = generateId();
    expect(typeof id).toBe('string');
  });

  it('generates ids of expected length', () => {
    const id = generateId();
    expect(id.length).toBe(9);
  });

  it('generates unique ids', () => {
    const ids = new Set();
    for (let i = 0; i < 100; i++) {
      ids.add(generateId());
    }
    expect(ids.size).toBe(100);
  });

  it('generates alphanumeric ids', () => {
    const id = generateId();
    expect(id).toMatch(/^[a-z0-9]+$/);
  });
});

describe('isEmpty', () => {
  it('returns true for null', () => {
    expect(isEmpty(null)).toBe(true);
  });

  it('returns true for undefined', () => {
    expect(isEmpty(undefined)).toBe(true);
  });

  it('returns true for empty string', () => {
    expect(isEmpty('')).toBe(true);
  });

  it('returns true for whitespace-only string', () => {
    expect(isEmpty('   ')).toBe(true);
    expect(isEmpty('\t\n')).toBe(true);
  });

  it('returns false for non-empty string', () => {
    expect(isEmpty('hello')).toBe(false);
    expect(isEmpty(' hello ')).toBe(false);
  });

  it('returns true for empty array', () => {
    expect(isEmpty([])).toBe(true);
  });

  it('returns false for non-empty array', () => {
    expect(isEmpty([1])).toBe(false);
    expect(isEmpty([null])).toBe(false);
  });

  it('returns true for empty object', () => {
    expect(isEmpty({})).toBe(true);
  });

  it('returns false for non-empty object', () => {
    expect(isEmpty({ a: 1 })).toBe(false);
  });

  it('returns false for numbers', () => {
    expect(isEmpty(0)).toBe(false);
    expect(isEmpty(1)).toBe(false);
    expect(isEmpty(-1)).toBe(false);
  });

  it('returns false for booleans', () => {
    expect(isEmpty(true)).toBe(false);
    expect(isEmpty(false)).toBe(false);
  });

  it('handles objects with prototype properties', () => {
    const obj = Object.create({ inherited: 'value' });
    expect(isEmpty(obj)).toBe(true);
  });
});

describe('getErrorMessage', () => {
  it('extracts message from Error instance', () => {
    const error = new Error('Something went wrong');
    expect(getErrorMessage(error)).toBe('Something went wrong');
  });

  it('handles string errors', () => {
    expect(getErrorMessage('Error string')).toBe('Error string');
  });

  it('extracts message from object with message property', () => {
    const error = { message: 'Custom error' };
    expect(getErrorMessage(error)).toBe('Custom error');
  });

  it('handles null', () => {
    expect(getErrorMessage(null)).toBe('An unexpected error occurred');
  });

  it('handles undefined', () => {
    expect(getErrorMessage(undefined)).toBe('An unexpected error occurred');
  });

  it('handles number', () => {
    expect(getErrorMessage(42)).toBe('An unexpected error occurred');
  });

  it('handles object without message', () => {
    expect(getErrorMessage({ code: 500 })).toBe('An unexpected error occurred');
  });

  it('handles empty string', () => {
    expect(getErrorMessage('')).toBe('');
  });

  it('handles object with non-string message', () => {
    const error = { message: 123 };
    expect(getErrorMessage(error)).toBe('123');
  });

  it('handles TypeError', () => {
    const error = new TypeError('Type error occurred');
    expect(getErrorMessage(error)).toBe('Type error occurred');
  });

  it('handles RangeError', () => {
    const error = new RangeError('Range error occurred');
    expect(getErrorMessage(error)).toBe('Range error occurred');
  });
});
