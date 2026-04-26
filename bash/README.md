# cb - Universal Clipboard Utility

A lightweight, terminal-based clipboard utility that works seamlessly across SSH sessions, containers, and any terminal environment using OSC 52 escape sequences.

## Features

- 🖥️ **Universal compatibility**: Works in SSH sessions, tmux, screen, and any OSC 52-compatible terminal
- 📋 **Bidirectional clipboard**: Copy to clipboard or paste from clipboard
- 📁 **Multiple input modes**: Files, stdin, or direct string arguments
- 🔄 **Flexible flag positioning**: Use flags before or after arguments (`cb -p file` or `cb file -p`)
- 🛣️ **Realpath support**: Copy absolute file paths with `-r` flag
- 🌍 **Unicode support**: Full UTF-8 support for international text and emoji
- 🔍 **Smart detection**: Automatic binary file detection and handling
- ⚡ **Fast and lightweight**: Pure bash implementation with minimal dependencies

## Installation

cb can be used in two ways: as a standalone executable or as a sourced bash function.

### Standalone Executable (Recommended)

```bash
# Make the script executable
chmod +x cb

# Install for current user
mkdir -p ~/.local/bin
cp ./cb ~/.local/bin/

# Ensure ~/.local/bin is on PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Sourced Function Mode

```bash
# Source the script to add cb function to your shell
source ./cb

# Or add to your ~/.bashrc for permanent availability
echo 'source /path/to/cb' >> ~/.bashrc
```

### Usage Modes Comparison

| Aspect | Standalone Executable | Sourced Function |
|--------|----------------------|------------------|
| **Shell Compatibility** | Works with any shell (zsh, fish, etc.) | Bash only |
| **Setup** | Requires executable permissions and PATH | Easy integration via ~/.bashrc |
| **Installation** | Copy to bin directory, modify PATH | Just add source line to shell config |
| **Environment** | Clean, no pollution | Adds function to shell session |
| **Portability** | Standard Unix tool behavior | Requires sourcing in each session |

**Recommendation**: Use standalone executable for cross-shell compatibility, sourced function for easy bash integration.

## Usage

### Copy Operations

```bash
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

```bash
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

### Flexible Flag Positioning

Both traditional and flexible flag positioning are supported:

```bash
# Traditional positioning
cb -p "text"
cb -r file.txt

# Flexible positioning (flags after arguments)
cb "text" -p
cb file.txt -r
```

## Examples

### Clearing the Clipboard

```bash
# Clear clipboard with empty content
echo -n "" | cb
# Output: ✓ Clipboard cleared (empty stdin content)

# Clear with empty string
cb -p ""
# Output: ✓ Clipboard cleared (empty string)

# Clear with empty file
touch empty.txt && cb empty.txt
# Output: ✓ Clipboard cleared (empty file)
```

### Basic File Operations

```bash
# Copy a configuration file
cb ~/.bashrc

# Copy a log file for analysis
cb /var/log/app.log

# Copy current directory path
cb -r .
```

### Text Processing Workflows

```bash
# Copy processed text
cat data.txt | grep "error" | cb

# Copy and then paste with modifications
cb file.txt
cb | sed 's/old/new/g' > modified.txt

# Copy clipboard content to multiple files
cb > backup1.txt
cb > backup2.txt
```

### Cross-Session Workflows

```bash
# On one machine/session
cb important-data.txt

# On another machine/session (same terminal)
cb > received-data.txt
```

### Advanced Usage

```bash
# Copy large files efficiently
cb large-dataset.csv

# Handle files with unusual names
cb -p "file with spaces.txt"
cb "file-that-looks-like-flag"

