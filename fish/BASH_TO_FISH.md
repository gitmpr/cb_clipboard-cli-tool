# Bash to Fish Shell Porting Guide

This document outlines the key differences encountered when porting the `cb` utility from bash to fish shell, and provides guidance for similar porting efforts.

## Overview

Fish shell presents several fundamental differences from bash that require careful consideration when porting scripts. The fish philosophy emphasizes simplicity, user-friendliness, and consistency, which leads to different syntax and behavior patterns.

## Key Differences and Required Changes

### 1. Variable Expansion and String Interpolation

**Bash:**
```bash
echo "${COLOR_ERROR}Error: $*${COLOR_RESET}"
local content="$1"
```

**Fish:**
```fish
echo "$COLOR_ERROR"Error: $argv"$COLOR_RESET"
set -l content $argv[1]
```

**Key Points:**
- Fish uses `$argv` instead of `$1`, `$2`, etc.
- Fish doesn't require `${var}` syntax in most cases
- All variables in fish are lists (arrays)
- String interpolation within double quotes is more predictable
- Fish doesn't perform word splitting like bash

### 2. Function Arguments and `$argv` Handling

**Bash:**
```bash
function my_function() {
    local arg1="$1"
    local arg2="$2"
    echo "Args: $*"
}
```

**Fish:**
```fish
function my_function
    set -l arg1 $argv[1]
    set -l arg2 $argv[2]
    echo "Args:" $argv
end
```

**Key Points:**
- Fish uses `$argv` as a list for all function arguments
- Individual arguments accessed via `$argv[1]`, `$argv[2]`, etc.
- `$argv` can be used directly in most contexts without special handling
- No need for `"$@"` vs `"$*"` distinctions

### 3. `isatty` Function Behavior

**Bash:**
```bash
if [[ -t 0 ]]; then  # or: if tty -s
    echo "stdin is a terminal"
fi
```

**Fish:**
```fish
if isatty stdin
    echo "stdin is a terminal"
end
```

**Key Points:**
- Fish has a built-in `isatty` command
- Returns exit status 0 for terminal, non-zero for non-terminal
- Accepts `stdin`, `stdout`, `stderr` as string arguments
- More readable than bash's `-t` test or `tty -s`

### 4. Boolean Logic and Conditionals

**Bash:**
```bash
if [[ ! -t 0 || ! -t 1 || ! -t 2 ]]; then
    echo "Not fully interactive"
fi
```

**Fish:**
```fish
if not isatty stdin; or not isatty stdout; or not isatty stderr
    echo "Not fully interactive"
end
```

**Key Points:**
- Fish uses `not`, `and`, `or` instead of `!`, `&&`, `||` in conditions
- No `[[` construct - uses `test` command
- `test` command doesn't accept `==` (use `=` instead)
- More natural language-like syntax

### 5. Variable Declarations and Scope

**Bash:**
```bash
local my_var="value"
readonly CONSTANT="constant_value"
```

**Fish:**
```fish
set -l my_var "value"
set -g CONSTANT "constant_value"  # or set -l for local
```

