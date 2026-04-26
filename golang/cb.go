package main

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"golang.org/x/term"
)

type BoxChars struct {
	TopLeft     string
	TopRight    string
	BottomLeft  string
	BottomRight string
	Horizontal  string
	Vertical    string
	TeeLeft     string
	TeeRight    string
}

type Colors struct {
	Black         string
	Red           string
	Green         string
	Yellow        string
	Blue          string
	Magenta       string
	Cyan          string
	White         string
	BrightBlack   string
	BrightRed     string
	BrightGreen   string
	BrightYellow  string
	BrightBlue    string
	BrightMagenta string
	BrightCyan    string
	BrightWhite   string
	NC            string
}

var boxChars = BoxChars{
	TopLeft:     "╭",
	TopRight:    "╮",
	BottomLeft:  "╰",
	BottomRight: "╯",
	Horizontal:  "─",
	Vertical:    "│",
	TeeLeft:     "├",
	TeeRight:    "┤",
}

var colors Colors
var cachedTerminalWidth int
var colorsSetup bool

func setupColors() {
	if colorsSetup {
		return
	}
	colorsSetup = true
	if term.IsTerminal(int(os.Stderr.Fd())) {
		colors = Colors{
			Black:         "\033[0;30m",
			Red:           "\033[0;31m",
			Green:         "\033[0;32m",
			Yellow:        "\033[0;33m",
			Blue:          "\033[0;34m",
			Magenta:       "\033[0;35m",
			Cyan:          "\033[0;36m",
			White:         "\033[1;37m",
			BrightBlack:   "\033[0;90m",
			BrightRed:     "\033[0;91m",
			BrightGreen:   "\033[0;92m",
			BrightYellow:  "\033[0;93m",
			BrightBlue:    "\033[0;94m",
			BrightMagenta: "\033[0;95m",
			BrightCyan:    "\033[0;96m",
			BrightWhite:   "\033[1;97m",
			NC:            "\033[0m",
		}
	}
}

func calculateVisibleLength(str string) int {
	ansiRegex := regexp.MustCompile(`\x1b\[[0-9;]*m`)
	cleaned := ansiRegex.ReplaceAllString(str, "")
	return utf8.RuneCountInString(cleaned)
}

func wordWrapLine(line string, maxWidth int) []string {
	if calculateVisibleLength(line) <= maxWidth {
		return []string{line}
	}
	words := splitWords(line)
	var result []string
	var currentLine strings.Builder
	currentVisibleLength := 0
	for _, word := range words {
		wordLen := calculateVisibleLength(word)
		var newLen int
		if currentLine.Len() > 0 {
			newLen = currentVisibleLength + 1 + wordLen
		} else {
			newLen = wordLen
		}
		if newLen <= maxWidth {
			if currentLine.Len() > 0 {
				currentLine.WriteString(" ")
				currentVisibleLength++
			}
			currentLine.WriteString(word)
			currentVisibleLength += wordLen
		} else {
			if currentLine.Len() > 0 {
				result = append(result, currentLine.String())
				currentLine.Reset()
			}
			currentLine.WriteString(word)
			currentVisibleLength = wordLen
		}
	}
	if currentLine.Len() > 0 {
		result = append(result, currentLine.String())
	}
	return result
}

func splitWords(line string) []string {
	var words []string
	var currentWord strings.Builder
	inEscape := false
	for _, char := range line {
		if char == '\033' {
			inEscape = true
			currentWord.WriteRune(char)
		} else if inEscape {
			currentWord.WriteRune(char)
			if char == 'm' {
				inEscape = false
			}
		} else if char == ' ' {
			if currentWord.Len() > 0 {
				words = append(words, currentWord.String())
				currentWord.Reset()
			}
		} else {
			currentWord.WriteRune(char)
		}
	}
	if currentWord.Len() > 0 {
		words = append(words, currentWord.String())
	}
	return words
}

func processContentForWidth(inputContent []string, terminalWidth int) []string {
	maxContentWidth := terminalWidth - 4
	if maxContentWidth < 20 {
		maxContentWidth = 20
	}
	var outputContent []string
	for _, line := range inputContent {
		if line == "---EMPTY---" || line == "---SEPARATOR---" {
			outputContent = append(outputContent, line)
		} else {
			outputContent = append(outputContent, wordWrapLine(line, maxContentWidth)...)
		}
	}
	return outputContent
}

