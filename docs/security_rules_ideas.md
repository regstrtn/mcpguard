# 🛡️ Non-Intrusive Security & Guardrail Ideas

To make `mcpguard` a highly useful product, the policy library should address **egregious safety failures** or **malicious intent**, while leaving 99% of a developer's workflow completely untouched. 

Below is a list of high-value safety rule buckets that maintain Developer Experience (DX).

---

## 1. ☁️ Cloud Metadata Server Isolation (Anti-SSRF)
*   **The Threat**: An AI Agent could be tricked into querying the local server's internal cloud metadata endpoints to steal IAM service account tokens or account IDs.
*   **Target Tools**: `http_request`, `curl`, `fetch`
*   **Rule Idea**: Deny HTTP requests targeting `169.254.169.254` (Standard AWS/GCP/Azure Metadata IP) or `metadata.google.internal`.
*   **Why it's Safe**: Developers almost *never* need their IDE agent to read or query local EC2/GCE metadata for local code generation tasks.

---

## 2. 🔑 Anti-Credential Exfiltration (Tar/Zip Locks)
*   **The Threat**: To steal locally saved keys, an agent is instructed to create a compressed `.tar` file of standard key holders (`~/.ssh/`, `~/.aws/`) and upload it to a workspace directory for the user to commit or send to arbitrary endpoints.
*   **Target Tools**: `run_command`, `shell_`, `execute_command`
*   **Rule Idea**: Reject commands containing compressions setups targeting key holding directory formats, e.g., `tar.*\\.ssh` or `zip.*\\.env`.
*   **Why it's Safe**: Legit workflows compress workspace codes, not SSH keys folders.

---

## 3. 🚦 Native Process Disruption (Anti-Freeze)
*   **The Threat**: An agent kills critical system processes (e.g., stopping docker, killing parent Node binaries, stopping network interfaces) which breaks local execution nodes.
*   **Target Tools**: `run_command`
*   **Rule Idea**: Block absolute high-risk system commands that disconnect hosts like `killall`, `kill -9`, `systemctl stop`, `ufw disable`, `iptables -F`.
*   **Why it's Safe**: Developers shouldn't task an editor agent with stopping local systemd daemons unless intentionally breaking things.

---

## 4. 🪪 Live Credential Sniffing (Authorization Headers)
*   **The Threat**: Adding an agent to an API wrapper results in it building request strings containing `Authorization: Bearer <secret_key>`. If that secret gets logged or written to files, it creates leaks.
*   **Target Tools**: `http_request`, `write_file`
*   **Rule Idea**: Create a scanner parser looking for `Authorization:\\s*Bearer\\s+[a-zA-Z0-9_.-]{16,}` and trigger `Action.APPROVE` to double-check with the user that they want to send or save a live token string.
*   **Why it's Safe**: Gives a confirmation overlay so tokens aren't committed to git by accident.

---

## 5. 💣 Sub-Process Cluttering (Anti-Forkbomb)
*   **The Threat**: Broken prompting loops occasionally spin infinite child processes calling something like `while true; do node app.js &; done`.
*   **Target Tools**: `run_command`
*   **Rule Idea**: Deny commands containing typical shell bomb wrappers `while true.*&; done` or multiple nested trigger backgrounding wrappers designed to exhaust system RAM.
*   **Why it's Safe**: Prevents local runtime exhaustions during prompt-loops.
