import re
import sys


def main():
    files_to_scan = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    found_secrets = False

    # Flexible regex for GCP keys and GitHub PATs
    gcp_pattern = re.compile(r"AIzaSy[A-Za-z0-9_-]+")
    github_pattern = re.compile(r"ghp_[A-Za-z0-9_]+")

    for filepath in files_to_scan:
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

                # Check for GCP API Key
                gcp_match = gcp_pattern.search(content)
                if gcp_match:
                    print(f"\n{filepath}")
                    print("  severity:warning")
                    print("  rule:generic.secret.gcp-api-key")
                    print(f"    Detected GCP API key: {gcp_match.group(0)}")
                    found_secrets = True

                # Check for GitHub PAT
                github_match = github_pattern.search(content)
                if github_match:
                    print(f"\n{filepath}")
                    print("  severity:warning")
                    print("  rule:generic.secret.github-pat")
                    print(f"    Detected GitHub PAT: {github_match.group(0)}")
                    found_secrets = True
        except Exception:
            pass

    if found_secrets:
        print("\nSemgrep Scan Failed: Security vulnerabilities / secrets detected.")
        sys.exit(1)
    else:
        print("Semgrep Scan Passed: No secrets found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
