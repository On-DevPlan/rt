 

---
name: dev-workflow
description: Use when making code changes in this RT project, before committing, or when verifying module registration
---
# RT Development Workflow

## Critical Rule

**Every code change MUST be followed by `pnpm run build` to verify compilation.**

This applies to:

- Module creation (new `module.meta.js`)
- Page/Widget creation
- CSS changes
- Import path changes
- Any file modification

## Standard Workflow

### 1. Create or Modify Files

```bash
# Module structure
src/modules/<module-id>/
  module.meta.js
  pages/
    SomePage.jsx
  widgets/
    SomeWidget.jsx
```

### 2. Register Module

In `module.meta.js`, use correct import path:

```js
// CORRECT
import { defineModule, definePage } from '../../framework/schema.js'

// WRONG - will fail
import { defineModule, definePage } from 'xxui'
```

### 3. Build Verification (MANDATORY)

```bash
pnpm run build
```

If build fails:

- Check import paths
- Verify all dependencies are installed (`@xyflow/react` etc)
- Check for typos in module meta
- Ensure file exists before registration

### 4. Common Build Errors

| Error                           | Fix                                                 |
| ------------------------------- | --------------------------------------------------- |
| Failed to resolve import "xxui" | Use`../../framework/schema.js`                    |
| Failed to resolve import "antd" | Don't use antd (not installed) or install it first  |
| Module not found                | Verify`module.meta.js` exists and path is correct |

## Module Meta Import Paths

```js
// For files in src/modules/<x>/<y>/
// The correct import is:
import { defineModule, definePage } from '../../framework/schema.js'
```

## Checklist Before Any Commit

- [ ] `pnpm run build` passes with no errors
- [ ] New files created before registration
- [ ] Import paths are correct (not `xxui`)
- [ ] Dependencies installed if added

## CSS Module Rule

When adding new CSS classes to `module.css` files:

- Use camelCase naming: `.lineActive`, `.progressTrack`
- Verify DOM structure matches CSS selector paths
- Test with inline styles first if CSS doesn't apply

## Build Pass = Safe to Test

Only after `pnpm run build` succeeds can you test the feature in browser.