func buildContentLine(content string, boxWidth int) string {
	contentLength := calculateVisibleLength(content)
	availableWidth := boxWidth - 4
	paddingNeeded := availableWidth - contentLength
	if paddingNeeded < 0 {
		paddingNeeded = 0
	}
	padding := strings.Repeat(" ", paddingNeeded)
	return fmt.Sprintf("%s%s%s %s%s %s%s%s", colors.Cyan, boxChars.Vertical, colors.NC, content, padding, colors.Cyan, boxChars.Vertical, colors.NC)
}

func buildHorizontalLine(lineType string, boxWidth int) string {
	var leftChar, rightChar string
	switch lineType {
	case "top":
		leftChar = boxChars.TopLeft
		rightChar = boxChars.TopRight
	case "bottom":
		leftChar = boxChars.BottomLeft
		rightChar = boxChars.BottomRight
	case "separator":
		leftChar = boxChars.TeeLeft
		rightChar = boxChars.TeeRight
	default:
		return ""
	}
	horizontalChars := strings.Repeat(boxChars.Horizontal, boxWidth-2)
	return fmt.Sprintf("%s%s%s%s%s", colors.Cyan, leftChar, horizontalChars, rightChar, colors.NC)
}

func buildEmptyLine(boxWidth int) string {
	spaces := strings.Repeat(" ", boxWidth-2)
	return fmt.Sprintf("%s%s%s%s%s", colors.Cyan, boxChars.Vertical, spaces, boxChars.Vertical, colors.NC)
}

func calculateBoxWidth(contentArray []string, minWidth, maxWidth int) int {
	maxContentLength := 0
	for _, line := range contentArray {
		if l := calculateVisibleLength(line); l > maxContentLength {
			maxContentLength = l
		}
	}
	finalWidth := maxContentLength + 4
	if finalWidth < minWidth {
		finalWidth = minWidth
	}
	if maxWidth > 0 && finalWidth > maxWidth {
		finalWidth = maxWidth
	}
	return finalWidth
}

func getTerminalWidth() int {
	if cachedTerminalWidth == 0 {
		width, _, err := term.GetSize(int(os.Stdout.Fd()))
		if err != nil {
			cachedTerminalWidth = 80
		} else {
			cachedTerminalWidth = width
		}
	}
	return cachedTerminalWidth
}

func renderBox(title string, lines []string, minWidth int, showSeparator bool, terminalWidth int) {
	if terminalWidth == 0 {
		terminalWidth = getTerminalWidth()
	}
	processedContent := processContentForWidth(lines, terminalWidth)
	var allContent []string
	if title != "" {
		allContent = append(allContent, title)
	}
	allContent = append(allContent, processedContent...)
	boxWidth := calculateBoxWidth(allContent, minWidth, terminalWidth)
	fmt.Println(buildHorizontalLine("top", boxWidth))
	if title != "" {
		fmt.Println(buildContentLine(title, boxWidth))
		if showSeparator {
			fmt.Println(buildHorizontalLine("separator", boxWidth))
		}
	}
	for _, line := range processedContent {
		switch line {
		case "---EMPTY---":
			fmt.Println(buildEmptyLine(boxWidth))
		case "---SEPARATOR---":
			fmt.Println(buildHorizontalLine("separator", boxWidth))
		default:
			fmt.Println(buildContentLine(line, boxWidth))
		}
	}
	fmt.Println(buildHorizontalLine("bottom", boxWidth))
}

// =============================================================================
// CORE FUNCTIONALITY
// =============================================================================

func isTTY(fd uintptr) bool {
	return term.IsTerminal(int(fd))
}

func debugLog(format string, args ...interface{}) {
	debug := os.Getenv("CB_DEBUG")
	if debug == "1" || debug == "true" {
		msg := fmt.Sprintf(format, args...)
		fmt.Fprintf(os.Stderr, "%s[DEBUG] %s%s\n", colors.BrightBlack, msg, colors.NC)
	}
}

