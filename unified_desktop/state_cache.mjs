// Shared by the packaged page and the Node regression tests.
export class WorkbenchStateCache {
  constructor(fetch, {ttl = 15000, clock = () => Date.now()} = {}) {
    this.fetch = fetch; this.ttl = ttl; this.clock = clock;
    this.generation = 0; this.value = null; this.pending = null; this.loadedAt = 0;
  }
  invalidate() { this.generation++; this.value = null; this.pending = null; }
  get(force = false) {
    if (force) this.invalidate();
    if (this.value && this.clock() - this.loadedAt < this.ttl) return Promise.resolve(this.value);
    if (this.pending) return this.pending;
    const generation = this.generation;
    const pending = this.fetch().then(value => {
      if (generation !== this.generation) return this.get();
      this.value = value; this.loadedAt = this.clock(); return value;
    }).finally(() => { if (this.pending === pending) this.pending = null; });
    this.pending = pending;
    return pending;
  }
}
