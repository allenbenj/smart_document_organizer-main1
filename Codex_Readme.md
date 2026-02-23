Controlled Hardening Protocol for Software Development
This is not a feature sprint.
This is disciplined stabilization.
The objective: eliminate drift, eliminate reactive patching, eliminate unverified claims.
Operating Rule
Development proceeds in strict, single hardening phases.
No overlapping initiatives.
No scope creep.
No “quick fixes” outside the defined boundary.
Progression to the next phase requires explicit acceptance of Done Criteria.
No feature claims without passing predefined acceptance checks.
Phase Structure Framework
Each hardening phase must include:
Defined Scope (frozen)
Risk Model
Implementation Plan
Verification Requirements
Done Criteria (approved before moving forward)
Phase Execution Model
1. Scope Definition (Frozen)
Before writing or modifying code:
Define exact modules/files affected.
Define exact behaviors under modification.
Define explicit non-goals.
List assumptions.
Scope Freeze Rule:
No additional behaviors, refactors, or improvements are introduced unless:
They are necessary to meet defined acceptance checks.
They are explicitly approved before execution.
2. Risk Identification
For the phase, identify:
Data integrity risks
Concurrency risks
Performance risks
Security risks
Regression risks
Use structured reasoning:
Causal chain analysis
Failure mode identification
Boundary condition mapping
This forces clarity before implementation.
3. Implementation Plan
Implementation must follow best practices:
Small, isolated commits
Clear naming
No hidden side effects
Dependency injection over global state
Explicit error handling
Logging at failure boundaries
Idempotent operations where possible
No speculative abstraction.
No premature optimization.
No hidden magic.
4. Required Proof per Phase
Every phase must produce the following artifacts:
A. Code Diff
Clean diff
No unrelated formatting noise
Clear commit message explaining:
What changed
Why it changed
What risk it mitigates
No ambiguous “misc fixes.”
B. Compile + Test Evidence
Clean compile output
Unit tests passing
Integration tests passing
No new warnings introduced
If warnings appear:
Document them
Either resolve or justify explicitly
C. One Reproducible Manual Scenario
Define one deterministic scenario:
Starting state
Inputs
Expected outputs
Observed outputs
Must be reproducible by another person without interpretation.
This prevents illusion-of-correctness thinking.
5. Done Criteria (Must Be Approved Before Progression)
Each phase must define measurable acceptance checks such as:
Specific functional behavior verified
Performance threshold met (if applicable)
No regression in dependent modules
All defined risks mitigated or documented
Advancement requires explicit confirmation that:
All acceptance checks passed
Proof artifacts provided
Scope boundaries respected
No “it seems good.”
Enforcement Mechanisms
To prevent reactive patching:
Freeze branch during phase
No emergency feature additions
No refactors unless risk-driven
No merging of unrelated changes
All changes must map to phase objectives.
Anti-Drift Rule
If a bug is discovered outside scope:
Log it.
Do not fix it.
Defer to a future phase.
Discipline prevents chaos.
Acceptance Standard
No feature claim is valid unless:
It passes predefined acceptance checks.
It is demonstrated via reproducible scenario.
It is covered by tests where applicable.
Claims without proof are noise.
Example Phase Template
Phase Name:
Authentication Hardening
Scope:
Token validation logic
Session expiration handling
Non-Goals:
UI redesign
New auth methods
Risks:
Token replay
Expired session bypass
Race conditions in logout
Required Proof:
Code diff
Test suite output
Manual scenario: expired token request rejected
Done Criteria:
Expired tokens rejected deterministically
No performance regression >5%
All auth tests pass
No new security warnings
Only after approval: move to next phase.
Guiding Principle
Complex systems degrade through entropy.
Hardening phases impose order.
One phase.
One objective.
One measurable outcome.
Move only when stability is proven.