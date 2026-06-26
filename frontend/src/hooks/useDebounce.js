import { useState, useEffect } from 'react';

/**
 * useDebounce — delays updating the returned value until after `delay` ms
 * have passed since the last call. Prevents excessive API calls on fast typing.
 *
 * @param {*} value    The value to debounce (typically a search string)
 * @param {number} delay  Delay in milliseconds (default: 300)
 * @returns {*}        The debounced value
 */
export function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
