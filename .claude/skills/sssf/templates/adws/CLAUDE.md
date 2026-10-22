# ADW Interface Prompt — Code Standards

## Python Bracket & Parenthesis Spacing

This project uses a consistent bracket spacing convention to improve code readability and visual structure.

### The Standard

**Rule: Space after opening brackets, space before closing brackets. Collapse consecutive closing brackets.**

```python
# Function signatures
def method( self, arg: str ) -> None:
    pass

# Class definitions
class MyClass( BaseClass ):
    pass

# Type hints with generics
def process( items: list[ str ] ) -> dict[ str, int ]:
    pass

# Function calls
result = function( arg1, arg2 )
instance = ClassName( param )

# F-strings: apply spacing inside {}
message = f"Value is { variable }"
message = f"Type: { type( obj ).__name__ }"

# Nested/consecutive closing brackets: collapse to no space
result = outer( inner( arg ))
items: list[ str ])
```

### Key Points

1. **After opening brackets**: Always add a space
   - `( arg` ✅
   - `[ item` ✅
   - `{ value` ✅ (in f-strings)

2. **Before closing brackets**: Always add a space
   - `arg )` ✅
   - `item ]` ✅
   - `value }` ✅ (in f-strings)

3. **Consecutive closing brackets**: No space between them
   - `))` ✅ (not `) )`)
   - `])` ✅ (not `] )`)
   - `})` ✅ (not `} )`)

4. **Inside f-strings**: The spacing applies to content within `{}`
   - Expressions: `{ type( obj ).__name__ }`
   - Format specs: `{ value:x }`
   - Simple variables: `{ var }`

## Column Alignment

When a block of consecutive lines shares the same shape (parameter list, assignment
statements, or keyword arguments in a multi-line call), pad the shorter names so the
marker that follows — `:`, `=` — lines up in a common column across the whole block.

```python
# Multi-line parameter lists: align the ':' after each name
def __init__( self,
              argument_parser:  IArgumentParser,
              prompt_resolver:  IPromptResolver,
              config_loader:    IConfigLoader,
              session_factory:  ISessionFactory,
              phase_executor:   IPhaseExecutor,
              logger:           ILifecycleLog ):

# Consecutive assignments: align the '='
self._argument_parser   = argument_parser
self._prompt_resolver   = prompt_resolver
self._config_loader     = config_loader
self._session_factory   = session_factory
self._phase_executor    = phase_executor

# Multi-line calls: align the '=' of each keyword argument, and pad the
# closing paren out to the widest line so it lands in its own column
return PromptApplication(
    argument_parser =   ArgparseArgumentParser(     __doc__, bootstrap_log  ),
    prompt_resolver =   FileOrInlinePromptResolver( bootstrap_log           ),
    config_loader   =   SssfConfigLoader(           bootstrap_log           ),
    session_factory =   SessionRunFactory(          bootstrap_log           ),
    phase_executor  =   ManualContextPhaseExecutor( bootstrap_log           ),
    logger          =   bootstrap_log,                                      )
```

### Key Points

1. **Only applies within a contiguous block** of same-shape lines (one parameter
   list, one run of assignments, one call's keyword arguments) — don't align
   across unrelated statements.
2. **Pad with extra spaces before the marker**, never after — the names stay
   left-aligned, the `:`/`=` columns line up.
3. **A single line, or a block with no shared shape, is left as plain single
   spacing** (the bracket-spacing rules above still apply) — alignment padding
   is only added once there's a second line to align against.
4. Re-align the whole block whenever a new line changes the widest name.

### File References

- **adw_interface_prompt.py** — Example implementation of this standard
- Created with this spacing convention applied throughout

## Why This Standard?

This consistent spacing creates visual boundaries around all structural elements, making the code easier to scan and understand at a glance. Every bracket pair is clearly delineated with white space, improving readability without requiring external formatting tools.