# Copy file paths for scripting
cb -r /etc/nginx/nginx.conf
# Paste the absolute path for use in scripts
echo "Editing $(cb)"
```

## How It Works

cb uses OSC 52 escape sequences to communicate directly with your terminal emulator's clipboard. **This requires an interactive terminal session** with a compatible terminal emulator. Key benefits:

- **No X11 required**: Works in pure terminal environments
- **SSH compatible**: Works over SSH without port forwarding
- **Container friendly**: Works inside Docker containers and VMs
- **Terminal emulator dependent**: Requires OSC 52 support in your terminal

**Important**: cb is designed exclusively for interactive terminal use and requires stderr to be connected to a terminal that supports OSC 52 sequences.

### Supported Terminals

- iTerm2 (macOS): OSC 52 enabled by default; paste supported.
- Terminal.app (macOS): OSC 52 supported; paste supported.
- Windows Terminal: OSC 52 copy/paste supported (recent builds).
- Alacritty: OSC 52 copy/paste supported; may require config.
- Kitty: Native clipboard integration; OSC 52 supported.
- WezTerm: Full OSC 52 support.
- tmux: Requires configuration (see below).
- screen: Limited/conditional OSC 52 support.
- Most modern terminal emulators with OSC 52 support.

## Environment Variables

- `CB_DEBUG`: Set to `1` or `true` to enable debug output

```bash
# Enable debug output
CB_DEBUG=1 cb file.txt
```

## Error Handling

cb provides clear error messages for common issues:

```bash
# File doesn't exist
cb nonexistent.txt
# Error: Cannot read file 'nonexistent.txt' - permission denied

# Directory instead of file
cb /some/directory
# Error: Cannot copy '/some/directory' - it is a directory, not a regular file
# Hint: Use -p flag to copy the literal string '/some/directory' instead

# Conflicting inputs
echo "data" | cb file.txt
# Error: Cannot accept both stdin and an argument

# Invalid flag combinations
cb -r -p file.txt
# Error: Cannot use -r and -p flags together
```

## File Type Support

- ✅ **Text files**: Full UTF-8 support with proper newline handling
- ✅ **Binary files**: Detected and copied as-is with warning
- ✅ **Large files**: Efficient handling of multi-MB files
- ✅ **Unicode content**: Emoji, international characters, mathematical symbols
- ✅ **Special files**: Handles various line endings (LF, CRLF, CR)

## Testing

The project includes a comprehensive test suite with 75 test cases covering basic functionality, edge cases, performance, Unicode support, and error conditions.

```bash
# Run all tests
python3 cb_test_framework.py --cb-path ./cb

# Run with verbose output
python3 cb_test_framework.py --cb-path ./cb --verbose
```

## Architecture

### Components

- **`cb`**: Main clipboard utility script (bash)
- **`cb_osc52_paste.py`**: OSC 52 paste implementation (Python)
- **`cb_test_framework.py`**: Comprehensive test suite (75 tests)

### Design Principles

- **Interactive-focused**: Designed specifically for terminal users
- **Robust**: Comprehensive error handling and input validation
- **Fast**: Minimal overhead with efficient operations
- **Portable**: Works across SSH, containers, and terminal multiplexers
- **Well-tested**: 100% test coverage with comprehensive test cases

## Troubleshooting

### Clipboard Not Working

1. **Check terminal support**:
   ```bash
   # Test if your terminal supports OSC 52
   printf '\033]52;c;%s\033\\' $(echo "test" | base64)
   ```

2. **Enable clipboard in tmux**:
   ```bash
   # Add to ~/.tmux.conf
   # Enable OSC 52 clipboard support
   set -g set-clipboard on
   set -g allow-passthrough on
   ```

3. **Non-bash shells**: cb is bash-only. Use bash to run it.

4. **Check permissions**:
   ```bash
   # Ensure script is executable
   chmod +x cb
   ```

### Performance Issues

```bash
# For very large files, monitor with debug output
CB_DEBUG=1 cb large-file.txt
```

### SSH Issues

Ensure your SSH client forwards OSC sequences:
- Most modern SSH clients do this automatically
- Some corporate firewalls may block OSC sequences

## Design Philosophy

cb is designed **exclusively for interactive terminal usage**. The script enforces this with an early interactive shell check that prevents use in scripts and automation, providing clear error messages to guide users toward appropriate tools for their use case.

This design choice ensures:
- **Clear user experience**: No confusing OSC 52 failures in non-terminal environments
- **Proper tool selection**: Encourages users to choose the right tool for each context
- **Terminal focus**: Optimized specifically for human terminal interaction

## Contributing

1. Make changes to the codebase
2. Run the test suite: `python3 cb_test_framework.py --cb-path ./cb`
3. Ensure 100% test success rate (75 tests)
4. Update documentation as needed

## License

This project is provided as-is for educational and practical use.

## Acknowledgments

- OSC 52 specification for enabling terminal clipboard access
- The bash and Python communities for excellent documentation
- Terminal emulator developers for OSC 52 support
