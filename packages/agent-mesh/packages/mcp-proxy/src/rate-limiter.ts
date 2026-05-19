// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
/**
 * Rate Limiter
 * 
 * Token bucket rate limiting for tool calls.
 */

export interface RateLimitConfig {
  requests: number;
  per: string;  // 'second' | 'minute' | 'hour'
}

interface BucketState {
  tokens: number;
  lastRefill: number;
}

export class RateLimiter {
  private globalConfig: RateLimitConfig;
  private perToolConfig: Map<string, RateLimitConfig> = new Map();
  private buckets: Map<string, BucketState> = new Map();

  constructor(globalConfig: RateLimitConfig) {
    this.globalConfig = globalConfig;
  }

  setToolLimit(tool: string, config: RateLimitConfig): void {
    this.perToolConfig.set(tool, config);
  }

  allow(tool: string, identity: string = 'default'): boolean {
    const scope = this.normalizeIdentity(identity);

    // Check per-tool limit first
    const toolConfig = this.perToolConfig.get(tool);
    if (toolConfig && !this.checkBucket(`${scope}:tool:${tool}`, toolConfig)) {
      return false;
    }

    // Check global limit
    return this.checkBucket(`${scope}:global`, this.globalConfig);
  }

  private checkBucket(key: string, config: RateLimitConfig): boolean {
    const now = Date.now();
    const refillInterval = this.parseInterval(config.per);
    
    let bucket = this.buckets.get(key);
    
    if (!bucket) {
      bucket = {
        tokens: config.requests,
        lastRefill: now,
      };
      this.buckets.set(key, bucket);
    }

    // Refill tokens based on time passed
    const timePassed = now - bucket.lastRefill;
    const refillTokens = Math.floor(timePassed / refillInterval) * config.requests;
    
    if (refillTokens > 0) {
      bucket.tokens = Math.min(config.requests, bucket.tokens + refillTokens);
      bucket.lastRefill = now;
    }

    // Check if we have tokens
    if (bucket.tokens > 0) {
      bucket.tokens--;
      return true;
    }

    return false;
  }

  private parseInterval(per: string): number {
    switch (per.toLowerCase()) {
      case 'second':
        return 1000;
      case 'minute':
        return 60 * 1000;
      case 'hour':
        return 60 * 60 * 1000;
      default:
        return 60 * 1000; // Default to minute
    }
  }

  getStatus(identity: string = 'default'): Record<string, { remaining: number; limit: number }> {
    const status: Record<string, { remaining: number; limit: number }> = {};
    const scope = this.normalizeIdentity(identity);
    
    const globalBucket = this.buckets.get(`${scope}:global`);
    status['global'] = {
      remaining: globalBucket?.tokens ?? this.globalConfig.requests,
      limit: this.globalConfig.requests,
    };

    for (const [tool, config] of this.perToolConfig) {
      const bucket = this.buckets.get(`${scope}:tool:${tool}`);
      status[tool] = {
        remaining: bucket?.tokens ?? config.requests,
        limit: config.requests,
      };
    }

    return status;
  }

  private normalizeIdentity(identity: string): string {
    const trimmed = identity.trim();
    if (!trimmed) {
      return 'default';
    }
    return trimmed.replace(/[^a-zA-Z0-9._:-]/g, '_');
  }
}
