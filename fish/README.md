# cb - Universal Clipboard Utility (Fish Shell)

A lightweight, terminal-based clipboard utility that works seamlessly across SSH sessions, containers, and any terminal environment using OSC 52 escape sequences. This is the **Fish shell implementation** of cb.

## Features

- 🖥️ **Universal compatibility**: Works in SSH sessions, tmux, screen, and any OSC 52-compatible terminal
- 📋 **Bidirectional clipboard**: Copy to clipboard or paste from clipboard
- 📁 **Multiple input modes**: Files, stdin, or direct string arguments
- 🔄 **Flexible flag positioning**: Use flags before or after arguments (`cb -p file` or `cb file -p`)
- 🛣️ **Realpath support**: Copy absolute file paths with `-r` flag
- 🌍 **Unicode support**: Full UTF-8 support for international text and emoji
- 🔍 **Smart detection**: Automatic binary file detection and handling
- ⚡ **Fast and lightweight**: Pure fish implementation with minimal dependencies
- 🐠 **Fish-optimized**: Takes advantage of fish shell's cleaner syntax and better string handling

## Fish Shell Advantages

This fish implementation provides several improvements over the bash version:

- **Cleaner string handling**: No need for sentinel tricks to preserve trailing newlines
- **Better variable scoping**: Fish's function-local variables are more predictable
- **Simpler syntax**: More readable test expressions and conditionals
- **Consistent quoting**: Fish's string handling is more intuitive
- **Better error handling**: More predictable exit behavior

## Installation

### Standalone Executable (Recommended)

```fish
# Make the script executable
chmod +x cb

# Install for current user
mkdir -p ~/.local/bin
cp ./cb ~/.local/bin/

# Ensure ~/.local/bin is on PATH (fish automatically checks ~/.local/bin)
```

### Function Mode (Fish-specific)

```fish
# Source the script to add cb function to your fish session
source ./cb

# Or add to your ~/.config/fish/config.fish for permanent availability
echo 'source /path/to/cb' >> ~/.config/fish/config.fish
```

## Usage

### Copy Operations

```fish
# Copy file contents to clipboard
cb file.txt

# Copy text from stdin
echo "Hello World" | cb
cat document.txt | cb

# Copy literal string (treat as text, not filename)
cb -p "filename.txt"
cb "some text string"

# Copy absolute file path instead of contents
cb -r script.sh
cb /path/to/file.txt -r
```

### Paste Operations

```fish
# Paste to stdout
cb | cat

# Paste to file
cb > output.txt

# Paste and process
cb | grep "pattern"
cb | sort | uniq
```

### Flag Options

- `-p` : Treat argument as literal string (not file path)
- `-r` : Copy absolute path of file instead of contents
- `-h` : Show help message

### Fish-Specific Features

Fish's superior string handling makes cb more reliable:

```fish
# Fish handles complex strings better
cb "text with 'quotes' and \$variables"

# No need for complex escaping
cb -p 'filename with spaces.txt'

# Better Unicode support
cb "emoji 🐠 and unicode ✨"
```

## Examples

### Basic Operations

```fish
# Copy a configuration file
cb ~/.config/fish/config.fish

# Copy current directory path
cb -r .

# Clear clipboard
echo -n "" | cb
```

### Fish Scripting Integration

```fish
# Use in fish functions
function copy_config
    cb ~/.config/fish/config.fish
    echo "Fish config copied to clipboard"
end

# Pipe processing with fish
cb data.txt
cb | string split '\n' | string match '*error*' > errors.txt
```

## How It Works

cb uses OSC 52 escape sequences to communicate directly with your terminal emulator's clipboard. **This requires an interactive terminal session** with a compatible terminal emulator.

**Important**: cb is designed exclusively for interactive terminal use and requires stderr to be connected to a terminal that supports OSC 52 sequences.

### Supported Terminals

- iTerm2 (macOS): OSC 52 enabled by default; paste supported.
- Terminal.app (macOS): OSC 52 supported; paste supported.
- Windows Terminal: OSC 52 copy/paste supported (recent builds).
- Alacritty: OSC 52 copy/paste supported; may require config.
- Kitty: Native clipboard integration; OSC 52 supported.
- WezTerm: Full OSC 52 support.
- tmux: Requires configuration (see troubleshooting).
- Most modern terminal emulators with OSC 52 support.

## Environment Variables

- `CB_DEBUG`: Set to `1` or `true` to enable debug output
- `CB_ALLOW_NONINTERACTIVE`: Set to `1` to bypass interactive checks (testing only)

```fish
# Enable debug output
set -x CB_DEBUG 1
cb file.txt
```

## Fish vs Bash Implementation

| Feature | Fish Implementation | Bash Implementation |
|---------|-------------------|-------------------|
| **String Handling** | Native fish strings, no sentinel tricks | Requires `${var%x}` sentinel pattern |
| **Variable Scoping** | Clean function-local variables | Requires `local` declarations |
| **Syntax** | Clean `test` expressions | Complex `[[ ]]` syntax |
| **Unicode** | Superior UTF-8 handling | Good but requires more care |
| **Error Handling** | Predictable `return` behavior | More complex exit handling |
| **Readability** | More concise and readable | More verbose |

## Error Handling

cb provides clear error messages for common issues:

```fish
# File doesn't exist - same as bash version
cb nonexistent.txt
# Error: Cannot read file 'nonexistent.txt' - permission denied

# Directory instead of file
cb /some/directory
# Error: Cannot copy '/some/directory' - it is a directory, not a regular file
# Hint: Use -p flag to copy the literal string '/some/directory' instead
```

## Architecture

### Components

- **`cb`**: Main clipboard utility script (fish)
- **`cb_osc52_paste.py`**: OSC 52 paste implementation (Python, shared with bash version)

### Design Principles

- **Fish-native**: Written idiomatically for fish shell
- **Interactive-focused**: Designed specifically for terminal users
- **Robust**: Comprehensive error handling and input validation
- **Portable**: Works across SSH, containers, and terminal multiplexers
- **Clean**: Takes advantage of fish's superior syntax

## Troubleshooting

### Fish-Specific Issues

1. **Function conflicts**: If you have other `cb` functions defined:
   ```fish
   functions -e cb  # Remove existing cb function
   source ./cb      # Re-source the script
   ```

2. **Path issues**: Fish automatically includes `~/.local/bin` in PATH, but you can verify:
   ```fish
   echo $PATH | grep .local/bin
   ```

3. **Fish version**: Ensure you're using Fish 3.0+ for best compatibility:
   ```fish
   fish --version
   ```

### General OSC 52 Issues

1. **Check terminal support**:
   ```fish
   # Test if your terminal supports OSC 52
   printf '\e]52;c;%s\e\\' (echo "test" | base64)
   ```

2. **Enable clipboard in tmux**:
   ```fish
   # Add to ~/.tmux.conf
   # Enable OSC 52 clipboard support
   set -g set-clipboard on
   set -g allow-passthrough on
   ```

## Contributing

1. Make changes to the fish implementation
2. Test manually with various inputs
3. Ensure compatibility with the bash version's behavior
4. Update documentation as needed

## License

This project is provided as-is for educational and practical use.

## Acknowledgments

- OSC 52 specification for enabling terminal clipboard access
- The fish shell community for excellent documentation and tools
- Terminal emulator developers for OSC 52 support
- The original bash implementation that this fish version is based on
