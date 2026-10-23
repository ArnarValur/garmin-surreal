# Project Workflow — Strict (TDD)

> Full test-driven development workflow with coverage gates.
> Red → Green → Refactor on every task. No exceptions.

---

## The Two Laws

These bind every write in this conductor. Everything else in this file is convention; these are law.

1. **One fact, one home.** Live truth lives in `pulse.md`. A session's story is told once, in `relay.md`. Lessons live in the permanent rules files (`agent-rules/`). Decisions live in ADRs (`adr/`) or track-plan D-numbers. Never retell — point.
2. **A ruling binds only when it lands in a repo file.** Agent memory is a cache and conversation is vapor. If a rule, decision, or lesson is not in a repo file, it does not exist.

---

## Guiding Principles

1. **The Plan is the Source of Truth:** All work is tracked in a track — its `plan.md` holds the tasks; `tracks.md` holds one line per track
2. **The Tech Stack is Deliberate:** Changes to the tech stack must be documented in the **Tech Stack** section of `project-context.md` *before* implementation. Architecturally significant changes (those satisfying the three-criteria ADR test: hard to reverse, surprising without context, real trade-off) additionally warrant an ADR in `conductor/adr/` — propose it in-session; approved ADRs are written at `/checkpoint`.
3. **Test-Driven Development:** Write unit tests before implementing functionality
4. **High Code Coverage:** Aim for >80% code coverage for all modules
5. **User Experience First:** Every decision should prioritize user experience
6. **Non-Interactive & CI-Aware:** Prefer non-interactive commands. Use `CI=true` for watch-mode tools (tests, linters) to ensure single execution

---

## Task Workflow

All tasks follow a strict 11-step lifecycle:

### Standard Task Workflow

1. **Select Task:** Choose the next available task from the active track's `plan.md`, in order

2. **Mark In Progress:** In the track's `plan.md`, change the task from `[ ]` to `[~]`

3. **Write Failing Tests (Red Phase):**
   - Create a new test file for the feature or bug fix
   - Write one or more unit tests that clearly define the expected behavior and acceptance criteria
   - **CRITICAL:** Run the tests and confirm that they fail as expected. This is the "Red" phase of TDD. Do not proceed until you have failing tests

4. **Implement to Pass Tests (Green Phase):**
   - Write the minimum amount of application code necessary to make the failing tests pass
   - Run the test suite again and confirm that all tests now pass. This is the "Green" phase

5. **Refactor (Recommended):**
   - With the safety of passing tests, refactor the implementation code and the test code to improve clarity, remove duplication, and enhance performance without changing external behavior
   - Rerun tests to ensure they still pass after refactoring

6. **Verify Coverage:** Run coverage reports using the project's chosen tools. For example:

   ```bash
   # Python
   pytest --cov=app --cov-report=html
   # Node.js
   CI=true npx vitest --coverage
   # Go
   go test -coverprofile=coverage.out ./...
   ```

   **Gate: >80% coverage for new code.** Do not proceed if coverage is below threshold.

7. **Document Deviations:** If implementation differs from tech stack:
   - **STOP** implementation
   - Update the **Tech Stack** section of `project-context.md` with the new design
   - Add a dated note explaining the change (user-edited — no command writes to `project-context.md` post-init)
   - If the change is architecturally significant (three-criteria ADR test), propose it as an ADR in-session; it is written at `/checkpoint` once approved
   - Resume implementation

8. **Commit Code Changes:**
   - Stage all code changes related to the task
   - Commit with a clear, concise message following conventional commits format
   - Example: `feat(ui): Create basic HTML structure for calculator`

9. **Record Task Completion in Plan:**
    - **9.1:** In the track's `plan.md`, update the completed task from `[~]` to `[x]` and append the first 7 characters of the commit hash
    - **9.2:** Write the updated content back to the track's `plan.md`

10. **Commit Plan Update:**
    - Stage the modified `plan.md`
    - Commit: `conductor(tracks): Mark task '<task name>' as complete`

---

## Phase Completion — Checkpointing Protocol

**Trigger:** Executed immediately after a task is completed that also concludes a phase in the track's `plan.md`.

1. **Announce Protocol Start:** Inform the user that the phase is complete and checkpointing has begun

