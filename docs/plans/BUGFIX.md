# Post-Refactor Bug Fixes

The refactor has several bugs that need fixing. Fix ALL of these issues, then run the contract tests to verify. Commit when done.

## BUG LIST

### 1. scripts/open_computer_use_mcp_server.py: ModuleNotFoundError
`from open_computer_use import server` fails because the project root is not on sys.path. Fix: add sys.path insert at top pointing to parent of scripts/.

### 2. open_computer_use/backends/linux_x11.py line 43: syntax error
Missing closing paren. `"height": int(size[1]}` should be `"height": int(size[1])}`.

### 3. open_computer_use/backends/linux_x11.py line 160: broken _activate_app call
The call `_activate_app(app.get(...)` is missing closing paren, and the function signature takes a list not a single window. Also references undefined `code` variable on the next line. Rewrite the app-found branch cleanly.

### 4. open_computer_use/backends/linux_x11.py line 531-532: incomplete create_backend()
`create_backend()` has no body. Add `return LinuxX11Backend()`.

### 5. open_computer_use/types.py lines 17-18: duplicate LAST_APP
`LAST_APP` is defined twice. Remove the duplicate.

### 6. open_computer_use/server.py tool handlers: duplicate kwargs
`tool_click`, `tool_scroll`, `tool_set_value`, `tool_perform_secondary_action` pass `**args` which includes already-extracted kwargs (element_index, x, y, etc) causing duplicate keyword arguments. Remove the `**args` spread or filter out already-extracted keys.

### 7. open_computer_use/server.py tool_get_app_state: LAST_APP conflict
References `from .types import LAST_APP` and then `global LAST_APP` which conflicts. Fix to import and mutate the module-level variable properly via `types.LAST_APP = app_name`.

### 8. open_computer_use/backends/fake.py: ELEMENT_CACHE not populated
`get_accessibility_tree` does not populate ELEMENT_CACHE, so element_from_index fails for any test that calls get_app_state then click. Populate the cache with fake elements matching the tree.

### 9. open_computer_use/server.py: eager backend initialization
Backend is initialized at module level which causes import side effects. Make it lazy (initialize on first use).

## VERIFICATION

After fixing all bugs, run:
```
OPEN_CU_BACKEND=fake python3 scripts/open_computer_use_mcp_server.py --self-test
```
Then run:
```
OPEN_CU_BACKEND=fake python3 -m pytest tests/test_mcp_contract.py -v
```

Commit all fixes with message: `fix: resolve post-refactor bugs and test failures`
