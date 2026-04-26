# cb: clipboard copy/paste CLI tool
This tool was made because of dissatisfaction with existing cli tools. They either require too long commands/flags, require a remote agent when wanting to interact with the local clipboard, or simply do not work at all over ssh.

`cb` is a minimal clipboard tool for the terminal that works wherever your terminal works, including SSH sessions, inside tmux, in containers, and on remote machines, without any special setup on the remote side.

It uses OSC 52 terminal escape sequences, which means the clipboard operation travels through the terminal connection itself. The command is kept intentionally minimal: `cb` figures out whether to copy or paste based on how you invoke it, so there is nothing extra to remember. Every operation prints a short confirmation to stderr: what was copied, how many lines and characters, so you always know the action actually happened.

```
echo "some text" | cb          # copy from stdin
cb file.txt                    # copy file contents
cb "literal string"            # copy a string (as long as it is not an existing file path)
cb -s file.txt                 # force copy as string (not file contents)
cb -r file.txt                 # copy absolute path of file
cb | grep pattern              # paste to a command
cb > output.txt                # paste to file
```

## Copy vs paste, how cb decides

`cb` detects the right mode automatically based on how it is called:

| Invocation | Behaviour |
|------------|-----------|
| `cb file.txt` | Copy file contents |
| `cb "some string"` | Copy literal string (if not an existing file path) |
| `cb -s anything` | Always copy as literal string |
| `cb -r file.txt` | Copy absolute real path of file |
| `echo text \| cb` | Copy from stdin |
| `cb \| cmd` | Paste clipboard to command |
| `cb > file` | Paste clipboard to file |

## Installation

### Pre-built binary (Linux x86_64)

Download from the [latest release](../../releases/latest):

```bash
curl -L https://github.com/gitmpr/cb_clipboard-cli-tool/releases/latest/download/cb -o ~/.local/bin/cb
chmod +x ~/.local/bin/cb
```

Make sure `~/.local/bin` is on your PATH.

### Build from source

Requires Go 1.21+:

```bash
git clone https://github.com/gitmpr/cb_clipboard-cli-tool.git
cd cb_clipboard-cli-tool/golang
go build -o cb .
mv cb ~/.local/bin/cb
```

## Options

| Flag | Description |
|------|-------------|
| `-s` | Treat argument as a literal string, not a file path |
| `-r` | Copy the absolute path of the file instead of its contents |
| `-h` | Show help |

Flags can appear before or after the argument: `cb -r file.txt` and `cb file.txt -r` both work.

## Terminal emulator support

`cb` requires a terminal emulator that supports OSC 52. As of April 2026:

| Terminal | OSC 52 support |
|----------|---------------|
| Ghostty | ✅ Full support |
| WezTerm | ✅ Full support |
| Alacritty | ✅ Full support |
| kitty | ✅ Full support |
| iTerm2 | ✅ Full support |
| Windows Terminal | ✅ Full support |
| Gnome Terminal / VTE-based | ❌ OSC 52 not implemented |

## Environment variables

| Variable | Description |
|----------|-------------|
| `CB_DEBUG` | Set to `1` to enable debug output |


## Shell script versions

This project started out as shell scripts, that were later ported to a native golang binary executable. The shell script implementations with identical behaviour are available in `bash/` and `fish/`. They can be sourced directly into your shell session or placed on your PATH, but do require a python helper function script that spawns a PTY for simulating OSC 52 input for clipboard reading

## License

MIT