func errorExit(msg string) {
	lines := strings.SplitN(msg, "\n", 2)
	fmt.Fprintf(os.Stderr, "%sError: %s%s\n", colors.Red, lines[0], colors.NC)
	if len(lines) > 1 {
		fmt.Fprintf(os.Stderr, "%s%s%s\n", colors.Cyan, lines[1], colors.NC)
	}
	os.Exit(1)
}

func copyToClipboard(content string) {
	var b64Content string
	if len(content) > 0 {
		b64Content = base64.StdEncoding.EncodeToString([]byte(content))
	}
	if b64Content != "" {
		fmt.Fprintf(os.Stderr, "\033]52;c;%s\033\\", b64Content)
	} else {
		fmt.Fprintf(os.Stderr, "\033]52;c;\033\\")
	}
}

func analyzeInput(text string) (lineCount, charCount int, hasTrailingNL bool) {
	charCount = len(text)
	if charCount == 0 {
		return 0, 0, false
	}
	hasTrailingNL = strings.HasSuffix(text, "\n")
	newlineCount := strings.Count(text, "\n")
	if hasTrailingNL {
		lineCount = newlineCount
	} else {
		lineCount = newlineCount + 1
	}
	return
}

func isBinaryFile(filename string) bool {
	f, err := os.Open(filename)
	if err != nil {
		return false
	}
	defer f.Close()
	buf := make([]byte, 1024)
	n, err := f.Read(buf)
	if err != nil && err != io.EOF {
		return false
	}
	return bytes.IndexByte(buf[:n], 0) >= 0
}

func getAbsolutePath(path string) string {
	abs, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	return abs
}

// =============================================================================
// HANDLERS
// =============================================================================

func handleStdin() {
	debugLog("Reading from stdin")
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sError reading stdin: %v%s\n", colors.Red, err, colors.NC)
		os.Exit(1)
	}
	content := string(data)
	lineCount, charCount, hasTrailingNL := analyzeInput(content)

	if charCount == 0 {
		fmt.Fprintf(os.Stderr, "%sCopying empty content from stdin%s\n", colors.Cyan, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%sCopying content from stdin%s\n", colors.Cyan, colors.NC)
	}

	copyToClipboard(content)

	if charCount == 0 {
		fmt.Fprintf(os.Stderr, "%s✓ Clipboard cleared (empty stdin content)%s\n", colors.Magenta, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%s✓ Stdin content copied to clipboard: %s%d%s lines, %s%d%s characters%s\n",
			colors.Magenta, colors.BrightYellow, lineCount, colors.Magenta,
			colors.BrightYellow, charCount, colors.Magenta, colors.NC)
		if hasTrailingNL {
			fmt.Fprintf(os.Stderr, "  %s(ends with newline - good for terminal output)%s\n", colors.BrightBlack, colors.NC)
		} else {
			fmt.Fprintf(os.Stderr, "  %s(no trailing newline - may cause display issues)%s\n", colors.Yellow, colors.NC)
		}
	}
}

func handleFile(path string) {
	if isBinaryFile(path) {
		fmt.Fprintf(os.Stderr, "%sWarning: Copying binary file '%s' - content will be copied as-is%s\n", colors.Yellow, path, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%sCopying text file '%s'%s\n", colors.Cyan, path, colors.NC)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sError: Failed to read file '%s': %v%s\n", colors.Red, path, err, colors.NC)
		os.Exit(1)
	}

	content := string(data)
	lineCount, charCount, hasTrailingNL := analyzeInput(content)

	if charCount == 0 {
		fmt.Fprintf(os.Stderr, "%sCopying empty file '%s'%s\n", colors.Cyan, path, colors.NC)
	}

	copyToClipboard(content)

	if charCount == 0 {
		fmt.Fprintf(os.Stderr, "%s✓ Clipboard cleared (empty file)%s\n", colors.Green, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%s✓ File contents copied to clipboard: %s%d%s lines, %s%d%s characters%s\n",
			colors.Green, colors.BrightYellow, lineCount, colors.Green,
			colors.BrightYellow, charCount, colors.Green, colors.NC)
		if hasTrailingNL {
			fmt.Fprintf(os.Stderr, "  %s(file ends with newline - standard format)%s\n", colors.BrightBlack, colors.NC)
		} else {
			fmt.Fprintf(os.Stderr, "  %s(file missing final newline - not POSIX compliant)%s\n", colors.Yellow, colors.NC)
		}
	}
}

