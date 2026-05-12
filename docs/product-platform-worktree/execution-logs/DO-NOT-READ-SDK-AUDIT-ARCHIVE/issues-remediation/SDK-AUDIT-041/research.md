# SDK-AUDIT-041 Research: Safe Regex Engine Or Timeout-Backed Redaction Enforcement

## Problem

Response redaction policies accept regex patterns that are validated with heuristics and executed with Python `re`. Python's backtracking regex engine can be vulnerable to catastrophic backtracking for some patterns and inputs. The current validation rejects some dangerous shapes, but it does not prove safe execution.

Current limitations:

- No regex timeout.
- No linear-time engine.
- Heuristics can miss pathological patterns.
- Patterns are compiled in the response path.
- No ReDoS corpus test with strict budgets.

## Industry Pattern

Systems that accept user-controlled regex use one of these controls:

- A safe linear-time regex engine such as RE2.
- A strict approved regex subset.
- A timeout-capable engine and small input budget.
- Precompilation and caching outside the hot path.
- Deny-by-default behavior if redaction fails.

RE2 is an industry-standard safe regex engine used widely in production; its project describes it as designed for untrusted regexes with linear-time matching and bounded memory behavior: https://github.com/google/re2

Python's third-party `regex` package supports operation timeouts, according to its PyPI documentation: https://pypi.org/project/regex/

## AWS Assessment

AWS does not provide a managed service or native Python runtime feature that safely executes arbitrary regex redaction rules inside this application path. AWS WAF regex matching is not suitable because redaction occurs on upstream response bodies after gateway invocation, inside application logic. Lambda or Step Functions would add network hops and would still need a safe regex engine inside the function.

AWS is insufficient for this specific in-process redaction problem because:

- The gateway must transform response bodies synchronously before returning them.
- Redaction patterns are tenant/operator configuration, not edge request-filtering rules.
- A managed AWS service would not expose the required nested JSON traversal and replacement semantics.

## Options

### Option A: Keep Heuristics With Python `re`

Benefits:

- No dependency change.

Tradeoffs:

- Does not enforce execution time.
- Residual ReDoS risk remains.

Decision: reject for production.

### Option B: Use RE2 Via Python Binding

Benefits:

- Linear-time matching.
- Industry standard for untrusted regex.
- Strongest ReDoS prevention.

Tradeoffs:

- Python bindings can add binary packaging complexity.
- RE2 intentionally omits features such as backreferences and lookaround.
- Some existing patterns may need migration.

Decision: defer for MVP unless the timeout-backed approach fails validation. RE2 is the stronger long-term choice, but binary packaging and feature migration are unnecessary friction for the first production release.

### Option C: Use Python `regex` Module With Timeout

Benefits:

- Easier compatibility with Python regex features.
- Timeout support for each operation.
- Stable PyPI package.

Tradeoffs:

- Timeout mitigates but does not make all patterns linear.
- Must handle timeout exceptions fail-closed.

Decision: adopt for MVP.

## Final Architecture

Adopt a timeout-backed implementation for MVP:

1. Primary MVP engine: Python `regex` module with strict per-operation timeout.
2. Optional future engine: RE2 through `google-re2` or a maintained equivalent binding when customer/security requirements justify the stronger guarantee.

Contract:

- Default production engine is `timeout`.
- Patterns that exceed timeout or validation limits are rejected or fail closed.
- Redaction failure is fail-closed by default: block full response storage and return a gateway error or sanitized deny result.
- Compile rules at policy create/update time where possible, cache by policy ID/version/update timestamp.
- Enforce max pattern length, max rules per policy, max traversed response bytes, and max redaction time budget.

## Selected Alternative And Industry Standard Justification

AWS is insufficient for in-process response redaction. The selected MVP alternative is the Python `regex` module with timeouts because it is simple to package and directly addresses the immediate no-timeout gap.

RE2 remains the industry-standard scale-up option because it was designed to safely process untrusted regular expressions with linear-time execution and bounded memory, and it has been used in production at Google and elsewhere for many years. It is deferred, not rejected.
