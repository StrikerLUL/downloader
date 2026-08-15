import os
import sys
import subprocess
import time
import shutil
import tempfile
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure we can import test_cases from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_cases

class TestContext:
    def __init__(self, port, download_script, project_root):
        self.port = port
        self.download_script = download_script
        self.project_root = project_root
        self.temp_dirs = []
        
    def create_temp_dir(self):
        d = tempfile.mkdtemp(prefix="downloader_test_")
        self.temp_dirs.append(d)
        return d
        
    def cleanup(self):
        for d in self.temp_dirs:
            # Add a small delay/retry to prevent Windows file locking issues during cleanup
            for _ in range(5):
                try:
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    break
                except Exception:
                    time.sleep(0.1)
        self.temp_dirs.clear()
        
    def run_cli(self, args, env_override=None, cwd=None, timeout=15):
        cmd = [sys.executable, self.download_script] + args
        env = os.environ.copy()
        if env_override:
            env.update(env_override)
        env["DOWNLOADER_MOCK_SERVER"] = f"http://127.0.0.1:{self.port}"
        env["PYTHONIOENCODING"] = "utf-8"
        
        return subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )

def main():
    print("=" * 60)
    print("🚀 STARTING E2E TEST RUNNER")
    print("=" * 60)
    
    # Paths setup
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    # Handle running from tests directory or agent directory
    if os.path.basename(tests_dir) == 'tests':
        project_root = os.path.dirname(tests_dir)
    else:
        # Fallback for agent dir - look for worktree project root
        project_root = r"C:\Users\cilli\.gemini\antigravity\brain\f4cb1ec0-db6d-4e7b-8c3f-8e712c58a680\.system_generated\worktrees\subagent-E2E-Test-Implementer-teamwork-preview-worker-a75cfcd5"
        if not os.path.exists(project_root):
            project_root = os.path.dirname(tests_dir)
            
    download_script = os.path.join(project_root, "download_video.py")
    mock_server_script = os.path.join(tests_dir, "mock_server.py")
    if not os.path.exists(mock_server_script):
        mock_server_script = os.path.join(project_root, "tests", "mock_server.py")
        
    print(f"[*] Project root: {project_root}")
    print(f"[*] Downloader CLI script: {download_script}")
    print(f"[*] Mock server script: {mock_server_script}")
    
    # 1. Start Mock Server
    print("[*] Starting mock HTTP server...")
    proc = subprocess.Popen(
        [sys.executable, mock_server_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    port = None
    start_time = time.time()
    # Wait for mock server to print its dynamic port
    while time.time() - start_time < 5:
        line = proc.stdout.readline()
        if line.startswith("PORT:"):
            port = int(line.strip().split(":")[1])
            break
        time.sleep(0.1)
        
    if not port:
        print("[!] Error: Mock server failed to start or did not print PORT.")
        # Try reading stderr
        try:
            outs, errs = proc.communicate(timeout=1)
            print(f"[!] Server Stderr: {errs}")
        except Exception:
            pass
        sys.exit(1)
        
    print(f"[+] Mock server successfully started on port: {port}")
    
    # 2. Setup Context
    ctx = TestContext(port, download_script, project_root)
    
    # 3. Load Test Cases
    cases = test_cases.register_all_cases()
    print(f"[+] Loaded {len(cases)} test cases.")
    
    passed_count = 0
    failed_count = 0
    results = []
    
    # Sort test cases by ID
    sorted_ids = sorted(cases.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in x.replace('.', '-').split('-')])
    
    # 4. Run Test Cases
    print("\n" + "=" * 60)
    print("🏃 RUNNING E2E TEST CASES")
    print("=" * 60)
    
    for tid in sorted_ids:
        case = cases[tid]
        print(f"[*] Running {case['id']}: {case['description']}... ", end="", flush=True)
        
        try:
            # Execute test
            passed, detail = case['fn'](ctx)
            # Cleanup temp files/directories created during this test
            ctx.cleanup()
        except Exception as e:
            passed = False
            detail = f"Test threw exception: {e}"
            ctx.cleanup()
            
        if passed:
            print("\033[92mPASSED\033[0m")
            passed_count += 1
            status = "PASSED"
        else:
            print("\033[91mFAILED\033[0m")
            failed_count += 1
            status = "FAILED"
            print(f"    └─ Detail: {detail}")
            
        results.append({
            "id": case['id'],
            "category": case['category'],
            "description": case['description'],
            "status": status,
            "detail": detail
        })
        
    # 5. Stop Mock Server
    print("\n[*] Stopping mock HTTP server...")
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[+] Mock server stopped.")
    
    # 6. Structured Execution Summary
    print("\n" + "=" * 60)
    print("📊 E2E TEST EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total Test Cases: {len(results)}")
    print(f"Passed:           {passed_count}")
    print(f"Failed:           {failed_count}")
    print(f"Success Rate:     {passed_count / len(results) * 100:.2f}%")
    print("=" * 60)
    
    # Output detailed JSON results to test_results.json
    results_path = os.path.join(project_root, "test_results.json")
    try:
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total": len(results),
                    "passed": passed_count,
                    "failed": failed_count,
                    "success_rate": f"{passed_count / len(results) * 100:.2f}%"
                },
                "results": results
            }, f, indent=4)
        print(f"[+] Detailed test results exported to: {results_path}")
    except Exception as e:
        print(f"[!] Failed to export test results: {e}")
        
    print("\nDone.")
    
if __name__ == '__main__':
    main()
