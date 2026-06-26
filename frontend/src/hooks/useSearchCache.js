/**
 * useSearchCache.js — LRU in-memory search result cache
 *
 * Provides instant results for repeated searches without hitting the network.
 * Implements a Least Recently Used (LRU) eviction policy.
 *
 * Strategy:
 *   - Key: normalized search term (trimmed, lowercased)
 *   - Max entries: 100 (est. ~50KB max memory footprint)
 *   - Cache hit: returns immediately, 0ms latency
 *   - Cache miss: calls API, stores result
 *   - Eviction: removes oldest entry when capacity exceeded
 *
 * Hit-rate expectation:
 *   - Users typically retype same queries (autocomplete pattern)
 *   - Expected 60-80% hit rate on second+ character keystrokes
 */

const MAX_CACHE_SIZE = 100;

/** Module-level LRU cache — shared across all component instances */
const _cache = new Map();

function normalizeKey(query) {
  return query.trim().toLowerCase();
}

/**
 * Check if a search result exists in cache.
 * @param {string} query
 * @returns {Array|null} cached results or null on miss
 */
export function cacheGet(query) {
  const key = normalizeKey(query);
  if (!_cache.has(key)) return null;
  // LRU: move to end (most recently used)
  const value = _cache.get(key);
  _cache.delete(key);
  _cache.set(key, value);
  return value;
}

/**
 * Store search results in cache.
 * @param {string} query
 * @param {Array} results
 */
export function cacheSet(query, results) {
  const key = normalizeKey(query);
  if (_cache.has(key)) {
    _cache.delete(key); // refresh position
  } else if (_cache.size >= MAX_CACHE_SIZE) {
    // Evict the least recently used (first entry)
    const firstKey = _cache.keys().next().value;
    _cache.delete(firstKey);
  }
  _cache.set(key, results);
}

/** Clear the entire cache (e.g., on logout) */
export function cacheClear() {
  _cache.clear();
}

/** Returns current cache stats for debugging */
export function cacheStats() {
  return { size: _cache.size, maxSize: MAX_CACHE_SIZE };
}
