import re

def clean_sentence(text: str) -> str:
    text = re.sub(r"^[\d\-\*\.\)\s]+", "", text)
    return text.strip().rstrip(".")


def extract_goal_and_tasks(text: str):
    """
    Rule-based extraction of ONE goal and MULTIPLE tasks.
    No AI, no API, deterministic.
    """

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    goal = None
    tasks = []

    # ---------- GOAL EXTRACTION ----------
    for i, line in enumerate(lines):
        low = line.lower().strip()

        # Case: "GOAL:" alone
        if low in ("goal:", "goal"):
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    goal = clean_sentence(lines[j])
                    break
            break

        # Case: "GOAL: actual text"
        if low.startswith("goal:"):
            goal = clean_sentence(line.split(":", 1)[1])
            break

        # Natural language fallback
        if low.startswith((
            "i want to",
            "my goal is",
            "i aim to",
            "i would like to",
            "objective:"
        )):
            goal = clean_sentence(line)
            break

    # Absolute fallback
    if not goal and lines:
        goal = clean_sentence(lines[0])

    # ---------- TASK EXTRACTION ----------
    for line in lines:
        # Numbered list
        if re.match(r"^\d+[\).\s]", line):
            tasks.append(clean_sentence(line))

        # Bullet list
        elif line.startswith(("-", "*", "•")):
            tasks.append(clean_sentence(line))

        # Verb-based heuristic
        elif line.lower().startswith((
            "learn ",
            "study ",
            "build ",
            "practice ",
            "implement ",
            "revise ",
            "read ",
            "understand ",
            "debug ",
            "verify ",
            "write "
        )):
            tasks.append(clean_sentence(line))

    # Remove duplicates, keep order
    tasks = list(dict.fromkeys(tasks))

    # Safety cap
    if len(tasks) > 10:
        tasks = tasks[:10]

    return goal, tasks