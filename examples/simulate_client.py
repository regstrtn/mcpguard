import subprocess
import json
import time

def simulate_mcp_session():
    print("🚀 [Simulating MCP Client Session]")
    print("---")
    
    # 1. Start the mcpguard proxy, which wraps a loopback process ('cat')
    process = subprocess.Popen(
        ["python3", "-m", "mcpguard.cli", "run", "--config", "policies/default.yaml", "--", "cat"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 2. Simulate an initialize handshake (MCP setup phase)
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestRunner", "version": "1.0"}
        }
    }
    
    # 3. Simulate a Malicious Tool Call (Absolute Traversal on a filesystem)
    traversal_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "call_tool",
        "params": {
            "name": "read_file",
            "arguments": {
                "path": "../../../../../../../etc/passwd"
            }
        }
    }

    print("📤 Sending 'initialize' handshake...")
    process.stdin.write(json.dumps(init_msg) + "\n")
    process.stdin.flush()
    time.sleep(0.5)

    print("📤 Sending malicious 'call_tool' request (Targeting: '../../etc/passwd')...")
    process.stdin.write(json.dumps(traversal_call) + "\n")
    process.stdin.flush()
    
    print("\n📩 [Intercepted Message Output]:")
    print("---")
    while True:
        output = process.stdout.readline()
        if output:
            parsed = json.loads(output.strip())
            # Print pretty response
            print(json.dumps(parsed, indent=2))
            if parsed.get("id") == 2:  # If we got response to our call
                 if "error" in parsed:
                     print("\n✅ Result: mcpguard SUCCESSFULLY blocked the relative traversal request!")
                 break
        else:
            break

    process.terminate()

if __name__ == "__main__":
    simulate_mcp_session()
