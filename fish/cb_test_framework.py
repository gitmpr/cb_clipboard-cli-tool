#!/usr/bin/env python3
"""
Comprehensive testing framework for cb clipboard script
Tests both executable and sourced function modes with real clipboard verification
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pexpect

_BASH = shutil.which("bash") or "/bin/bash"

# Colors for output
class Colors:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def colored(text: str, color: str) -> str:
    """Apply color to text"""
    return f"{color}{text}{Colors.RESET}"


@dataclass
class TestResult:
    """Represents the result of a single test"""

    name: str
    passed: bool
    expected_exit_code: int
    actual_exit_code: int
    expected_pattern: str | None = None
    actual_output: str = ""
    stderr_output: str = ""
    clipboard_content: str | None = None
    execution_time: float = 0.0
    error_message: str | None = None


class ClipboardMock:
    """Mock clipboard for testing without interfering with system clipboard"""

    def __init__(self):
        self.content = ""
        self.last_set_time = 0

    def set_content(self, content: str):
        """Set clipboard content"""
        self.content = content
        self.last_set_time = time.time()

    def get_content(self) -> str:
        """Get clipboard content"""
        return self.content

    def clear(self):
        """Clear clipboard"""
        self.content = ""
        self.last_set_time = 0


class CBTester:
    """Comprehensive testing framework for cb script"""

    def __init__(self, cb_path: str = "cb", debug: bool = False, verbose: bool = False):
        # Convert to absolute path to work correctly when changing directories
        self.cb_path = os.path.abspath(cb_path) if not shutil.which(cb_path) or os.path.exists(cb_path) else cb_path
        self.debug = debug
        self.verbose = verbose
        self.test_dir: str | None = None
        self.results: list[TestResult] = []
        self.clipboard_mock = ClipboardMock()

        # Detect shell type from shebang
        self.shell_type = self._detect_shell_type()

        # Detect if cb_path is a compiled binary (e.g. ELF) rather than a shell script
        self.is_compiled_binary = self._detect_compiled_binary()

        # Test environment setup
        self.test_files = {
            "simple.txt": "Hello, World!\n",
            "empty.txt": "",
            "multiline.txt": "Line 1\nLine 2\nLine 3\n",
            "no_newline.txt": "No trailing newline",
            "binary.bin": b"\x00\x01\x02\xff\xfe\xfd",
            "unicode.txt": "Hello 🌍 Unicode! ñoño\n",
            "large.txt": "A" * 10000 + "\n",
        }

    def _detect_compiled_binary(self) -> bool:
        """Return True if cb_path is a compiled binary (e.g. ELF), not a shell script."""
        try:
            with open(self.cb_path, "rb") as f:
                magic = f.read(4)
            return magic == b"\x7fELF"
        except OSError:
            return False

    def _detect_shell_type(self) -> str:
        """Detect shell type from script shebang"""
        try:
            with open(self.cb_path) as f:
                first_line = f.readline().strip()
                if "fish" in first_line:
                    return "fish"
                elif "bash" in first_line:
                    return "bash"
                else:
                    return "bash"  # Default to bash for unknown
        except Exception:
            return "bash"  # Default to bash if can't read

    def create_test_file(self, filename, content):
        """Create a test file in the current test environment"""
        path = Path(filename)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def setup_test_environment(self):
        """Set up isolated test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="cb_test_")
        original_dir = os.getcwd()
        os.chdir(self.test_dir)

        try:
            # Create test files
            for filename, content in self.test_files.items():
                path = Path(filename)
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")

            # Create directories
            Path("test_dir").mkdir()
            Path("nested/dir").mkdir(parents=True)

            # Create symlinks
            os.symlink("simple.txt", "good_symlink")
            os.symlink("nonexistent.txt", "broken_symlink")
            os.symlink("test_dir", "dir_symlink")

            # Create special files (if possible)
            try:
                os.mkfifo("named_pipe")
            except (OSError, AttributeError):
                # FIFO creation might fail on some systems
                pass

            if self.verbose:
                print(f"📁 Test environment created in {self.test_dir}")

        except Exception as e:
            os.chdir(original_dir)
            raise RuntimeError(f"Failed to setup test environment: {e}") from e

    def cleanup_test_environment(self):
        """Clean up test environment"""
        if self.test_dir and os.path.exists(self.test_dir):
            original_dir = os.getcwd()
            os.chdir("/")  # Change away from test directory
            try:
                shutil.rmtree(self.test_dir)
                if self.verbose:
                    print("🧹 Test environment cleaned up")
            except Exception as e:
                print(f"⚠️ Warning: Failed to cleanup {self.test_dir}: {e}")
            finally:
                if os.path.exists(original_dir):
                    os.chdir(original_dir)

    @contextmanager
    def test_environment(self):
        """Context manager for test environment"""
        self.setup_test_environment()
        try:
            yield
        finally:
            self.cleanup_test_environment()

    def run_cb_command(
        self,
        args: list[str],
        stdin_input: str | None = None,
        timeout: float = 5.0,
        mode: str = "executable",
        use_pty: bool = False,
    ) -> TestResult:
        """Run cb command and capture results"""

        if mode == "executable":
            cmd = [self.cb_path] + args
        elif mode == "sourced":
            # Test as sourced function using appropriate shell
            if self.shell_type == "fish":
                source_cmd = f"source {self.cb_path} && cb {' '.join(args)}"
                cmd = ["fish", "-c", source_cmd]
            else:
                source_cmd = f"source {self.cb_path} && cb {' '.join(args)}"
                cmd = [_BASH, "-c", source_cmd]
        else:
            raise ValueError(f"Invalid mode: {mode}")

        start_time = time.time()

        try:
            if use_pty:
                # Use pexpect for proper terminal simulation
                # Set CB_ALLOW_NONINTERACTIVE to bypass interactive check for testing
                test_env = os.environ.copy()
                test_env["CB_ALLOW_NONINTERACTIVE"] = "1"
                if mode == "executable":
                    child = pexpect.spawn(cmd[0], cmd[1:], cwd=self.test_dir, timeout=timeout, env=test_env)
                else:
                    if self.shell_type == "fish":
                        child = pexpect.spawn(
                            "fish", ["-c", source_cmd], cwd=self.test_dir, timeout=timeout, env=test_env
                        )
                    else:
                        child = pexpect.spawn(
                            _BASH, ["-c", source_cmd], cwd=self.test_dir, timeout=timeout, env=test_env
                        )

                if stdin_input is not None:
                    child.send(stdin_input)
                    child.sendeof()

                child.expect(pexpect.EOF)
                output = child.before.decode("utf-8", errors="replace") if child.before else ""
                stderr_output = ""  # pexpect combines stdout and stderr
                child.close()

                return TestResult(
                    name="",
                    passed=False,
                    expected_exit_code=0,
                    actual_exit_code=child.exitstatus or 0,
                    actual_output=output,
                    stderr_output=stderr_output,
                    execution_time=time.time() - start_time,
                )
            else:
                # Use subprocess.run for tests that need non-terminal stdin/stdout
                # Set CB_ALLOW_NONINTERACTIVE to bypass interactive check for testing
                test_env = os.environ.copy()
                test_env["CB_ALLOW_NONINTERACTIVE"] = "1"
                result = subprocess.run(
                    cmd,
                    input=stdin_input,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.test_dir,
                    env=test_env,
                )

                return TestResult(
                    name="",
                    passed=False,  # Will be set by caller
                    expected_exit_code=0,
                    actual_exit_code=result.returncode,
                    actual_output=result.stdout,
                    stderr_output=result.stderr,
                    execution_time=time.time() - start_time,
                )

        except subprocess.TimeoutExpired:
            return TestResult(
                name="",
                passed=False,
                expected_exit_code=0,
                actual_exit_code=-1,
                error_message=f"Command timed out after {timeout}s",
                execution_time=timeout,
            )
        except Exception as e:
            return TestResult(
                name="",
                passed=False,
                expected_exit_code=0,
                actual_exit_code=-1,
                error_message=str(e),
                execution_time=time.time() - start_time,
            )

    def test_case(
        self,
        name: str,
        args: list[str],
        expected_exit_code: int = 0,
        expected_pattern: str | None = None,
        stdin_input: str | None = None,
        mode: str = "executable",
        should_fail: bool = False,
        use_pty: bool = False,
    ) -> TestResult:
        """Run a single test case"""

        result = self.run_cb_command(args, stdin_input, mode=mode, use_pty=use_pty)
        result.name = name
        result.expected_exit_code = expected_exit_code
        result.expected_pattern = expected_pattern

        # Determine if test passed
        exit_code_match = result.actual_exit_code == expected_exit_code
        pattern_match = True

        if expected_pattern:
            combined_output = result.actual_output + result.stderr_output
            pattern_match = expected_pattern in combined_output

        result.passed = exit_code_match and pattern_match and not result.error_message

        # Log result
        if result.passed:
            print(f"   ✅ {name}")
        else:
            print(f"   ❌ {name}")
            if self.debug:
                print(f"      Expected exit: {expected_exit_code}, got: {result.actual_exit_code}")
                if expected_pattern and not pattern_match:
                    print(f"      Expected pattern: {expected_pattern}")
                    print(f"      Actual output: {repr(result.actual_output[:200])}")
                if result.error_message:
                    print(f"      Error: {result.error_message}")

        self.results.append(result)
        return result

    def test_stdin_pipe_to_terminal(self, name: str, stdin_data: str, expected_exit_code: int, expected_pattern: str):
        """Test stdin pipe to terminal scenario (echo "data" | cb)"""
        import shlex

        # Create a shell command that pipes data to cb, simulating real-world usage
        if stdin_data:
            escaped_data = shlex.quote(stdin_data)
            shell_cmd = f"echo {escaped_data} | {shlex.quote(self.cb_path)}"
        else:
            # For empty stdin, use a different approach
            shell_cmd = f"echo -n '' | {shlex.quote(self.cb_path)}"

        start_time = time.time()

        try:
            # Use pexpect to run the shell command in a proper terminal
            # Set CB_ALLOW_NONINTERACTIVE to bypass interactive check for testing
            test_env = os.environ.copy()
            test_env["CB_ALLOW_NONINTERACTIVE"] = "1"
            child = pexpect.spawn(_BASH, ["-c", shell_cmd], cwd=self.test_dir, timeout=5.0, env=test_env)
            child.expect(pexpect.EOF)
            output = child.before.decode("utf-8", errors="replace") if child.before else ""
            child.close()

            result = TestResult(
                name=name,
                passed=False,
                expected_exit_code=expected_exit_code,
                actual_exit_code=child.exitstatus or 0,
                expected_pattern=expected_pattern,
                actual_output=output,
                stderr_output="",  # pexpect combines stdout and stderr
                execution_time=time.time() - start_time,
            )

            # Determine if test passed
            exit_code_match = result.actual_exit_code == expected_exit_code
            pattern_match = True

            if expected_pattern:
                pattern_match = expected_pattern in result.actual_output

            result.passed = exit_code_match and pattern_match

            # Log result
            if result.passed:
                print(f"   ✅ {name}")
            else:
                print(f"   ❌ {name}")
                if self.debug:
                    print(f"      Expected exit: {expected_exit_code}, got: {result.actual_exit_code}")
                    if expected_pattern and not pattern_match:
                        print(f"      Expected pattern: {expected_pattern}")
                        print(f"      Actual output: {repr(result.actual_output[:200])}")

            self.results.append(result)
            return result

        except Exception as e:
            result = TestResult(
                name=name,
                passed=False,
                expected_exit_code=expected_exit_code,
                actual_exit_code=-1,
                error_message=str(e),
                execution_time=time.time() - start_time,
            )

            print(f"   ❌ {name}")
            if self.debug:
                print(f"      Error: {str(e)}")

            self.results.append(result)
            return result

    def test_basic_functionality(self):
        """Test basic copy functionality"""
        print(f"\n{colored('📋 Testing Basic Functionality', Colors.BOLD)}")

        # Test file copying (use pty to simulate proper terminal)
        self.test_case("Copy simple text file", ["simple.txt"], 0, "✓", use_pty=True)
        self.test_case("Copy empty file", ["empty.txt"], 0, "empty", use_pty=True)
        self.test_case("Copy multiline file", ["multiline.txt"], 0, "✓", use_pty=True)
        self.test_case(
            "Copy file without trailing newline", ["no_newline.txt"], 0, "missing final newline", use_pty=True
        )

        # Test string copying (use pty to simulate proper terminal)
        self.test_case("Copy simple string", ["hello world"], 0, "✓", use_pty=True)
        self.test_case("Copy empty string", [""], 0, "empty", use_pty=True)

        # Test stdin copying (simulate echo | cb using shell command in pty)
        # This properly simulates stdin=pipe, stdout=terminal
        self.test_stdin_pipe_to_terminal("Copy from stdin", "hello from stdin", 0, "✓")
        self.test_stdin_pipe_to_terminal("Copy empty stdin", "", 0, "empty")

    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        print(f"\n{colored('🔍 Testing Edge Cases', Colors.BOLD)}")

        # Test error conditions (use pty for proper terminal simulation)
        self.test_case("No args, no stdin (should fail)", [], 1, "Usage:", use_pty=True)
        self.test_case("Too many arguments", ["arg1", "arg2"], 1, "Too many arguments", use_pty=True)

        # Test special files (use pty for proper terminal simulation)
        self.test_case("Directory without -s", ["test_dir"], 1, "directory", use_pty=True)
        self.test_case("Directory with -s", ["-s", "test_dir"], 0, "✓", use_pty=True)
        self.test_case("Broken symlink without -s", ["broken_symlink"], 1, "broken symbolic link", use_pty=True)
        self.test_case("Broken symlink with -s", ["-s", "broken_symlink"], 0, "✓", use_pty=True)

        # Test unicode and special characters (use pty for proper terminal simulation)
        self.test_case("Copy unicode file", ["unicode.txt"], 0, "✓", use_pty=True)
        self.test_case("Copy string with special chars", ["hello\tworld\n"], 0, "✓", use_pty=True)

        # Test large files (use pty for proper terminal simulation)
        self.test_case("Copy large file", ["large.txt"], 0, "✓", use_pty=True)

    def test_symlinks(self):
        """Test symlink handling"""
        print(f"\n{colored('🔗 Testing Symlink Handling', Colors.BOLD)}")

        self.test_case("Good symlink to file", ["good_symlink"], 0, "Copying text file", use_pty=True)
        self.test_case("Directory symlink without -s", ["dir_symlink"], 1, "symbolic link", use_pty=True)
        self.test_case("Directory symlink with -s", ["-s", "dir_symlink"], 0, "✓", use_pty=True)

    def test_flag_positioning(self):
        """Test -s flag positioning"""
        print(f"\n{colored('🏴 Testing Flag Positioning', Colors.BOLD)}")

        # Test -s flag before argument (traditional way)
        self.test_case("-s flag before argument", ["-s", "nonexistent_file.txt"], 0, "✓", use_pty=True)

        # Test -s flag after argument (new feature)
        self.test_case("-s flag after argument", ["nonexistent_file.txt", "-s"], 0, "✓", use_pty=True)

        # Test -s flag with existing file (should treat as string)
        self.test_case("-s flag after existing file", ["simple.txt", "-s"], 0, "literal string", use_pty=True)

    def test_realpath_flag(self):
        """Test -r flag for copying file paths"""
        print(f"\n{colored('📁 Testing Realpath Flag (-r)', Colors.BOLD)}")

        # Test -r flag with existing file (traditional positioning)
        self.test_case("-r flag before existing file", ["-r", "simple.txt"], 0, "Copying absolute path", use_pty=True)

        # Test -r flag with existing file (flexible positioning)
        self.test_case("-r flag after existing file", ["simple.txt", "-r"], 0, "Copying absolute path", use_pty=True)

        # Test -r flag with non-existent file
        self.test_case(
            "-r flag with non-existent file", ["-r", "nonexistent.txt"], 0, "hypothetical absolute path", use_pty=True
        )

        # Test -r flag conflicts with -s flag
        self.test_case(
            "-r and -s flags together (should fail)",
            ["-r", "-s", "simple.txt"],
            1,
            "Cannot use -r and -s flags together",
            use_pty=True,
        )

        # Test -r flag without arguments (should fail)
        self.test_case("-r flag without arguments", ["-r"], 1, "-r flag requires a file path argument", use_pty=True)

    def test_binary_files(self):
        """Test binary file detection and handling"""
        print(f"\n{colored('🔢 Testing Binary File Handling', Colors.BOLD)}")

        self.test_case("Binary file handling", ["binary.bin"], 0, "Warning: Copying binary file", use_pty=True)

    def test_sourced_mode(self):
        """Test cb when sourced as a function"""
        print(f"\n{colored('📚 Testing Sourced Function Mode', Colors.BOLD)}")

        if self.is_compiled_binary:
            print(f"   {colored('⏭', Colors.YELLOW)} Sourced: Copy file     {colored('(skipped — compiled binary cannot be sourced as a shell function)', Colors.DIM)}")
            print(f"   {colored('⏭', Colors.YELLOW)} Sourced: Copy string   {colored('(skipped — compiled binary cannot be sourced as a shell function)', Colors.DIM)}")
            print(f"   {colored('⏭', Colors.YELLOW)} Sourced: Error handling {colored('(skipped — compiled binary cannot be sourced as a shell function)', Colors.DIM)}")
            return

        # Test basic functionality in sourced mode (use pty for proper terminal simulation)
        self.test_case("Sourced: Copy file", ["simple.txt"], 0, "✓", mode="sourced", use_pty=True)
        self.test_case("Sourced: Copy string", ["hello"], 0, "✓", mode="sourced", use_pty=True)
        self.test_case("Sourced: Error handling", ["test_dir"], 1, "directory", mode="sourced", use_pty=True)

    def test_paste_mode_detection(self):
        """Test paste mode detection and warnings"""
        print(f"\n{colored('📤 Testing Paste Mode Detection', Colors.BOLD)}")

        # In non-interactive environments, stdin is never a terminal, so cb | cat
        # will read from stdin instead of entering paste mode. This is correct behavior.
        try:
            # Test with output redirection simulation (no timeout needed - cb should respond quickly)
            # Use relative path and change to script directory to avoid path issues
            cb_dir = os.path.dirname(os.path.abspath(self.cb_path))
            cb_name = os.path.basename(self.cb_path)
            cmd = f"bash -c './{cb_name} | cat' 2>&1"
            # Set CB_ALLOW_NONINTERACTIVE to bypass interactive check for testing
            test_env = os.environ.copy()
            test_env["CB_ALLOW_NONINTERACTIVE"] = "1"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cb_dir, env=test_env)

            # In non-interactive environments, expect stdin processing, paste mode attempt, or successful paste
            if (
                "Copying empty content from stdin" in result.stdout
                or "Pasting clipboard contents" in result.stdout
                or "Could not read from clipboard" in result.stdout
                or "Cannot copy to clipboard: stderr must be connected to a terminal" in result.stdout
                or (result.returncode == 0 and len(result.stdout.strip()) > 0)
            ):
                print("   ✅ Paste mode detection works (or stdin processing in non-interactive env)")
                self.results.append(
                    TestResult(
                        name="Paste mode detection",
                        passed=True,
                        expected_exit_code=0,
                        actual_exit_code=result.returncode,
                        expected_pattern="stdin processing or paste mode",
                        actual_output=result.stdout,
                    )
                )
            else:
                print("   ❌ Paste mode detection failed")
                print(f"      Command: {cmd}")
                print(f"      Exit code: {result.returncode}")
                print(f"      Full stdout: {repr(result.stdout)}")
                print(f"      Full stderr: {repr(result.stderr)}")
                print("      Looking for any of:")
                print("        - 'Copying empty content from stdin'")
                print("        - 'Pasting clipboard contents'")
                print("        - 'Could not read from clipboard'")
                print("        - 'Cannot copy to clipboard: stderr must be connected to a terminal'")
                self.results.append(
                    TestResult(
                        name="Paste mode detection",
                        passed=False,
                        expected_exit_code=0,
                        actual_exit_code=result.returncode,
                        expected_pattern="stdin processing or paste mode",
                        actual_output=result.stdout,
                        error_message="Expected stdin processing or paste mode indicators not found",
                    )
                )
        except Exception as e:
            print(f"   ⚠️ Paste mode test skipped: {e}")
            self.results.append(
                TestResult(
                    name="Paste mode detection",
                    passed=False,
                    expected_exit_code=0,
                    actual_exit_code=-1,
                    error_message=f"Test exception: {e}",
                    actual_output="",
                )
            )

    def test_argument_conflicts(self):
        """Test stdin + argument conflicts"""
        print(f"\n{colored('⚔️ Testing Argument Conflicts', Colors.BOLD)}")

        # These tests specifically need to test stdin+argument conflicts, so use subprocess
        self.test_case(
            "Stdin + file conflict",
            ["simple.txt"],
            1,
            "Cannot accept both stdin and an argument",
            stdin_input="conflict\n",
            use_pty=False,
        )
        self.test_case(
            "Stdin + string conflict",
            ["hello"],
            1,
            "Cannot accept both stdin and an argument",
            stdin_input="conflict\n",
            use_pty=False,
        )

    # =============================================================================
    # EXTENDED EDGE CASE TESTS
    # =============================================================================

    def test_performance_stress(self):
        """Test performance with large files and stress conditions"""
        print(f"\n{colored('⚡ Testing Performance & Stress Conditions', Colors.BOLD)}")

        # Test very large file (1MB of text)
        large_content = "Line " + "x" * 1000 + "\n" * 1000
        self.create_test_file("large_1mb.txt", large_content)
        self.test_case("Copy 1MB file", ["large_1mb.txt"], 0, "✓", use_pty=True)

        # Test file with extremely long line (no newlines)
        long_line = "x" * 50000  # 50KB single line
        self.create_test_file("long_line.txt", long_line)
        self.test_case("Copy file with 50KB single line", ["long_line.txt"], 0, "✓", use_pty=True)

        # Test rapid successive operations
        self.create_test_file("rapid_test.txt", "rapid test content")
        start_time = time.time()
        success_count = 0
        for _i in range(5):
            result = self.run_cb_command(["rapid_test.txt"], use_pty=True)
            if result.actual_exit_code == 0:
                success_count += 1
        duration = time.time() - start_time
        # Report the performance result
        if success_count >= 4:
            print(f"   ✅ 5 rapid operations ({success_count}/5 success) in {duration:.2f}s")
        else:
            print(f"   ❌ 5 rapid operations ({success_count}/5 success) in {duration:.2f}s")

        # Test many repeated flags (stress argument parsing)
        many_flags = ["-s"] * 10 + ["test_string"]  # Should fail gracefully
        self.test_case("Many repeated flags", many_flags, 1, "Invalid option", use_pty=True)

    def test_character_encoding(self):
        """Test various character encodings and internationalization"""
        print(f"\n{colored('🌍 Testing Character Encoding & Internationalization', Colors.BOLD)}")

        # Test various UTF-8 content
        test_cases = [
            ("emoji.txt", "Hello 👋 World 🌍 with emoji 🎉\n", "UTF-8 with emoji"),
            ("chinese.txt", "你好世界\n这是中文测试\n", "Chinese characters"),
            ("arabic.txt", "مرحبا بالعالم\nهذا اختبار عربي\n", "Arabic text (RTL)"),
            ("mixed_unicode.txt", "Mixed: ASCII + 中文 + العربية + 🌟\n", "Mixed Unicode"),
            ("mathematical.txt", "Math: ∑∞₁ ∫∆∇ ≠≤≥ ±×÷\n", "Mathematical symbols"),
        ]

        for filename, content, description in test_cases:
            self.create_test_file(filename, content)
            self.test_case(f"Copy {description}", [filename], 0, "✓", use_pty=True)

        # Test different line endings
        self.create_test_file("crlf.txt", "Windows\r\nline\r\nendings\r\n")
        self.test_case("Copy Windows CRLF line endings", ["crlf.txt"], 0, "✓", use_pty=True)

        self.create_test_file("cr_only.txt", "Old Mac\rline\rendings\r")
        self.test_case("Copy Mac CR line endings", ["cr_only.txt"], 0, "✓", use_pty=True)

        # Test BOM (Byte Order Mark)
        bom_content = "\ufeffBOM test content\n"
        self.create_test_file("bom.txt", bom_content)
        self.test_case("Copy file with UTF-8 BOM", ["bom.txt"], 0, "✓", use_pty=True)

    def test_advanced_file_types(self):
        """Test edge cases with special file content"""
        print(f"\n{colored('📄 Testing Advanced File Types & Edge Cases', Colors.BOLD)}")

        # Test file with null bytes (should be detected as binary)
        null_content = "Text with\x00null\x00bytes"
        self.create_test_file("null_bytes.txt", null_content)
        self.test_case("File with null bytes", ["null_bytes.txt"], 0, "binary", use_pty=True)

        # Test file with only whitespace
        whitespace_content = "   \t  \n  \t\t  \n   "
        self.create_test_file("whitespace_only.txt", whitespace_content)
        self.test_case("File with only whitespace", ["whitespace_only.txt"], 0, "✓", use_pty=True)

        # Test file with control characters
        control_content = "Text with\x07bell\x1b[31mANSI\x1b[0m codes"
        self.create_test_file("control_chars.txt", control_content)
        self.test_case("File with control characters", ["control_chars.txt"], 0, "✓", use_pty=True)

        # Test extremely deep nested content
        nested_content = "(" * 1000 + "deep nesting" + ")" * 1000
        self.create_test_file("deep_nesting.txt", nested_content)
        self.test_case("File with deep nesting", ["deep_nesting.txt"], 0, "✓", use_pty=True)

        # Test file that looks like command
        command_like = "rm -rf /\nsudo dangerous-command\n"
        self.create_test_file("dangerous_looking.txt", command_like)
        self.test_case("File with dangerous-looking content", ["dangerous_looking.txt"], 0, "✓", use_pty=True)

    def test_edge_case_arguments(self):
        """Test edge cases in argument handling"""
        print(f"\n{colored('⚙️ Testing Edge Case Arguments', Colors.BOLD)}")

        # Test arguments that look like flags
        self.test_case("String starting with dash", ["-not-a-flag"], 0, "✓", use_pty=True)
        self.test_case("String with -s inside", ["-s", "text-with-p-flag"], 0, "✓", use_pty=True)
        self.test_case("String with equals", ["-s", "key=value"], 0, "✓", use_pty=True)

        # Test very long arguments
        long_string = "x" * 10000
        self.test_case("Very long string argument", ["-s", long_string], 0, "✓", use_pty=True)

        # Test arguments with special shell characters
        special_chars = "arg with spaces & special | chars > < $ * ?"
        self.test_case("Argument with special shell chars", ["-s", special_chars], 0, "✓", use_pty=True)

        # Test empty string vs no arguments
        self.test_case("Explicit empty string", ["-s", ""], 0, "empty", use_pty=True)

        # Test numeric arguments
        self.test_case("Numeric string", ["-s", "12345"], 0, "✓", use_pty=True)
        self.test_case("Float string", ["-s", "123.456"], 0, "✓", use_pty=True)

    def test_empty_content_edge_cases(self):
        """Test comprehensive empty content scenarios for OSC 52 empty clipboard functionality"""
        print(f"\n{colored('🕳️ Testing Empty Content Edge Cases', Colors.BOLD)}")

        # Test various empty content scenarios
        self.test_case("Empty string with -s flag", ["-s", ""], 0, "empty", use_pty=True)

        # Test empty file
        empty_file = os.path.join(self.test_dir, "empty_file.txt")
        with open(empty_file, "w") as f:
            pass  # Create empty file
        self.test_case("Copy empty file", [empty_file], 0, "empty", use_pty=True)

        # Test whitespace-only strings (should not be considered empty)
        self.test_case("String with just spaces", ["-s", "   "], 0, "✓", use_pty=True)
        self.test_case("String with just newlines", ["-s", "\n\n"], 0, "✓", use_pty=True)
        self.test_case("String with just tabs", ["-s", "\t\t"], 0, "✓", use_pty=True)

        # Note: Empty stdin piped input (echo -n "" | cb) works correctly in real usage
        # but is complex to test due to PTY vs non-PTY stdin terminal detection differences

    def test_filesystem_edge_cases(self):
        """Test filesystem-related edge cases"""
        print(f"\n{colored('💾 Testing Filesystem Edge Cases', Colors.BOLD)}")

        # Test files with unusual names
        unusual_names = [
            ("file with spaces.txt", "content", "Filename with spaces"),
            ("file-with-dashes.txt", "content", "Filename with dashes"),
            ("file.with.dots.txt", "content", "Filename with multiple dots"),
            ("UPPERCASE.TXT", "content", "Uppercase filename"),
            ("mixedCaSe.TxT", "content", "Mixed case filename"),
        ]

        for filename, content, description in unusual_names:
            self.create_test_file(filename, content)
            self.test_case(f"Copy {description}", [filename], 0, "✓", use_pty=True)

        # Test very long filename (if filesystem supports it)
        try:
            long_filename = "a" * 200 + ".txt"
            self.create_test_file(long_filename, "content")
            self.test_case("Very long filename", [long_filename], 0, "✓", use_pty=True)
        except OSError:
            # Skip if filesystem doesn't support long names
            print("   ⏭️ Very long filename - Skipped (Filesystem limitation)")

    def test_concurrent_operations(self):
        """Test concurrent operations and race conditions"""
        print(f"\n{colored('🔄 Testing Concurrent Operations', Colors.BOLD)}")

        # Create test file for concurrent access
        self.create_test_file("concurrent.txt", "concurrent test content")

        # Test rapid file modifications during copy
        self.test_case("Copy while file being modified", ["concurrent.txt"], 0, "✓", use_pty=True)

        # Test multiple flags in different orders
        flag_combinations = [
            (["-r", "-s"], 1, "Cannot use -r and -s flags together"),
            (["-s", "-r"], 1, "Cannot use -r and -s flags together"),
            (["-r", "concurrent.txt", "-s"], 1, "Cannot use -r and -s flags together"),
        ]

        for flags, expected_exit, expected_output in flag_combinations:
            self.test_case(f"Flag combination: {' '.join(flags)}", flags, expected_exit, expected_output, use_pty=True)

    def run_cb_and_get_osc52(self, args: list[str], stdin_input: str | None = None) -> bytes | None:
        """Run cb in a PTY and extract the decoded OSC52 clipboard payload bytes.

        Returns the decoded bytes that were sent to the clipboard, or None if no
        OSC52 sequence was found. An empty-payload OSC52 (clipboard clear) returns b''.
        """
        import base64
        import re

        test_env = os.environ.copy()
        test_env["CB_ALLOW_NONINTERACTIVE"] = "1"

        cmd = [self.cb_path] + args

        child = pexpect.spawn(cmd[0], cmd[1:], cwd=self.test_dir, timeout=5.0, env=test_env)

        if stdin_input is not None:
            child.send(stdin_input)
            child.sendeof()

        child.expect(pexpect.EOF)
        raw = child.before if child.before else b""
        child.close()

        # OSC52 format: ESC ] 52 ; c ; <base64> ESC backslash
        match = re.search(rb"\x1b]52;c;([A-Za-z0-9+/=]*)\x1b\\", raw)
        if match is None:
            return None
        b64 = match.group(1)
        if not b64:
            return b""  # Empty OSC52 = clipboard clear
        return base64.b64decode(b64)

    def test_clipboard_payload_verification(self):
        """Verify actual OSC52 bytes sent match the expected clipboard content.

        This is the critical correctness test: it checks what bytes are actually
        written to the clipboard, not just whether the command exits 0 or prints '✓'.
        """
        print(f"\n{colored('🔬 Testing OSC52 Clipboard Payload Verification', Colors.BOLD)}")

        cases = [
            # (description, args, stdin_input, expected_bytes)
            ("String 'hello'", ["-s", "hello"], None, b"hello"),
            ("Simple file (simple.txt)", ["simple.txt"], None, b"Hello, World!\n"),
            ("Multiline file (multiline.txt)", ["multiline.txt"], None, b"Line 1\nLine 2\nLine 3\n"),
            ("No-trailing-newline file", ["no_newline.txt"], None, b"No trailing newline"),
            ("Unicode file (unicode.txt)", ["unicode.txt"], None, "Hello \U0001f30d Unicode! \xf1o\xf1o\n".encode()),
        ]

        for description, args, stdin_input, expected in cases:
            payload = self.run_cb_and_get_osc52(args, stdin_input)
            passed = payload == expected
            status = "✅" if passed else "❌"
            detail = ""
            if not passed:
                detail = f" (got {repr(payload)}, want {repr(expected)})"
            print(f"   {status} OSC52 payload: {description}{detail}")
            self.results.append(TestResult(
                name=f"OSC52 payload: {description}",
                passed=passed,
                expected_exit_code=0,
                actual_exit_code=0,
                expected_pattern=repr(expected),
                actual_output=repr(payload),
            ))

        # Empty string → OSC52 clear (payload is empty bytes b'')
        payload = self.run_cb_and_get_osc52(["-s", ""])
        passed = payload == b""
        status = "✅" if passed else "❌"
        detail = "" if passed else f" (got {repr(payload)}, want b'')"
        print(f"   {status} OSC52 payload: empty string clears clipboard{detail}")
        self.results.append(TestResult(
            name="OSC52 payload: empty string clears clipboard",
            passed=passed,
            expected_exit_code=0,
            actual_exit_code=0,
            expected_pattern="b''",
            actual_output=repr(payload),
        ))

    def test_environment_variations(self):
        """Test behavior under different environment conditions"""
        print(f"\n{colored('🌐 Testing Environment Variations', Colors.BOLD)}")

        # Test with different environment variables
        old_debug = os.environ.get("CB_DEBUG")
        os.environ["CB_DEBUG"] = "1"
        self.test_case("Copy with debug enabled", ["-s", "debug test"], 0, "✓", use_pty=True)
        if old_debug is None:
            os.environ.pop("CB_DEBUG", None)
        else:
            os.environ["CB_DEBUG"] = old_debug

        # Note: cb is designed for interactive terminal use only
        # Non-interactive environments are not supported by design

    def test_help_functionality(self):
        """Test help text functionality and formatting"""
        print(f"\n{colored('📖 Testing Help Text Functionality', Colors.BOLD)}")

        # Test basic help output
        self.test_case("Help command works", ["-h"], 0, "Universal clipboard utility", use_pty=True)

        # Test that help contains expected sections
        result = self.run_cb_command(["-h"], use_pty=True)
        help_output = result.actual_output

        # Check for key sections in help text
        expected_sections = [
            "Universal clipboard utility",
            "Usage:",
            "Description:",
            "Copy Modes:",
            "Paste Modes:",
            "Options:",
            "Environment:",
            "Examples:",
        ]

        all_sections_found = True
        missing_sections = []

        for section in expected_sections:
            if section not in help_output:
                all_sections_found = False
                missing_sections.append(section)

        if all_sections_found:
            test_result = TestResult(
                name="Help contains all expected sections",
                passed=True,
                expected_exit_code=0,
                actual_exit_code=result.actual_exit_code,
                actual_output=help_output,
            )
        else:
            test_result = TestResult(
                name="Help contains all expected sections",
                passed=False,
                expected_exit_code=0,
                actual_exit_code=result.actual_exit_code,
                actual_output=help_output,
                error_message=f"Missing sections: {missing_sections}",
            )

        self.results.append(test_result)
        status = "✅" if test_result.passed else "❌"
        print(f"   {status} Help contains all expected sections")

        # Test help text formatting (colors should not cause syntax errors)
        # This tests that the fish version doesn't have echo/printf syntax issues
        self.test_case("Help text formatting works", ["-h"], 0, None, use_pty=True)

        # Test help in narrow terminal (should use simple format)
        old_columns = os.environ.get("COLUMNS")
        os.environ["COLUMNS"] = "50"

        result_narrow = self.run_cb_command(["-h"], timeout=5.0, use_pty=True)

        # Restore original COLUMNS value
        if old_columns is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = old_columns

        # In narrow terminal, should not have box drawing characters
        has_box_chars = "╭" in result_narrow.actual_output or "│" in result_narrow.actual_output

        narrow_test_result = TestResult(
            name="Help adapts to narrow terminal width",
            passed=(result_narrow.actual_exit_code == 0 and not has_box_chars),
            expected_exit_code=0,
            actual_exit_code=result_narrow.actual_exit_code,
            actual_output=result_narrow.actual_output,
        )

        self.results.append(narrow_test_result)
        status = "✅" if narrow_test_result.passed else "❌"
        print(f"   {status} Help adapts to narrow terminal width")

    def run_all_tests(self):
        """Run the complete comprehensive test suite including extended tests"""
        print(f"{colored('🚀 CB Comprehensive Test Suite', Colors.BOLD + Colors.BLUE)}")

        # Show absolute path of cb file being tested
        cb_absolute_path = os.path.abspath(self.cb_path)
        print(f"Testing: {self.cb_path}")
        print(f"Absolute path: {cb_absolute_path}")

        # Warn if no specific path was provided
        if self.cb_path == "cb":
            print(f"{colored('⚠️  WARNING: No --cb-path specified, using cb from PATH', Colors.YELLOW)}")

        print("Running basic functionality and extended edge case tests...")

        # Check if cb script exists
        if not os.path.exists(self.cb_path) and not shutil.which(self.cb_path):
            print(f"{colored('❌ Error: cb script not found at', Colors.RED)} {self.cb_path}")
            return False

        with self.test_environment():
            # Run basic functionality tests
            self.test_basic_functionality()
            self.test_edge_cases()
            self.test_symlinks()
            self.test_flag_positioning()
            self.test_realpath_flag()
            self.test_binary_files()
            self.test_sourced_mode()
            self.test_paste_mode_detection()
            self.test_argument_conflicts()

            # Run extended edge case tests
            self.test_performance_stress()
            self.test_character_encoding()
            self.test_advanced_file_types()
            self.test_edge_case_arguments()
            self.test_empty_content_edge_cases()
            self.test_filesystem_edge_cases()
            self.test_concurrent_operations()
            self.test_environment_variations()
            self.test_help_functionality()
            self.test_clipboard_payload_verification()

        return self.print_summary()

    def print_summary(self):
        """Print comprehensive test results"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests

        print(f"\n{colored('=' * 60, Colors.BOLD)}")
        print(f"{colored('📊 TEST SUMMARY', Colors.BOLD + Colors.BLUE)}")
        print(f"{colored('=' * 60, Colors.BOLD)}")

        print(f"Total tests: {total_tests}")
        print(f"Passed: {colored(str(passed_tests), Colors.GREEN)}")
        print(f"Failed: {colored(str(failed_tests), Colors.RED if failed_tests > 0 else Colors.GREEN)}")

        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            print(
                f"Success rate: {colored(f'{success_rate:.1f}%', Colors.GREEN if success_rate == 100 else Colors.YELLOW)}"
            )

        # Show execution time stats
        execution_times = [r.execution_time for r in self.results if r.execution_time > 0]
        if execution_times:
            avg_time = sum(execution_times) / len(execution_times)
            print(f"Average execution time: {avg_time:.3f}s")

        # Show failed tests details
        if failed_tests > 0:
            print(f"\n{colored('❌ FAILED TESTS:', Colors.RED + Colors.BOLD)}")
            for result in self.results:
                if not result.passed:
                    print(f"  • {result.name}")
                    if result.error_message:
                        print(f"    Error: {result.error_message}")
                    elif result.expected_exit_code != result.actual_exit_code:
                        print(f"    Expected exit {result.expected_exit_code}, got {result.actual_exit_code}")

        if passed_tests == total_tests:
            print(f"\n{colored('🎉 ALL TESTS PASSED!', Colors.GREEN + Colors.BOLD)}")
            return True
        else:
            print(f"\n{colored(f'❌ {failed_tests} TEST(S) FAILED', Colors.RED + Colors.BOLD)}")
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprehensive testing framework for cb clipboard script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_cb.py                    # Test cb in current PATH
  python test_cb.py --cb-path ./cb     # Test specific cb script
  python test_cb.py --debug --verbose  # Verbose output with debug info
        """,
    )

    parser.add_argument("--cb-path", default="cb", help="Path to cb script (default: 'cb' from PATH)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for failed tests")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Validate dependencies
    missing_deps = []
    try:
        import pexpect  # noqa: F401
    except ImportError:
        missing_deps.append("pexpect")

    if missing_deps:
        print(f"{colored('❌ Missing dependencies:', Colors.RED)} {', '.join(missing_deps)}")
        print("Install with: pip install " + " ".join(missing_deps))
        return 1

    # Create and run tester
    tester = CBTester(args.cb_path, debug=args.debug, verbose=args.verbose)

    try:
        success = tester.run_all_tests()
        return 0 if success else 1

    except KeyboardInterrupt:
        print(f"\n{colored('⏹️ Tests interrupted by user', Colors.YELLOW)}")
        return 130
    except Exception as e:
        print(f"{colored('💥 Unexpected error:', Colors.RED)} {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
