// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { afterEach, describe, expect, it } from 'vitest';
import { once } from 'events';
import { mkdtempSync, readFileSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { AuditLogger } from '../src/audit.js';
import { evaluatePolicy, Policy } from '../src/policy.js';
import { MCPProxy } from '../src/proxy.js';
import { RateLimiter } from '../src/rate-limiter.js';

const tempDirs: string[] = [];

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true });
  }
});

describe('evaluatePolicy', () => {
  it('copies mitigates from the matched rule into the decision', () => {
    const policy: Policy = {
      version: '1.0',
      mode: 'enforce',
      rules: [
        {
          tool: 'run_shell',
          action: 'deny',
          reason: 'blocked',
          mitigates: ['ASI02', 'ASI05'],
        },
        { tool: '*', action: 'allow' },
      ],
    };

    const decision = evaluatePolicy(policy, 'run_shell', {});

    expect(decision).toMatchObject({
      allowed: false,
      matchedRule: 'run_shell',
      mitigatedRisks: ['ASI02', 'ASI05'],
    });
  });

  it('leaves mitigatedRisks unset when the matched rule has no annotations', () => {
    const policy: Policy = {
      version: '1.0',
      mode: 'enforce',
      rules: [{ tool: '*', action: 'allow' }],
    };

    const decision = evaluatePolicy(policy, 'read_file', { path: 'README.md' });

    expect(decision.allowed).toBe(true);
    expect(decision.mitigatedRisks).toBeUndefined();
  });

  it('treats wildcard tool policies as globs instead of raw regular expressions', () => {
    const policy: Policy = {
      version: '1.0',
      mode: 'enforce',
      rules: [
        { tool: 'mcp.read_*', action: 'deny', reason: 'read tools blocked' },
        { tool: '*', action: 'allow' },
      ],
    };

    expect(evaluatePolicy(policy, 'mcp.read_file', {}).allowed).toBe(false);
    expect(evaluatePolicy(policy, 'mcpXread_file', {}).allowed).toBe(true);
  });

  it('normalizes traversal segments before evaluating path allow conditions', () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'mcp-proxy-policy-'));
    tempDirs.push(tempDir);
    const allowedRoot = join(tempDir, 'allowed');
    const policy: Policy = {
      version: '1.0',
      mode: 'enforce',
      rules: [
        {
          tool: 'read_file',
          action: 'allow',
          conditions: [{ path_starts_with: allowedRoot }],
        },
        { tool: '*', action: 'deny' },
      ],
    };

    expect(evaluatePolicy(policy, 'read_file', { path: `${allowedRoot}/report.txt` }).allowed).toBe(true);
    expect(evaluatePolicy(policy, 'read_file', { path: `${allowedRoot}/../secret.txt` }).allowed).toBe(false);
  });
});

