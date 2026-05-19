// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
/**
 * Audit Logger - CloudEvents format
 * 
 * Logs all tool invocations and policy decisions in CloudEvents v1.0 format.
 */

import { createWriteStream, WriteStream } from 'fs';
import { createHash, randomUUID } from 'crypto';

export interface AuditLoggerOptions {
  path?: string;
  format?: 'json' | 'cloudevents';
}

export interface AuditEvent {
  type: string;
  tool: string;
  arguments?: Record<string, any>;
  decision: 'allow' | 'deny';
  reason?: string;
  rule?: string;
  mitigates?: string[];
  latency_ms?: number;
}

export class AuditLogger {
  private static readonly MAX_REDACTION_DEPTH = 8;
  private static readonly MAX_OBJECT_KEYS = 100;
  private static readonly MAX_ARRAY_ITEMS = 100;
  private static readonly MAX_STRING_LENGTH = 500;
  private static readonly SENSITIVE_KEY_PATTERNS = [
    'password',
    'passwd',
    'secret',
    'token',
    'key',
    'credential',
    'authorization',
    'cookie',
    'set-cookie',
    'api_key',
    'apikey',
    'private',
  ];

  private options: AuditLoggerOptions;
  private stream: WriteStream | null = null;
  private previousHash: string = '0'.repeat(64);
  private source: string;

  constructor(options: AuditLoggerOptions = {}) {
    this.options = {
      format: 'cloudevents',
      ...options,
    };
    this.source = `urn:agentmesh-mcp-proxy:${process.pid}`;

    if (options.path) {
      this.stream = createWriteStream(options.path, { flags: 'a' });
    }
  }

  log(event: AuditEvent): void {
    const cloudEvent = this.formatCloudEvent(event);
    const line = JSON.stringify(cloudEvent);

    // Write to file
    if (this.stream) {
      this.stream.write(line + '\n');
    }

    // Also log to stderr in verbose mode
    if (process.env.AGENTMESH_VERBOSE) {
      console.error(`[audit] ${event.decision}: ${event.tool}`, event.reason || '');
    }
  }

  private formatCloudEvent(event: AuditEvent): object {
    const id = randomUUID();
    const time = new Date().toISOString();
    const sanitizedArguments = this.sanitizeArguments(event.arguments);
    const loggedEvent = {
      ...event,
      arguments: sanitizedArguments,
    };

    // Compute hash chain hash for tamper detection
    const previousHash = this.previousHash;
    const dataJson = JSON.stringify(loggedEvent);
    const entryHash = this.computeHash(`${previousHash}:${dataJson}`);
    this.previousHash = entryHash;

    if (this.options.format === 'json') {
      return {
        id,
        timestamp: time,
        ...loggedEvent,
        _hash: entryHash,
      };
    }

    // CloudEvents v1.0 format
    return {
      specversion: '1.0',
      id,
      type: event.type,
      source: this.source,
      time,
      datacontenttype: 'application/json',
      data: {
        tool: event.tool,
        arguments: sanitizedArguments,
        decision: event.decision,
        reason: event.reason,
        matched_rule: event.rule,
        mitigates: event.mitigates,
        latency_ms: event.latency_ms,
      },
      // Extension attributes for AgentMesh
      agentmeshversion: '1.0',
      entryhash: entryHash,
      previoushash: previousHash,
    };
  }

  private computeHash(data: string): string {
    return createHash('sha256').update(data).digest('hex');
  }

  private sanitizeArguments(args?: Record<string, any>): Record<string, any> | undefined {
    if (!args) return undefined;

    return this.sanitizeValue(args, 0) as Record<string, any>;
  }

  private sanitizeValue(value: unknown, depth: number): unknown {
    if (depth > AuditLogger.MAX_REDACTION_DEPTH) {
      return '[MAX_DEPTH]';
    }
    if (typeof value === 'string') {
      return this.sanitizeString(value);
    }
    if (value === null || typeof value !== 'object') {
      return value;
    }
    if (Array.isArray(value)) {
      const items = value
        .slice(0, AuditLogger.MAX_ARRAY_ITEMS)
        .map((item) => this.sanitizeValue(item, depth + 1));
      if (value.length > AuditLogger.MAX_ARRAY_ITEMS) {
        items.push(`[${value.length - AuditLogger.MAX_ARRAY_ITEMS} more item(s) truncated]`);
      }
      return items;
    }

    const sanitized: Record<string, unknown> = {};
    const entries = Object.entries(value as Record<string, unknown>).slice(0, AuditLogger.MAX_OBJECT_KEYS);
    for (const [key, nestedValue] of entries) {
      if (this.isSensitiveKey(key)) {
        sanitized[key] = '[REDACTED]';
      } else {
        sanitized[key] = this.sanitizeValue(nestedValue, depth + 1);
      }
    }
    const remainingKeys = Object.keys(value as Record<string, unknown>).length - entries.length;
    if (remainingKeys > 0) {
      sanitized.__truncated_keys = remainingKeys;
    }
    return sanitized;
  }

  private isSensitiveKey(key: string): boolean {
    const normalized = key.toLowerCase();
    return AuditLogger.SENSITIVE_KEY_PATTERNS.some((pattern) => normalized.includes(pattern));
  }

  private sanitizeString(value: string): string {
    const normalized = value.replace(/[\u0000-\u001f\u007f]/g, ' ');
    if (normalized.length > AuditLogger.MAX_STRING_LENGTH) {
      return normalized.substring(0, AuditLogger.MAX_STRING_LENGTH) + '...[truncated]';
    }
    return normalized;
  }

  close(): void {
    if (this.stream) {
      this.stream.end();
    }
  }
}
