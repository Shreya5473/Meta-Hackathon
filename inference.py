import os
import textwrap
import json
from urllib import request as urllib_request
from urllib import error as urllib_error
from typing import Any, List, Optional

from openenv.environment import GeoTradeEnv
from openenv.models import GeoTradeAction

# Environment configuration
IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.getenv("API_KEY")

API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_NAME = os.getenv("GEOTRADE_TASK", "all")
BENCHMARK = os.getenv("GEOTRADE_BENCHMARK", "geotrade")

# Local fallback defaults (used only outside validator when API env vars are absent)
if not API_BASE_URL:
    API_BASE_URL = "https://router.huggingface.co/v1"
if not API_KEY:
    API_KEY = os.getenv("HF_TOKEN")

MAX_STEPS = 8
TEMPERATURE = 0.7
MAX_TOKENS = 150
SUCCESS_SCORE_THRESHOLD = 0.1
SCORE_EPSILON = 1e-4

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
        f"[STEP] step={step} action={action} reward={reward:.4f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Log the end of the episode."""
    rewards_str = ",".join(f"{r:.4f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.4f} rewards={rewards_str}",
        flush=True,
    )


def strict_unit(value: float, eps: float = SCORE_EPSILON) -> float:
    """Clamp metric strictly inside (0,1) for validator compatibility."""
    return max(eps, min(1.0 - eps, value))


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
    client: Any | None, step: int, last_echoed: str, last_reward: float, history: List[str]
) -> str:
    """Get a message from the LLM."""
    user_prompt = build_user_prompt(step, last_echoed, last_reward, history)

    if client is None:
        return request_model_message_via_http(step=step, user_prompt=user_prompt)

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
        return request_model_message_via_http(step=step, user_prompt=user_prompt)


def request_model_message_via_http(step: int, user_prompt: str) -> str:
    """Call OpenAI-compatible chat completion endpoint via API_BASE_URL/API_KEY."""
    if not API_BASE_URL or not API_KEY:
        print("[DEBUG] Missing API_BASE_URL/API_KEY; using local fallback message", flush=True)
        return f"step_{step}_fallback_message_with_context"

    endpoint = f"{API_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }

    req = urllib_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return text if text else "hello"
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(f"[DEBUG] HTTP proxy request failed: {exc.code} {body}", flush=True)
    except Exception as exc:
        print(f"[DEBUG] HTTP proxy request error: {exc}", flush=True)

    return "hello"


def create_openai_client() -> Any | None:
    """Create OpenAI-compatible client, or return None if unavailable."""
    try:
        from openai import OpenAI
    except Exception as exc:
        print(f"[DEBUG] OpenAI package unavailable: {exc}", flush=True)
        return None

    try:
        return OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    except Exception as exc:
        print(f"[DEBUG] OpenAI client init failed: {exc}", flush=True)
        return None


def run_episode(task_name: str, client: Any | None) -> None:
    """Run one episode for a specific task and print OpenEnv logs."""
    env = GeoTradeEnv(task_id=task_name)

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = SCORE_EPSILON
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        obs = env.reset()

        for step in range(1, MAX_STEPS + 1):
            if env._done:
                break

            message = get_model_message(client, step, str(obs), 0.0, history)
            action_payload = GeoTradeAction(
                task_id=task_name,
                decisions=[
                    {
                        "symbol": "XAUUSD",
                        "direction": "HOLD",
                        "weight": 0.0,
                        "confidence": 0.5,
                    }
                ],
                primary_signal=message,
                reasoning=message,
            )

            try:
                result = env.step(action_payload)
                reward = float(result.reward.total) if result.reward else SCORE_EPSILON
                done = result.done
                error = None
            except Exception as e:
                reward = SCORE_EPSILON
                done = True
                error = str(e)

            reward = strict_unit(reward)
            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=message, reward=reward, done=done, error=error)
            history.append(f"Step {step}: {message!r} -> reward {reward:+.4f}")

            if done:
                break

        raw_score = sum(rewards) / max(1, len(rewards))
        score = strict_unit(raw_score)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


def main() -> None:
    """Main inference entrypoint."""
    client = create_openai_client()

    base_tasks = ["task_easy", "task_medium", "task_hard"]
    if TASK_NAME in base_tasks:
        tasks_to_run = [TASK_NAME] + [t for t in base_tasks if t != TASK_NAME]
    else:
        tasks_to_run = base_tasks

    for task_name in tasks_to_run:
        run_episode(task_name=task_name, client=client)


if __name__ == "__main__":
    main()