func handleString(text string, forced bool) {
	if forced {
		fmt.Fprintf(os.Stderr, "%sCopying literal string argument (forced with -s flag)%s\n", colors.Cyan, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%sCopying string argument%s\n", colors.Cyan, colors.NC)
	}

	lineCount, charCount, hasTrailingNL := analyzeInput(text)
	copyToClipboard(text)

	if charCount == 0 {
		fmt.Fprintf(os.Stderr, "%s✓ Clipboard cleared (empty string)%s\n", colors.Yellow, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%s✓ String copied to clipboard: %s%d%s lines, %s%d%s characters%s\n",
			colors.Yellow, colors.BrightYellow, lineCount, colors.Yellow,
			colors.BrightYellow, charCount, colors.Yellow, colors.NC)
		if hasTrailingNL {
			fmt.Fprintf(os.Stderr, "  %s(string ends with newline)%s\n", colors.BrightBlack, colors.NC)
		} else {
			fmt.Fprintf(os.Stderr, "  %s(string without trailing newline)%s\n", colors.BrightCyan, colors.NC)
		}
	}
}

func handleRealpath(path string) {
	abs := getAbsolutePath(path)
	if _, err := os.Stat(path); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "%sWarning: '%s' does not exist - copying hypothetical absolute path%s\n", colors.Yellow, path, colors.NC)
	} else {
		fmt.Fprintf(os.Stderr, "%sCopying absolute path of '%s'%s\n", colors.Cyan, path, colors.NC)
	}
	copyToClipboard(abs)
	fmt.Fprintf(os.Stderr, "%s✓ Path copied to clipboard: %s%s%s%s\n", colors.Green, colors.BrightYellow, abs, colors.Green, colors.NC)
}

var osc52ResponseRe = regexp.MustCompile(`\x1b\]52;c;([A-Za-z0-9+/=]*)`)

func pasteFromClipboard(timeout float64) (string, error) {
	// Open /dev/tty directly so paste works even when stdout is redirected
	ttyFile, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return "", fmt.Errorf("cannot open terminal: %w", err)
	}
	defer ttyFile.Close()

	fd := int(ttyFile.Fd())

	oldState, err := term.MakeRaw(fd)
	if err != nil {
		return "", fmt.Errorf("cannot set raw mode: %w", err)
	}
	defer term.Restore(fd, oldState)

	// Send OSC52 paste query
	if _, err := ttyFile.Write([]byte("\033]52;c;?\033\\")); err != nil {
		return "", fmt.Errorf("cannot query clipboard: %w", err)
	}

	type result struct {
		content string
		err     error
	}
	ch := make(chan result, 1)

	go func() {
		var buf []byte
		tmp := make([]byte, 4096)
		for {
			n, err := ttyFile.Read(tmp)
			if n > 0 {
				buf = append(buf, tmp[:n]...)
				if m := osc52ResponseRe.FindSubmatch(buf); m != nil {
					decoded, decErr := base64.StdEncoding.DecodeString(string(m[1]))
					if decErr != nil {
						ch <- result{"", fmt.Errorf("base64 decode error: %w", decErr)}
						return
					}
					s := string(decoded)
					if s == " " { // OSC52 convention: single space = empty clipboard
						s = ""
					}
					ch <- result{s, nil}
					return
				}
			}
			if err != nil {
				ch <- result{"", fmt.Errorf("read error: %w", err)}
				return
			}
		}
	}()

	select {
	case r := <-ch:
		return r.content, r.err
	case <-time.After(time.Duration(float64(time.Second) * timeout)):
		return "", fmt.Errorf("timeout waiting for clipboard response")
	}
}

func handlePaste() {
	content, err := pasteFromClipboard(2.0)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%sError: Could not read from clipboard: %v%s\n", colors.Red, err, colors.NC)
		os.Exit(1)
	}
	fmt.Print(content)
}

