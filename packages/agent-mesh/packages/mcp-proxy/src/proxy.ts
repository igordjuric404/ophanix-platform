// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
/**
 * MCP Proxy - The core security layer
 * 
 * Wraps any MCP server with policy enforcement, rate limiting,
 * input sanitization, and audit logging.
 */

import { spawn, ChildProcess } from 'child_process';
import { Policy, evaluatePolicy, PolicyDecision } from './policy.js';
import { AuditLogger } from './audit.js';
import { Sanitizer } from './sanitizer.js';
import { RateLimiter } from './rate-limiter.js';

export interface ProxyOptions {
  command: string;
  args: string[];
  policy: Policy;
  mode: 'enforce' | 'shadow';
  auditLogger: AuditLogger;
  rateLimit?: { requests: number; per: string };
  sanitize?: boolean;
  verbose?: boolean;
}

export class MCPProxy {
  private options: ProxyOptions;
  private childProcess: ChildProcess | null = null;
  private rateLimiter: RateLimiter | null = null;
  private sanitizer: Sanitizer;
  private buffer: string = '';

  constructor(options: ProxyOptions) {
    this.options = options;
    this.sanitizer = new Sanitizer();
    
    if (options.rateLimit) {
      this.rateLimiter = new RateLimiter(options.rateLimit);
    }
  }

  async start(): Promise<void> {
    // Resolve command (handle npm packages)
    const resolvedCommand = this.resolveCommand(this.options.command);
    
    if (this.options.verbose) {
      console.error(`[proxy] Starting: ${resolvedCommand} ${this.options.args.join(' ')}`);
    }

    // Spawn the wrapped MCP server
    this.childProcess = spawn(resolvedCommand, this.options.args, {
      stdio: ['pipe', 'pipe', 'inherit'],
      shell: process.platform === 'win32',
    });

    // Handle stdin (from Claude/client)
    process.stdin.on('data', (data) => {
      this.handleClientInput(data);
    });

    // Handle stdout (from MCP server)
    this.childProcess.stdout?.on('data', (data) => {
      this.handleServerOutput(data);
    });

    // Handle process exit
    this.childProcess.on('exit', (code) => {
      if (this.options.verbose) {
        console.error(`[proxy] Child process exited with code ${code}`);
      }
      process.exit(code ?? 0);
    });

    this.childProcess.on('error', (error) => {
      console.error(`[proxy] Error:`, error.message);
      process.exit(1);
    });

    // Handle our own exit
    process.on('SIGINT', () => this.shutdown());
    process.on('SIGTERM', () => this.shutdown());
  }

  private resolveCommand(command: string): string {
    const trimmed = command.trim();
    if (!trimmed) {
      throw new Error('MCP command is required');
    }
    if (trimmed.startsWith('@')) {
      throw new Error(
        'NPM package specifiers are not executed implicitly. Install the MCP server and pass an explicit executable path or local binary.',
      );
    }
    return trimmed;
  }

  private handleClientInput(data: Buffer): void {
    // Parse JSON-RPC messages from the client
    this.buffer += data.toString();
    
    const messages = this.parseMessages();
    
    for (const message of messages) {
      const processed = this.processClientMessage(message);
      if (processed !== null) {
        // Forward to child process
        this.childProcess?.stdin?.write(JSON.stringify(processed) + '\n');
      }
    }
  }

  private handleServerOutput(data: Buffer): void {
    // Forward server responses to stdout
    process.stdout.write(data);
  }

  private parseMessages(): any[] {
    const messages: any[] = [];
    const lines = this.buffer.split('\n');
    
    // Keep incomplete last line in buffer
    this.buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.trim()) {
        try {
          messages.push(JSON.parse(line));
        } catch {
          // Invalid JSON, skip
        }
      }
    }
    
    return messages;
  }

  private processClientMessage(message: any): any | null {
    // Only intercept tool calls (MCP tools/call)
    if (message.method !== 'tools/call') {
      return message; // Pass through
    }

    const toolName = message.params?.name;
    const toolArgs = message.params?.arguments || {};
    const rateLimitIdentity = this.resolveRateLimitIdentity(message, toolArgs);

    // 1. Sanitize inputs
    if (this.options.sanitize !== false) {
      const sanitizeResult = this.sanitizer.check(toolName, toolArgs);
      if (!sanitizeResult.safe) {
        this.options.auditLogger.log({
          type: 'ai.agentmesh.security.blocked',
          tool: toolName,
          arguments: toolArgs,
          decision: 'deny',
          reason: sanitizeResult.reason,
        });

        if (this.options.mode === 'enforce') {
          // Return error response
          this.sendErrorResponse(message.id, sanitizeResult.reason || 'Security check failed');
          return null;
        }
      }
    }

    // 2. Rate limiting
    if (this.rateLimiter && !this.rateLimiter.allow(toolName, rateLimitIdentity)) {
      this.options.auditLogger.log({
        type: 'ai.agentmesh.ratelimit.exceeded',
        tool: toolName,
        arguments: toolArgs,
        decision: 'deny',
        reason: 'Rate limit exceeded',
      });

      if (this.options.mode === 'enforce') {
        this.sendErrorResponse(message.id, 'Rate limit exceeded. Please wait before retrying.');
        return null;
      }
    }

    // 3. Policy evaluation
    const decision = evaluatePolicy(this.options.policy, toolName, toolArgs);

    this.options.auditLogger.log({
      type: decision.allowed ? 'ai.agentmesh.tool.invoked' : 'ai.agentmesh.policy.violation',
      tool: toolName,
      arguments: toolArgs,
      decision: decision.allowed ? 'allow' : 'deny',
      reason: decision.reason,
      rule: decision.matchedRule,
      mitigates: decision.mitigatedRisks,
    });

    if (!decision.allowed && this.options.mode === 'enforce') {
      this.sendErrorResponse(message.id, decision.reason || 'Blocked by policy');
      return null;
    }

    // Log allowed call
    if (this.options.verbose) {
      console.error(`[proxy] ${decision.allowed ? '✅' : '⚠️'} ${toolName}`, 
        this.options.mode === 'shadow' && !decision.allowed ? '(shadow mode - passed)' : '');
    }

    return message;
  }

  private resolveRateLimitIdentity(message: any, toolArgs: Record<string, any>): string {
    const metadata = message.params?._meta || message.params?.meta || {};
    const agentMeshMetadata = metadata.agentmesh || metadata.agentMesh || {};
    const candidate =
      agentMeshMetadata.rate_limit_identity ||
      agentMeshMetadata.rateLimitIdentity ||
      agentMeshMetadata.caller_id ||
      agentMeshMetadata.callerId ||
      metadata.client_id ||
      metadata.clientId ||
      metadata.session_id ||
      metadata.sessionId ||
      toolArgs.tenant_id ||
      toolArgs.tenantId ||
      toolArgs.organization_id ||
      toolArgs.organizationId ||
      toolArgs.agent_id ||
      toolArgs.agentId ||
      process.env.AGENTMESH_RATE_LIMIT_IDENTITY;
    if (typeof candidate === 'string' && candidate.trim()) {
      return `caller:${candidate.trim()}`;
    }
    return `process:${process.ppid}:${this.options.command}`;
  }

  private sendErrorResponse(id: number | string, message: string): void {
    const response = {
      jsonrpc: '2.0',
      id: id,
      error: {
        code: -32001,
        message: `[AgentMesh] ${message}`,
      },
    };
    process.stdout.write(JSON.stringify(response) + '\n');
  }

  private shutdown(): void {
    if (this.childProcess) {
      this.childProcess.kill();
    }
    process.exit(0);
  }
}