**Key Points:**
- Fish uses `set` command for all variable operations
- `-l` for local scope, `-g` for global scope
- `-x` for exported variables (like bash's `export`)
- `-q` to check if variable exists

### 6. Command Substitution and Arithmetic

**Bash:**
```bash
result=$(command)
count=$((var + 1))
```

**Fish:**
```fish
set result (command)
set count (math $var + 1)
```

**Key Points:**
- Fish uses `(command)` for command substitution
- No `$((arithmetic))` - use `math` command instead
- Command substitution splits only on newlines

### 7. String Handling and Quoting

**Bash:**
```bash
# Complex quoting often needed
echo "${COLOR_CYAN}│${COLOR_RESET} ${COLOR_WHITE}cb${COLOR_RESET}"
```

**Fish:**
```fish
# Simpler quoting, but printf often better for complex strings
printf "%s│%s %scb%s\n" "$COLOR_CYAN" "$COLOR_RESET" "$COLOR_WHITE" "$COLOR_RESET"
```

**Key Points:**
- Fish string handling is more predictable
- Less need for complex quoting
- `printf` often better than `echo` for formatted output
- Variable expansion in double quotes is consistent

### 8. Function Definition Syntax

**Bash:**
```bash
function_name() {
    local var="$1"
    echo "$var"
}
```

**Fish:**
```fish
function function_name
    set -l var $argv[1]
    echo $var
end
```

**Key Points:**
- Fish uses `function name ... end` syntax
- No parentheses or braces
- More structured and readable

### 9. Error Handling and Exit Status

**Bash:**
```bash
if command; then
    echo "Success"
else
    echo "Failed with status $?"
fi
```

**Fish:**
```fish
if command
    echo "Success"
else
    echo "Failed with status $status"
fi
```

**Key Points:**
- Fish uses `$status` instead of `$?`
- Exit status handling is more consistent
- Better error propagation in pipelines

### 10. Array/List Operations

**Bash:**
```bash
array=("one" "two" "three")
echo "${array[1]}"
echo "${#array[@]}"
```

**Fish:**
```fish
set array one two three
echo $array[2]  # Fish uses 1-based indexing
echo (count $array)
```

**Key Points:**
- All variables in fish are lists
- 1-based indexing (not 0-based like bash)
- `count` command for array length
- Range operations: `$array[1..3]`

## Common Pitfalls and Solutions

### 1. Command Substitution and Word Splitting

**Problem:** Fish does NOT perform word splitting like bash, which breaks functions that return multiple space-separated values.

**Bash:**
```bash
# This works in bash - word splitting occurs
analyze() { echo "1 2 3"; }
result=$(analyze)
IFS=' ' read -r a b c <<< "$result"  # a=1, b=2, c=3
```

**Fish (BROKEN):**
```fish
# This does NOT work in fish - no word splitting
function analyze; echo "1 2 3"; end
set result (analyze)      # result is a single item: "1 2 3"
set a $result[1]          # a = "1 2 3" (not just "1")
```

**Fish (CORRECT):**
```fish
# Use newlines for multiple return values
function analyze
    printf '%s\n%s\n%s\n' 1 2 3
end
set result (analyze)      # result is now 3 separate items
set a $result[1]          # a = "1"
set b $result[2]          # b = "2"
set c $result[3]          # c = "3"
```

**Key Insight:** Fish treats command substitution output as separate list items only when separated by newlines, not spaces. This is fundamentally different from bash's word splitting behavior.

### 2. Test Command Boolean Operators

**Problem:** Fish's `test` command doesn't support bash-style `-a` (AND) and `-o` (OR) operators.

**Bash:**
```bash
if [[ -L "$file" && ! -e "$file" ]]; then
    echo "broken symlink"
fi

# Or with test command
if [ -L "$file" -a ! -e "$file" ]; then
    echo "broken symlink"
fi
```

**Fish (BROKEN):**
```fish
# This does NOT work in fish
if test -L "$file" -a not -e "$file"
    echo "broken symlink"
end
```

**Fish (CORRECT):**
```fish
# Use fish's and/or keywords instead
if test -L "$file"; and not test -e "$file"
    echo "broken symlink"
end

# Alternative syntax
if test -L "$file" && not test -e "$file"
    echo "broken symlink"
end
```

**Key Insight:** Fish's `test` command only supports single conditions. Use `and`/`or`/`&&`/`||` between separate `test` commands for complex conditions.

### 3. Stdin Detection Issues

**Problem:** Fish's `isatty` behavior in non-interactive contexts can be different from bash.

**Solution:**
```fish
# Use direct isatty calls with proper error handling
if isatty stdin
    # Handle interactive case
else
    # Handle non-interactive case
end
```

### 4. Variable Expansion in Strings

**Problem:** Complex string formatting with colors and variables.

**Solution:**
```fish
# Use printf for complex formatting instead of echo
printf '%s[DEBUG] %s%s\n' "$COLOR_MUTED" "$message" "$COLOR_RESET" >&2
```

### 5. Function Return Values

**Problem:** Bash functions can return values via `return` or by echoing.

**Solution:**
```fish
# Fish functions should echo output, use return for exit status only
function get_value
    echo "result"  # This is the return value
    return 0       # This is the exit status
end

set result (get_value)
```

### 6. Dual-Mode Detection (Sourced vs Executed)

**Problem:** Fish doesn't have equivalent of bash's `BASH_SOURCE` vs `$0` comparison for detecting script execution vs sourcing.

**Bash:**
```bash
# Standard bash dual-mode detection
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main_function "$@"
fi
```

**Fish (BROKEN):**
```fish
# This doesn't work correctly in fish
if test (status current-filename) = (status filename)
    main_function $argv
end
```

**Fish (CORRECT):**
```fish
# Use $_ to detect if script was sourced
if test "$_" != "source" -a "$_" != "."
    main_function $argv
end
```

**Key Insight:** In fish, the `$_` environment variable contains the command used to invoke the current script. When sourced, `$_` equals "source" (or its alias "."). When executed directly, `$_` contains the script path or command name. This is the most reliable method for dual-mode detection in fish.

### 7. Variable Scope Issues

**Problem:** Fish local variables with `-l` flag are only accessible within the exact scope where they're defined.

**Fish (BROKEN):**
```fish
# Color constants defined as local
set -l COLOR_RED \e'[31m'

function show_error
    printf '%s%s%s\n' "$COLOR_RED" "$argv" "$COLOR_RESET"  # Variables undefined!
end
```

**Fish (CORRECT):**
```fish
# Color constants defined as global for cross-function access
set -g COLOR_RED \e'[31m'

function show_error
    printf '%s%s%s\n' "$COLOR_RED" "$argv" "$COLOR_RESET"  # Works correctly
end
```

**Key Insight:** Unlike bash where variables defined outside functions are accessible within functions, fish requires explicit global scope (`-g`) for variables that need to be accessed across function boundaries.

## Testing and Debugging

### Enable Debug Mode
```fish
set -x CB_DEBUG 1
./cb -h  # Test with debug output
```

### Check Variable Values
```fish
# Use printf for safe debugging output
printf "Debug: var=%s\n" "$var" >&2
```

### Test with Non-Interactive Mode
```fish
# Use environment override for testing
set -x CB_ALLOW_NONINTERACTIVE 1
./cb "test string"
```

## Performance Considerations

Fish generally performs better than bash for:
- String operations
- List/array handling
- Variable expansion

Fish may be slower for:
- Heavy arithmetic operations
- Complex regular expressions
- Large file processing

## Recommendations for Future Ports

1. **Start with core logic:** Port the main algorithm first, then handle fish-specific syntax
2. **Use fish built-ins:** Leverage fish's superior built-in commands (string, math, count)
3. **Simplify conditionals:** Take advantage of fish's cleaner syntax
4. **Test thoroughly:** Fish's different behavior requires comprehensive testing
5. **Embrace fish patterns:** Don't just transliterate - adapt to fish's philosophy

## Tools and Testing

- Use fish's built-in syntax checking: `fish -n script.fish`
- Test in both interactive and non-interactive modes
- Use the same test framework with environment overrides
- Validate behavior matches original bash implementation

## Conclusion

While porting from bash to fish requires significant syntax changes, the result is often more readable and maintainable code. Fish's consistency and user-friendly design make it worth the effort for scripts that benefit from cleaner syntax and better error handling.
