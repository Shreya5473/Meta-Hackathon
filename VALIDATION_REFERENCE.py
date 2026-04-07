#!/usr/bin/env python
"""
Sample Pre-Submission Validation Script
For Reference and Testing Pre-Submission Requirements

This script demonstrates how the OpenEnv platform will validate submissions.
Run this locally before submitting to ensure your submission will pass validation.
"""

# ============================================================================
# SAMPLE INFERENCE SCRIPT
# ============================================================================
"""
This is a SAMPLE of what a proper inference.py should look like.
Your inference.py should follow this structure.
"""

SAMPLE_INFERENCE_PY = '''
import asyncio
import os
import textwrap
from typing import List, Optional

from openai import OpenAI
from my_env_v4 import MyEnvV4Action, MyEnvV4Env

# Configuration from environment variables (MUST be set in Space settings)
IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.environ.get("HF_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

MAX_STEPS = 8
TEMPERATURE = 0.7
MAX_TOKENS = 150

def log_start(task: str, env: str, model: str) -> None:
    """REQUIRED: Log the start with exact format."""
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    """REQUIRED: Log each step with exact format."""
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """REQUIRED: Log the end with exact format."""
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)

async def main() -> None:
    """REQUIRED: Async main function."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = await MyEnvV4Env.from_docker_image(IMAGE_NAME)
    
    log_start(task="your_task", env="your_env", model=MODEL_NAME)
    
    try:
        result = await env.reset()
        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break
            # Your action generation logic here
            result = await env.step(MyEnvV4Action(...))
            log_step(step=step, action="...", reward=result.reward or 0.0, done=result.done, error=None)
    finally:
        await env.close()
        log_end(success=True, steps=MAX_STEPS, score=1.0, rewards=[0.1] * MAX_STEPS)

if __name__ == "__main__":
    asyncio.run(main())
'''

# ============================================================================
# PRE-VALIDATION SCRIPT REFERENCE
# ============================================================================
"""
The OpenEnv platform will check:

1. HF Space deploys
   - Automated ping to your Space URL
   - Must return 200 status
   - Must respond to /reset endpoint

2. OpenEnv spec compliance
   - openenv.yaml file with proper structure
   - Must define tasks, observation_space, action_space, reward_space
   - Must define /reset, /step, /state endpoints
   - Must support typed Pydantic models

3. Dockerfile builds
   - Automated docker build on repo push
   - Must expose port 7860
   - Must run uvicorn

4. Baseline reproduces
   - inference.py must complete without error
   - Must output structured logs with [START], [STEP], [END] format
   - Must produce scores in [0.0, 1.0] range

5. 3+ tasks with graders
   - At least 3 distinct tasks must be defined
   - Each task must be independently gradeable
   - Scores must be in [0.0, 1.0] range

6. Mandatory additional instructions
   Before submitting, ensure these environment variables are defined in your Space settings:
   - API_BASE_URL: The API endpoint for your LLM (e.g., https://api.openai.com/v1)
   - MODEL_NAME: The model identifier (e.g., gpt-4o-mini)
   - HF_TOKEN: Your HuggingFace API token
   
   Your inference.py MUST:
   - Use OpenAI Client for LLM calls
   - Be placed at root directory (/inference.py)
   - Output structured logs in EXACT format:
     * [START] task=... env=... model=...
     * [STEP] step=... action=... reward=... done=... error=...
     * [END] success=... steps=... score=... rewards=...

7. Infra restrictions
   - Runtime: < 20 minutes total
   - vCPU: 2
   - Memory: 8GB

8. Validator
   - Run pre_validation.py locally to catch issues before submitting
"""

# ============================================================================
# VALIDATION CHECKLIST
# ============================================================================

CHECKLIST = {
    "Files": [
        ("inference.py in root", "File exists and is executable"),
        ("openenv.yaml in root", "Valid YAML with proper structure"),
        ("requirements.txt", "Contains openai>=1.0.0 and openenv-core>=0.1.0"),
        ("Dockerfile", "Multi-stage, exposes port 7860, runs uvicorn"),
    ],
    
    "inference.py": [
        ("Imports asyncio", "Required for async execution"),
        ("Imports OpenAI", "Required for LLM integration"),
        ("Imports MyEnvV4Env", "Required for environment interaction"),
        ("async def main()", "Main function must be async"),
        ("env.reset()", "Must reset environment"),
        ("env.step()", "Must step environment"),
        ("log_start() function", "Log with [START] tag"),
        ("log_step() function", "Log with [STEP] tag"),
        ("log_end() function", "Log with [END] tag"),
        ("flush=True on prints", "Ensure logs are flushed immediately"),
    ],
    
    "openenv.yaml": [
        ("name: geo-trade", "Environment identifier"),
        ("version: 1.0.0", "Semantic versioning"),
        ("3+ tasks defined", "task_easy, task_medium, task_hard minimum"),
        ("observation_space", "Defined with type and description"),
        ("action_space", "Defined with type and description"),
        ("reward_space: [0.0, 1.0]", "Continuous range specification"),
        ("endpoints: reset, step, state", "Required OpenEnv endpoints"),
        ("environment_variables", "API_BASE_URL, MODEL_NAME, HF_TOKEN documented"),
    ],
    
    "Environment Setup": [
        ("API_BASE_URL", "Set in Space secrets (e.g., https://api.openai.com/v1)"),
        ("MODEL_NAME", "Set in Space secrets (e.g., gpt-4o-mini)"),
        ("HF_TOKEN", "Set in Space secrets (your HuggingFace token)"),
        ("Port 7860", "Space will access your app on this port"),
    ],
    
    "Logging Format": [
        ("[START]", "Must output: [START] task=X env=Y model=Z"),
        ("[STEP]", "Must output: [STEP] step=N action=A reward=R done=D error=E"),
        ("[END]", "Must output: [END] success=S steps=N score=C rewards=R1,R2,..."),
    ],
}

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  OpenEnv Hackathon - Pre-Submission Validation Reference")
    print("="*70 + "\n")
    
    for category, items in CHECKLIST.items():
        print(f"\n📋 {category}:")
        for item, description in items:
            print(f"   ☐ {item:40} → {description}")
    
    print("\n" + "="*70)
    print("  To validate locally, run: python pre_validation.py")
    print("  Status: All checks must PASS before submitting")
    print("="*70 + "\n")
