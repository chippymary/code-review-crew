import os
import sys


def main():
    # Read command from arguments or stdin
    command_str = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not command_str:
        command_str = sys.stdin.read().strip()

    if not command_str:
        print("APPROVED: Empty command.", file=sys.stdout)
        sys.exit(0)

    # 1. Block "rm -rf /"
    if "rm -rf /" in command_str:
        print("BLOCKED: Cannot run rm -rf on root directory.", file=sys.stderr)
        sys.exit(1)

    # 2. Block "git push --force"
    if "git push" in command_str and ("--force" in command_str or "-f" in command_str):
        print("BLOCKED: Force pushing is disabled.", file=sys.stderr)
        sys.exit(1)

    # 3. Block commands writing outside the project directory
    # Get project root (parent of .agents which is parent of scripts)
    project_root = os.path.abspath(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )

    # Check for output redirection or paths
    tokens = command_str.split()
    for token in tokens:
        # Check if absolute path outside project root is referenced for writing
        # (e.g., in copy, move, redirect commands)
        if (
            token.startswith("/") or (len(token) > 1 and token[1] == ":")
        ) and not token.startswith(project_root.replace("\\", "/")):
            # If command has a write or modify action, check
            if any(
                x in command_str for x in [">", ">>", "out", "cp", "mv", "rm", "mkdir"]
            ):
                print(
                    f"BLOCKED: Attempted operation outside project directory: {token}",
                    file=sys.stderr,
                )
                sys.exit(1)
        # Check for path traversal escaping project directory
        if ".." in token:
            print("BLOCKED: Path traversal (..) is not allowed.", file=sys.stderr)
            sys.exit(1)

    print("APPROVED: Command validation passed.", file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
