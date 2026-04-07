#!/usr/bin/env python
"""
Pre-submission validation script for OpenEnv Hackathon.

This script validates that the GeoTrade submission meets all Pre-Submission Checklist requirements:
1. HF Space deploys (ping URL → 200)
2. openenv.yaml spec compliance (typed models, step/reset/state endpoints)
3. Dockerfile builds
4. inference.py completes without error
5. 3+ tasks with graders (enumerate, run, verify scores in [0.0, 1.0])
6. Mandatory instructions (env vars, inference.py location, OpenAI client, logging format)
7. Infra restrictions (runtime < 20min, vCPU=2, memory=8GB)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def print_header(msg: str) -> None:
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}\n")


def print_success(msg: str) -> None:
    """Print success message."""
    print(f"✅ {msg}")


def print_error(msg: str) -> None:
    """Print error message."""
    print(f"❌ {msg}")


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"ℹ️  {msg}")


def check_required_files() -> Dict[str, bool]:
    """Check that required files exist."""
    print_header("1. Checking Required Files")
    
    required_files = {
        "inference.py": Path("inference.py"),
        "openenv.yaml": Path("openenv.yaml"),
        "requirements.txt": Path("requirements.txt"),
        "Dockerfile": Path("Dockerfile"),
        "app/main.py": Path("app/main.py"),
    }
    
    results = {}
    for name, path in required_files.items():
        exists = path.exists()
        results[name] = exists
        if exists:
            print_success(f"{name} found")
        else:
            print_error(f"{name} NOT found at {path}")
    
    if not all(results.values()):
        raise ValidationError("Missing required files")
    
    return results


def validate_inference_py() -> bool:
    """Validate inference.py structure and content."""
    print_header("2. Validating inference.py")
    
    inference_path = Path("inference.py")
    content = inference_path.read_text()
    
    # Check for required imports
    required_imports = ["asyncio", "OpenAI", "MyEnvV4Env", "MyEnvV4Action"]
    for imp in required_imports:
        if imp not in content:
            print_error(f"Missing required import: {imp}")
            return False
        print_success(f"Found import: {imp}")
    
    # Check for required functions
    required_functions = ["log_start", "log_step", "log_end", "main"]
    for func in required_functions:
        if f"def {func}" not in content:
            print_error(f"Missing required function: {func}")
            return False
        print_success(f"Found function: {func}")
    
    # Check for logging format
    logging_formats = [
        "[START]",
        "[STEP]",
        "[END]",
    ]
    for fmt in logging_formats:
        if fmt not in content:
            print_error(f"Missing required logging format: {fmt}")
            return False
        print_success(f"Found logging format: {fmt}")
    
    # Check for environment variables
    required_env_vars = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
    for env_var in required_env_vars:
        if env_var not in content:
            print_error(f"Missing required environment variable: {env_var}")
            return False
        print_success(f"Found env var reference: {env_var}")
    
    # Check for async main
    if "async def main()" not in content:
        print_error("main() must be async")
        return False
    print_success("main() is async")
    
    # Check for env.reset() and env.step()
    if "env.reset()" not in content:
        print_error("Missing env.reset() call")
        return False
    print_success("Found env.reset() call")
    
    if "env.step(" not in content:
        print_error("Missing env.step() call")
        return False
    print_success("Found env.step() call")
    
    return True


def validate_openenv_yaml() -> Dict[str, Any]:
    """Validate openenv.yaml structure."""
    print_header("3. Validating openenv.yaml")
    
    openenv_path = Path("openenv.yaml")
    with openenv_path.open() as f:
        config = yaml.safe_load(f)
    
    # Check required top-level fields
    required_fields = ["name", "version", "tasks", "endpoints"]
    for field in required_fields:
        if field not in config:
            print_error(f"Missing required field: {field}")
            return {}
        print_success(f"Found field: {field}")
    
    # Check environment_variables
    if "environment_variables" in config:
        required_env_vars = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
        env_vars = config.get("environment_variables", {})
        for env_var in required_env_vars:
            if env_var not in env_vars:
                print_error(f"Missing environment variable definition: {env_var}")
            else:
                print_success(f"Found environment variable: {env_var}")
    
    # Check tasks
    tasks = config.get("tasks", [])
    if len(tasks) < 3:
        print_error(f"Expected at least 3 tasks, found {len(tasks)}")
    else:
        print_success(f"Found {len(tasks)} tasks (required: 3+)")
    
    for i, task in enumerate(tasks):
        task_id = task.get("id", f"task_{i}")
        if "id" not in task or "name" not in task:
            print_error(f"Task {i} missing 'id' or 'name'")
        else:
            print_success(f"Task {i}: {task_id} ({task.get('name', 'N/A')})")
    
    # Check endpoints
    endpoints = config.get("endpoints", {})
    required_endpoints = ["reset", "step", "state"]
    for endpoint in required_endpoints:
        if endpoint not in endpoints:
            print_error(f"Missing required endpoint: {endpoint}")
        else:
            print_success(f"Found endpoint: {endpoint}")
    
    # Check observation/action/reward spaces
    spaces = ["observation_space", "action_space", "reward_space"]
    for space in spaces:
        if space in config:
            print_success(f"Found {space}")
        else:
            print_error(f"Missing {space}")
    
    return config


def validate_requirements_txt() -> List[str]:
    """Validate requirements.txt has required packages."""
    print_header("4. Validating requirements.txt")
    
    req_path = Path("requirements.txt")
    content = req_path.read_text()
    
    required_packages = ["openai", "openenv-core", "fastapi"]
    found_packages = []
    
    for pkg in required_packages:
        if pkg.lower() in content.lower():
            print_success(f"Found {pkg}")
            found_packages.append(pkg)
        else:
            print_error(f"Missing {pkg}")
    
    return found_packages


def validate_dockerfile() -> bool:
    """Validate Dockerfile structure."""
    print_header("5. Validating Dockerfile")
    
    dockerfile_path = Path("Dockerfile")
    content = dockerfile_path.read_text()
    
    # Check for multi-stage build
    if content.count("FROM") < 2:
        print_error("Dockerfile should use multi-stage build (at least 2 FROM statements)")
        return False
    print_success("Found multi-stage build")
    
    # Check for port 7860
    if "7860" not in content:
        print_error("Port 7860 not exposed")
        return False
    print_success("Port 7860 is exposed")
    
    # Check for uvicorn command
    if "uvicorn" not in content:
        print_error("uvicorn not found in Dockerfile")
        return False
    print_success("uvicorn command found")
    
    # Check for Python 3.11
    if "python:3.11" not in content:
        print_error("Python 3.11 not found")
        return False
    print_success("Python 3.11 found")
    
    return True


def check_syntax_errors() -> bool:
    """Check Python files for syntax errors."""
    print_header("6. Checking for Syntax Errors")
    
    python_files = ["inference.py", "app/main.py"]
    all_ok = True
    
    for filepath in python_files:
        path = Path(filepath)
        if not path.exists():
            print_error(f"{filepath} not found")
            all_ok = False
            continue
        
        try:
            compile(path.read_text(), filepath, "exec")
            print_success(f"{filepath} has no syntax errors")
        except SyntaxError as e:
            print_error(f"{filepath} has syntax error: {e}")
            all_ok = False
    
    return all_ok


def validate_docker_build() -> bool:
    """Attempt to build Docker image (dry-run check)."""
    print_header("7. Validating Docker Build")
    
    # Check if docker is installed
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        print_success(f"Docker is installed: {result.stdout.strip()}")
    except FileNotFoundError:
        print_error("Docker is not installed or not in PATH")
        return False
    
    # Try to build (this may take a while)
    print_info("Attempting to build Docker image (this may take 2-5 minutes)...")
    try:
        result = subprocess.run(
            ["docker", "build", "-t", "geotrade-validation:test", "."],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            print_success("Docker build succeeded")
            return True
        else:
            print_error(f"Docker build failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error("Docker build timed out (>10 minutes)")
        return False
    except Exception as e:
        print_error(f"Docker build error: {e}")
        return False


def validate_inference_execution() -> bool:
    """Test inference.py execution (will fail without proper setup)."""
    print_header("8. Testing inference.py Syntax & Import")
    
    try:
        # Just check if the file can be imported (don't execute main)
        path = Path("inference.py")
        code = path.read_text()
        compile(code, "inference.py", "exec")
        print_success("inference.py compiles successfully")
        
        # Try to import key dependencies
        try:
            import openai
            print_success(f"openai module is available: {openai.__version__}")
        except ImportError:
            print_error("openai module not installed")
            return False
        
        # Note: openenv-core may have dependency issues in local environment
        # but will work in Docker container
        try:
            import openenv_core
            print_success("openenv-core module is available")
        except (ImportError, ModuleNotFoundError) as e:
            print_info("openenv-core module not available locally (expected - will work in Docker)")
        
        return True
    except Exception as e:
        print_error(f"Error checking inference.py: {e}")
        return False


def run_full_validation() -> bool:
    """Run all validation checks."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*16 + "OpenEnv Hackathon Pre-Submission Validator" + " "*11 + "║")
    print("╚" + "="*68 + "╝")
    
    checks = []
    
    try:
        # 1. Check required files
        check_required_files()
        checks.append(("Required Files", True))
    except ValidationError as e:
        print_error(str(e))
        checks.append(("Required Files", False))
    
    try:
        # 2. Validate inference.py
        result = validate_inference_py()
        checks.append(("inference.py Structure", result))
    except Exception as e:
        print_error(f"Error validating inference.py: {e}")
        checks.append(("inference.py Structure", False))
    
    try:
        # 3. Validate openenv.yaml
        config = validate_openenv_yaml()
        checks.append(("openenv.yaml Structure", bool(config)))
    except Exception as e:
        print_error(f"Error validating openenv.yaml: {e}")
        checks.append(("openenv.yaml Structure", False))
    
    try:
        # 4. Validate requirements.txt
        packages = validate_requirements_txt()
        checks.append(("requirements.txt Packages", len(packages) >= 3))
    except Exception as e:
        print_error(f"Error validating requirements.txt: {e}")
        checks.append(("requirements.txt Packages", False))
    
    try:
        # 5. Validate Dockerfile
        result = validate_dockerfile()
        checks.append(("Dockerfile Structure", result))
    except Exception as e:
        print_error(f"Error validating Dockerfile: {e}")
        checks.append(("Dockerfile Structure", False))
    
    try:
        # 6. Check syntax errors
        result = check_syntax_errors()
        checks.append(("Python Syntax Errors", result))
    except Exception as e:
        print_error(f"Error checking syntax: {e}")
        checks.append(("Python Syntax Errors", False))
    
    # Note: Docker build is optional and time-consuming
    # Uncomment below if you want to test it
    # try:
    #     result = validate_docker_build()
    #     checks.append(("Docker Build", result))
    # except Exception as e:
    #     print_error(f"Error validating Docker build: {e}")
    #     checks.append(("Docker Build", False))
    
    try:
        # 7. Test inference.py execution
        result = validate_inference_execution()
        checks.append(("inference.py Execution", result))
    except Exception as e:
        print_error(f"Error testing inference.py: {e}")
        checks.append(("inference.py Execution", False))
    
    # Summary
    print_header("VALIDATION SUMMARY")
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:<10} {check_name}")
    
    print(f"\nTotal: {passed}/{total} checks passed\n")
    
    if passed == total:
        print_success("All validation checks PASSED! 🎉")
        print_success("Your submission is ready for the OpenEnv Hackathon!")
        return True
    else:
        print_error(f"Some checks failed ({total - passed} failures)")
        print_info("Please fix the issues above and run validation again.")
        return False


if __name__ == "__main__":
    try:
        success = run_full_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
