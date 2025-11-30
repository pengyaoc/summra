# Claude Instructions

## Work Log

Keep a work log for all tasks completed and in progress in `WORK_LOG.md`. Update the work log when task starts and update the status along the way. The work log would be used as future development context.

## Documentation

### PRD.md
Keep the Product Requirements Document up-to-date with user-facing feature definitions. This should include:
- Feature descriptions and user stories
- User interface specifications
- User workflows and interactions
- Feature requirements and acceptance criteria

### ERD.md
Keep the Engineering Reference Document up-to-date with technical details. This should include:
- Complex component and logic descriptions
- System components and architecture
- Database schema and data models
- Code structure and organization
- Technical implementation details

## Coding Principles

### DRY (Don't Repeat Yourself)
Follow the DRY principle to eliminate code duplication and maintain a single source of truth:

- **Identify Duplication:** When you notice identical or nearly identical code in multiple places, refactor to a shared function or method
- **Single Implementation:** Maintain one canonical implementation for each piece of logic
- **Easier Maintenance:** Changes should only need to be made in one place
- **Consistent Behavior:** Shared code ensures consistent behavior across the codebase

**Examples of DRY violations to avoid:**
- Duplicate text processing logic (e.g., separate normalization functions for different content types)
- Copy-pasted validation code
- Repeated API call patterns
- Duplicated database query logic

**How to refactor:**
1. Extract the common logic into a shared function
2. Update all call sites to use the shared function
3. Delete the duplicate implementations
4. Document the refactoring in WORK_LOG.md

**Recent example:** The `_clean_preface_text()` and `normalize_chapter_text()` methods performed identical text normalization. We eliminated the 84-line duplicate by using `normalize_chapter_text()` for both prefaces and chapters.