// =============================================================================
// HELP
// =============================================================================

func showUsageSimple() {
	setupColors()
	fmt.Printf("%scb%s %s- Universal clipboard utility%s\n", colors.White, colors.NC, colors.BrightCyan, colors.NC)
	fmt.Println()
	fmt.Printf("%sUsage:%s %scb%s %s[-s] [-r]%s %s[string|filename]%s\n", colors.Yellow, colors.NC, colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC)
	fmt.Println()
	fmt.Printf("%sDescription:%s\n", colors.Yellow, colors.NC)
	fmt.Println("  Copies text or file contents to the clipboard or pastes clipboard contents")
	fmt.Println("  depending on output destination. Works via OSC 52 escape sequences.")
	fmt.Println("  Designed for interactive terminal use only (not scripts).")
	fmt.Println()
	fmt.Printf("%sCopy Modes:%s\n", colors.Yellow, colors.NC)
	fmt.Printf("  %sFrom stdin:%s    %secho%s %s\"text\"%s %s|%s %scb%s\n", colors.BrightGreen, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.White, colors.NC, colors.White, colors.NC)
	fmt.Printf("  %sFrom file:%s     %scb%s %sfilename.txt%s\n", colors.BrightGreen, colors.NC, colors.White, colors.NC, colors.Green, colors.NC)
	fmt.Printf("  %sFrom string:%s   %scb%s %s'some text'%s\n", colors.BrightGreen, colors.NC, colors.White, colors.NC, colors.Green, colors.NC)
	fmt.Println()
	fmt.Printf("%sPaste Modes:%s\n", colors.Yellow, colors.NC)
	fmt.Printf("  %sTo pipe:%s       %scb%s %s|%s %ssort%s\n", colors.BrightGreen, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.White, colors.NC)
	fmt.Printf("  %sTo file:%s       %scb%s %s>%s %soutput.txt%s\n", colors.BrightGreen, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC)
	fmt.Println()
	fmt.Printf("%sOptions:%s\n", colors.Yellow, colors.NC)
	fmt.Printf("  %s-s%s    Treat argument as literal string (not file path)\n", colors.Blue, colors.NC)
	fmt.Printf("  %s-r%s    Copy absolute path of file instead of contents\n", colors.Blue, colors.NC)
	fmt.Printf("  %s-h%s    Show this help message\n", colors.Blue, colors.NC)
	fmt.Println()
	fmt.Printf("%sEnvironment:%s\n", colors.Yellow, colors.NC)
	fmt.Printf("  %sCB_DEBUG%s    Enable debug output (set to 1 or true)\n", colors.Green, colors.NC)
	fmt.Println()
	fmt.Printf("%sExamples:%s\n", colors.Yellow, colors.NC)
	fmt.Printf("  %scat%s %sfile.txt%s %s|%s %scb%s         %s# Copy file via pipe%s\n", colors.White, colors.NC, colors.Green, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Magenta, colors.NC)
	fmt.Printf("  %scb%s %simportant.log%s          %s# Copy file contents%s\n", colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC)
	fmt.Printf("  %scb%s %s-s%s %sfilename.txt%s        %s# Copy literal string%s\n", colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC)
	fmt.Printf("  %scb%s %s-r%s %sscript.sh%s           %s# Copy absolute path%s\n", colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC)
	fmt.Printf("  %scb%s %s|%s %sgrep%s %spattern%s         %s# Paste and filter%s\n", colors.White, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC)
	fmt.Printf("  %scb%s %s>%s %sbackup.txt%s           %s# Paste to file%s\n", colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC)
}