describe('AuditLogger', () => {
  it('includes mitigates in CloudEvents data only when present', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'mcp-proxy-audit-'));
    tempDirs.push(tempDir);

    const logPath = join(tempDir, 'audit.log');
    const logger = new AuditLogger({ path: logPath });

    logger.log({
      type: 'ai.agentmesh.policy.violation',
      tool: 'run_shell',
      decision: 'deny',
      mitigates: ['ASI02', 'ASI05'],
    });
    logger.log({
      type: 'ai.agentmesh.tool.invoked',
      tool: 'read_file',
      decision: 'allow',
    });

    logger.close();

    const stream = Reflect.get(logger, 'stream');
    if (stream) {
      await once(stream, 'finish');
    }

    const [deniedEntry, allowedEntry] = readFileSync(logPath, 'utf-8')
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line) as { data: Record<string, unknown> });

    expect(deniedEntry.data.mitigates).toEqual(['ASI02', 'ASI05']);
    expect(allowedEntry.data).not.toHaveProperty('mitigates');
  });

  it('emits the actual previous hash in CloudEvents extension attributes', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'mcp-proxy-audit-'));
    tempDirs.push(tempDir);

    const logPath = join(tempDir, 'audit.log');
    const logger = new AuditLogger({ path: logPath });

    logger.log({
      type: 'ai.agentmesh.tool.invoked',
      tool: 'read_file',
      decision: 'allow',
    });
    logger.log({
      type: 'ai.agentmesh.policy.violation',
      tool: 'run_shell',
      decision: 'deny',
    });

    logger.close();

    const stream = Reflect.get(logger, 'stream');
    if (stream) {
      await once(stream, 'finish');
    }

    const [firstEntry, secondEntry] = readFileSync(logPath, 'utf-8')
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line) as { entryhash: string; previoushash: string });

    expect(firstEntry.previoushash).toBe('0'.repeat(64));
    expect(secondEntry.previoushash).toBe(firstEntry.entryhash);
    expect(secondEntry.previoushash).not.toBe(secondEntry.entryhash);
  });

  it('recursively redacts nested secrets before writing audit entries', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'mcp-proxy-audit-'));
    tempDirs.push(tempDir);

    const logPath = join(tempDir, 'audit.log');
    const logger = new AuditLogger({ path: logPath });

    logger.log({
      type: 'ai.agentmesh.tool.invoked',
      tool: 'http_request',
      decision: 'allow',
      arguments: {
        request: {
          headers: {
            Authorization: 'Bearer secret-token',
          },
          body: {
            nested: [{ api_key: 'abc123' }],
          },
        },
      },
    });

    logger.close();

    const stream = Reflect.get(logger, 'stream');
    if (stream) {
      await once(stream, 'finish');
    }

    const [entry] = readFileSync(logPath, 'utf-8')
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line) as { data: { arguments: any } });

    expect(entry.data.arguments.request.headers.Authorization).toBe('[REDACTED]');
    expect(entry.data.arguments.request.body.nested[0].api_key).toBe('[REDACTED]');
    expect(JSON.stringify(entry)).not.toContain('secret-token');
    expect(JSON.stringify(entry)).not.toContain('abc123');
  });
});

describe('RateLimiter', () => {
  it('scopes global and per-tool buckets by caller identity', () => {
    const limiter = new RateLimiter({ requests: 1, per: 'minute' });
    limiter.setToolLimit('read_file', { requests: 1, per: 'minute' });

    expect(limiter.allow('read_file', 'caller-a')).toBe(true);
    expect(limiter.allow('read_file', 'caller-a')).toBe(false);
    expect(limiter.allow('read_file', 'caller-b')).toBe(true);
  });
});

describe('MCPProxy command resolution', () => {
  function createProxy(command: string): MCPProxy {
    return new MCPProxy({
      command,
      args: [],
      policy: { version: '1.0', mode: 'enforce', rules: [{ tool: '*', action: 'allow' }] },
      mode: 'enforce',
      auditLogger: new AuditLogger(),
    });
  }

  it('does not rewrite bare commands to npx', () => {
    const proxy = createProxy('node');
    const resolveCommand = Reflect.get(proxy, 'resolveCommand') as (command: string) => string;

    expect(resolveCommand.call(proxy, 'node')).toBe('node');
    expect(Reflect.get(proxy, 'options').args).toEqual([]);
  });

  it('rejects scoped npm package specifiers instead of executing npx', () => {
    const proxy = createProxy('@modelcontextprotocol/server-filesystem');
    const resolveCommand = Reflect.get(proxy, 'resolveCommand') as (command: string) => string;

    expect(() => resolveCommand.call(proxy, '@modelcontextprotocol/server-filesystem')).toThrow(
      /NPM package specifiers/,
    );
  });

  it('derives rate-limit identity from MCP metadata when present', () => {
    const proxy = createProxy('node');
    const resolveRateLimitIdentity = Reflect.get(proxy, 'resolveRateLimitIdentity') as (
      message: any,
      toolArgs: Record<string, unknown>,
    ) => string;

    expect(
      resolveRateLimitIdentity.call(
        proxy,
        { params: { _meta: { agentmesh: { caller_id: 'agent-123' } } } },
        {},
      ),
    ).toBe('caller:agent-123');
  });
});
