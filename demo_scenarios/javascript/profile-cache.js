// Demo 02: JavaScript async control flow and cache correctness.
const cache = new Map();

export async function loadProfile(userId, fetchProfile) {
  if (!cache.has(userId)) {
    cache.set(userId, fetchProfile(userId));
  }
  return cache.get(userId);
}