func showUsage() {
	termWidth := getTerminalWidth()
	// Respect COLUMNS env var (used by tests and some terminals)
	if col := os.Getenv("COLUMNS"); col != "" {
		var w int
		if _, err := fmt.Sscanf(col, "%d", &w); err == nil && w > 0 {
			termWidth = w
		}
	}
	if termWidth < 78 {
		showUsageSimple()
		return
	}
	setupColors()
	content := []string{
		fmt.Sprintf("%scb%s %s- Universal clipboard utility%s", colors.White, colors.NC, colors.BrightCyan, colors.NC),
		"---SEPARATOR---",
		fmt.Sprintf("%sUsage:%s %scb%s %s[-s] [-r]%s %s[string|filename]%s", colors.Yellow, colors.NC, colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("%sDescription:%s", colors.Yellow, colors.NC),
		"Copies text or file contents to the clipboard or pastes clipboard contents",
		"depending on output destination. Works via OSC 52 escape sequences.",
		"Designed for interactive terminal use only (not scripts).",
		"---EMPTY---",
		fmt.Sprintf("%sCopy Modes:%s", colors.Yellow, colors.NC),
		fmt.Sprintf("  %sFrom stdin:%s", colors.BrightGreen, colors.NC),
		fmt.Sprintf("     %secho%s %s\"some string\"%s %s|%s %scb%s", colors.White, colors.NC, colors.Green, colors.NC, colors.White, colors.NC, colors.White, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("  %sFrom file:%s", colors.BrightGreen, colors.NC),
		fmt.Sprintf("     %scb%s %s/path/to/file%s                    %s# Copy file contents%s", colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("  %sFrom string:%s", colors.BrightGreen, colors.NC),
		fmt.Sprintf("     %scb%s %s'some string'%s                    %s# Copy literal string%s", colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("%sPaste Modes:%s", colors.Yellow, colors.NC),
		fmt.Sprintf("  %sTo pipe:%s", colors.BrightGreen, colors.NC),
		fmt.Sprintf("     %scb%s %s|%s %ssort%s                           %s# Paste to command%s", colors.White, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Magenta, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("  %sTo file:%s", colors.BrightGreen, colors.NC),
		fmt.Sprintf("     %scb%s %s>%s %soutput.txt%s                     %s# Paste to new file%s", colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("%sOptions:%s", colors.Yellow, colors.NC),
		fmt.Sprintf("  %s-s%s          Treat argument as literal string (not file path)", colors.Blue, colors.NC),
		fmt.Sprintf("  %s-r%s          Copy absolute path of file instead of contents", colors.Blue, colors.NC),
		fmt.Sprintf("  %s-h%s          Show this help message", colors.Blue, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("%sEnvironment:%s", colors.Yellow, colors.NC),
		fmt.Sprintf("  %sCB_DEBUG%s    Enable debug output (set to 1 or true)", colors.Green, colors.NC),
		"---EMPTY---",
		fmt.Sprintf("%sExamples:%s", colors.Yellow, colors.NC),
		fmt.Sprintf("  %scat%s %sfile.txt%s %s|%s %scb%s                 %s# Copy file via pipe%s", colors.White, colors.NC, colors.Green, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %simportant.log%s                  %s# Copy file contents%s", colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %s-s%s %sfilename.txt%s                %s# Copy literal string%s", colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %sfilename.txt%s %s-s%s                %s# Copy literal string (flexible)%s", colors.White, colors.NC, colors.Green, colors.NC, colors.Blue, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %s-r%s %sscript.sh%s                   %s# Copy absolute path%s", colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %secho%s %s-n%s %s\"\"%s %s|%s %scb%s                   %s# Clear clipboard%s", colors.White, colors.NC, colors.Blue, colors.NC, colors.Green, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %s|%s %sgrep%s %spattern%s                 %s# Paste and filter%s", colors.White, colors.NC, colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
		fmt.Sprintf("  %scb%s %s>%s %sbackup.txt%s                   %s# Paste to file%s", colors.White, colors.NC, colors.White, colors.NC, colors.Green, colors.NC, colors.Magenta, colors.NC),
	}
	renderBox("", content, 76, false, getTerminalWidth())
}

// =============================================================================
// MAIN
// =============================================================================

func main() {
	setupColors()

	// Interactive mode check — bypass with CB_ALLOW_NONINTERACTIVE=1
	if os.Getenv("CB_ALLOW_NONINTERACTIVE") != "1" {
		stdinTTY := isTTY(os.Stdin.Fd())
		stdoutTTY := isTTY(os.Stdout.Fd())
		stderrTTY := isTTY(os.Stderr.Fd())
		if !stdinTTY || !stdoutTTY || !stderrTTY {
			if !stdinTTY && stdoutTTY && stderrTTY {
				// echo "text" | cb — piped stdin is fine
				debugLog("Allowing piped stdin to terminal")
			} else if stdinTTY && !stdoutTTY && stderrTTY {
				// cb > file — stdout redirect is fine (paste mode)
				debugLog("Allowing stdout redirect from terminal")
			} else {
				fmt.Fprintln(os.Stderr, "Error: cb is designed for interactive use only. It will not work correctly in scripts due to OSC 52 terminal requirements.")
				fmt.Fprintln(os.Stderr, "Hint: cb is meant for terminal users, not automation. Use other clipboard tools for scripting.")
				os.Exit(1)
			}
		}
	}

	// Parse flags — support flexible positioning (flags can appear before or after args)
	forceString := false
	copyRealpath := false
	sFlagCount := 0
	rFlagCount := 0
	var args []string

	for _, arg := range os.Args[1:] {
		switch arg {
		case "-s":
			sFlagCount++
			if sFlagCount > 1 {
				errorExit("Invalid option: -s (flag already specified)")
			}
			forceString = true
		case "-r":
			rFlagCount++
			if rFlagCount > 1 {
				errorExit("Invalid option: -r (flag already specified)")
			}
			copyRealpath = true
		case "-h", "--help":
			showUsage()
			os.Exit(0)
		default:
			// Reject unknown single-letter alpha flags (matching bash behaviour)
			if len(arg) == 2 && arg[0] == '-' && ((arg[1] >= 'a' && arg[1] <= 'z') || (arg[1] >= 'A' && arg[1] <= 'Z')) {
				errorExit(fmt.Sprintf("Invalid option: %s", arg))
			}
			args = append(args, arg)
		}
	}

	// Validate flag combinations
	if copyRealpath && forceString {
		errorExit("Cannot use -r and -s flags together")
	}
	if copyRealpath && len(args) == 0 {
		errorExit("-r flag requires a file path argument")
	}

	stdinTTY := isTTY(os.Stdin.Fd())
	stdoutTTY := isTTY(os.Stdout.Fd())

	// Stdin + argument conflict
	if len(args) > 0 && !stdinTTY {
		errorExit("Cannot accept both stdin and an argument")
	}

	// Paste mode: stdout is redirected, stdin is tty, no args
	if !stdoutTTY && stdinTTY && len(args) == 0 {
		handlePaste()
		return
	}

	switch len(args) {
	case 0:
		if stdinTTY {
			showUsage()
			os.Exit(1)
		}
		handleStdin()
	case 1:
		arg := args[0]
		switch {
		case copyRealpath:
			handleRealpath(arg)
		case forceString:
			handleString(arg, true)
		default:
			lstat, lstatErr := os.Lstat(arg)
			if lstatErr != nil {
				// File doesn't exist — treat as string
				handleString(arg, false)
				return
			}
			mode := lstat.Mode()
			if mode&os.ModeSymlink != 0 {
				stat, statErr := os.Stat(arg)
				if statErr != nil {
					errorExit(fmt.Sprintf("Cannot copy '%s' - it is a broken symbolic link\nHint: Use -s flag to copy the literal string '%s' instead", arg, arg))
				} else if stat.IsDir() {
					errorExit(fmt.Sprintf("Cannot copy '%s' - it is a symbolic link to a directory, not a regular file\nHint: Use -s flag to copy the literal string '%s' instead", arg, arg))
				} else {
					handleFile(arg)
				}
			} else if mode.IsDir() {
				errorExit(fmt.Sprintf("Cannot copy '%s' - it is a directory, not a regular file\nHint: Use -s flag to copy the literal string '%s' instead", arg, arg))
			} else if mode.IsRegular() {
				handleFile(arg)
			} else {
				errorExit(fmt.Sprintf("Cannot copy '%s' - unknown file type, not a regular file\nHint: Use -s flag to copy the literal string '%s' instead", arg, arg))
			}
		}
	default:
		fmt.Fprintf(os.Stderr, "%sError: Too many arguments. Quote your input into a single argument string.%s\n", colors.Red, colors.NC)
		showUsage()
		os.Exit(1)
	}
}
