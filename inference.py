import asyncio
import os
import sys
import textwrap
from typing import List, Optional

from openai import OpenAI

from openenv.environment import GeoTradeEnv
from openenv.models import GeoTradeAction, AssetDecision

# Environment configuration
IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.environ.get("HF_TOKEN")

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_NAME = os.getenv("MY_ENV_V4_TASK", "echo")
BENCHMARK = os.getenv("MY_ENV_V4_BENCHMARK", "my_env_v4")

MAX_STEPS = 8
TEMPERATURE = 0.7
MAX_TOKENS = 150
SUCCESS_SCORE_THRESHOLD = 0.1

# Max possible reward: each token contributes 0.1, across all steps
_MAX_REWARD_PER_STEP = MAX_TOKENS * 0.1
MAX_TOTAL_REWARD = MAX_STEPS * _MAX_REWARD_PER_STEP

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are interacting with a simple echo environment.
    Each turn you must send a message. The environment will echo it back.
    Reward is proportional to message length: reward = len(message) * 0.1
    Your goal is to maximize total reward by sending meaningful, substantive messages.
    Reply with exactly one message string — no quotes, no prefixes, just the message text.
    """
).strip()

def log_start(task: str, env: str, model: str) -> None:
    """Log the start of the episode."""
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    """Log each step of the episode."""
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Log the end of the episode."""
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def build_user_prompt(step: int, last_echoed: str, last_reward: float, history: List[str]) -> str:
    """Build the user prompt for the LLM."""
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Step: {step}
        Last echoed message: {last_echoed!r}
        Last reward: {last_reward:.2f}
        Previous steps:
        {history_block}
        Send your next message.
        """
    ).strip()


def get_model_message(
    client: OpenAI, step: int, last_echoed: str, last_reward: float, history: List[str]
) -> str:
    """Get a message from the LLM."""
    user_prompt = build_user_prompt(step, last_echoed, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        return text if text else "hello"
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return "hello"


async def main() -> None:
    """Main inference loop."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Initialize environment (GeoTradeEnv is synchronous, not async)
    env = GeoTradeEnv(task_id="task_easy")

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = env.reset(seed=42)
        last_observation = result
        last_reward = 0.0

        for step in range(1, MAX_STEPS + 1):
            if env._done:
                break

            # Build user prompt from current observation
            user_prompt = build_user_prompt(step, str(last_observation), last_reward, history)

            message = get_model_message(client, step, str(last_observation), last_reward, history)

            # Create action with the message as reasoning
            action = GeoTradeAction(
                task_id="task_easy",
                decisions=[
                    AssetDecision(
                        symbol="UNKNOWN",
                        direction="HOLD",
                        weight=0.0,
                        confidence=0.5,
                    )
                ],
                primary_signal=message[:100] if len(message) > 100 else message,
                reasoning=message,
            )

            result = env.step(action)
            obs = result.observation

            reward = result.reward.total or 0.0
            done = result.done
            error = None

            rewards.append(reward)
            steps_taken = step
            last_observation = obs
            last_reward = reward

            log_step(step=step, action=message, reward=reward, done=done, error=error)

            history.append(f"Step {step}: {message[:50]}... → reward {reward:+.2f}")

            if done:
                break

        score = sum(rewards) / MAX_TOTAL_REWARD if MAX_TOTAL_REWARD > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        # No cleanup needed for GeoTradeEnv
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    # Only run if explicitly called as main script
    import sys
    try:
        try:
            # Try the standard asyncio.run() first
            asyncio.run(main())
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                # If there's already an event loop running, use it
                import asyncio.runners
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If truly running, create a task instead
                    loop.create_task(main())
                else:
                    loop.run_until_complete(main())
            else:
                raise
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        sys.exit(1)