2. **Ensure Test Coverage for Phase Changes:**
   - **2.1:** Read the track's `plan.md` to find the previous phase's checkpoint SHA. If none, scope is all changes since first commit
   - **2.2:** List changed files: `git diff --name-only <previous_checkpoint_sha> HEAD`
   - **2.3:** For each code file (exclude `.json`, `.md`, `.yaml`, etc.), verify a corresponding test file exists. If missing, create one matching the project's test naming convention and style

3. **Execute Automated Tests with Proactive Debugging:**
   - Announce the exact shell command before running
   - Execute the test command
   - If tests fail: inform user, attempt fix (max 2 attempts). If still failing, **stop and ask for guidance**

4. **Create Checkpoint Commit:**
   - Stage all changes (or create empty commit if no changes)
   - Commit: `conductor(checkpoint): Checkpoint end of Phase X`

5. **Record Phase Checkpoint SHA:**
   - **5.1:** Get checkpoint commit hash: `git log -1 --format="%H"`
   - **5.2:** In the track's `plan.md`, append `[checkpoint: <7-char-sha>]` to the completed phase heading
   - **5.3:** Write the updated `plan.md`

6. **Commit Plan Update:**
   - Stage the track's `plan.md`
   - Commit: `conductor(tracks): Mark phase '<PHASE NAME>' as complete`

7. **Announce Completion:** Tell the user the phase is done — no sign-off step; the user speaks up if something is wrong

---

## Quality Gates

Before marking any task complete, verify:

- [ ] All tests pass
- [ ] Code coverage meets requirements (>80%)
- [ ] Code follows project style guidelines (as defined in `code_styleguides/`)
- [ ] All public functions/methods are documented
- [ ] Type safety is enforced
- [ ] No linting or static analysis errors
- [ ] Works correctly on mobile (if applicable)
- [ ] Documentation updated if needed
- [ ] No security vulnerabilities introduced

---

## Commit Guidelines

### Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests
- `chore`: Maintenance tasks
- `conductor`: Conductor file updates (plan, checkpoint, tracks)

### Examples

```bash
git commit -m "feat(auth): Add remember me functionality"
git commit -m "fix(posts): Correct excerpt generation for short posts"
git commit -m "test(comments): Add tests for emoji reaction limits"
git commit -m "conductor(tracks): Mark task 'Create user model' as complete"
```

---

## Definition of Done

A task is complete when:

1. All code implemented to specification
2. Unit tests written and passing (Red → Green → Refactor completed)
3. Code coverage meets project requirements (>80%)
4. Documentation complete (if applicable)
5. Code passes all configured linting and static analysis checks
6. Works on mobile (if applicable)
7. Implementation notes added to the track's `plan.md`
8. Changes committed with proper message

---

## Development Commands

> **Customize this section per project.** Replace examples with actual project commands.

### Setup

```bash
# Install dependencies and configure environment
# e.g., npm install / go mod tidy / pip install -r requirements.txt
```

### Daily Development

```bash
# Start dev server, run tests, lint, format
# e.g., npm run dev / go run main.go / npm test
```

### Before Committing

```bash
# Run all pre-commit checks: format, lint, type check, tests
# e.g., npm run check / make check
```

---

## Testing Requirements

### Unit Testing

- Every module must have corresponding tests
- Use appropriate test setup/teardown mechanisms
- Mock external dependencies
- Test both success and failure cases

### Integration Testing

- Test complete user flows
- Verify database transactions
- Test authentication and authorization
- Check form submissions

### Mobile Testing (if applicable)

- Test touch interactions
- Verify responsive layouts
- Check performance on constrained networks

---

## Code Review — Self-Review Checklist

Before requesting review:

1. **Functionality** — Feature works as specified, edge cases handled, error messages are user-friendly
2. **Code Quality** — Follows style guide, DRY applied, clear naming, appropriate comments
3. **Testing** — Unit tests comprehensive, integration tests pass, coverage adequate (>80%)
4. **Security** — No hardcoded secrets, input validation present, injection prevented, XSS protection
5. **Performance** — Queries optimized, images optimized, caching where needed

---

## Deployment Workflow

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Coverage >80%
- [ ] No linting errors
- [ ] Mobile testing complete (if applicable)
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] Backup created

### Deployment Steps

1. Merge feature branch to main
2. Tag release with version
3. Push to deployment service
4. Run database migrations
5. Verify deployment
6. Test critical paths
7. Monitor for errors

### Post-Deployment

1. Monitor analytics
2. Check error logs
3. Gather user feedback
4. Plan next iteration
