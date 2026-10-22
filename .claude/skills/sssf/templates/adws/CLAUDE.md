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

### File References

- **adw_interface_prompt.py** — Example implementation of this standard
- Created with this spacing convention applied throughout

## Why This Standard?

This consistent spacing creates visual boundaries around all structural elements, making the code easier to scan and understand at a glance. Every bracket pair is clearly delineated with white space, improving readability without requiring external formatting tools.
