"""
- builds a full report per student.

"""
import os, re, sys
from scoring import score_csv
MODEL = "llama3.2"        
MAX_TOPICS_PER_SESSION = 3

_CACHE = {}

try:
    import ollama
    _HAVE_OLLAMA = True
except ImportError:
    _HAVE_OLLAMA = False

_Cache = {}

def split_resources(text):
    """Break one resource cell into separate items at '1)', '2)', '3)' markers."""
    if not text:
        return []
    parts = re.split(r"\s*\d+\)\s*", text)
    return [p.strip().rstrip(",") for p in parts if p.strip()]

def llama(system, user, cap=250):
    if not _HAVE_OLLAMA:
        return "(Llama writes this paragraph when run on your VM.)"
    try:
        r = ollama.chat(model=MODEL,
            options={"temperature": 0.8, "num_predict": cap},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        return re.sub(r"http\S+", "", r["message"]["content"]).strip()
    except Exception as e:
        return f"(Llama is not reachable: {e})"

COACH = ("You are the Quantitative Coach. Use warm, direct, plain, student-centered and accessible "
         "language that is not overwhelming. Don't use phrases like 'you failed' "
         "or 'you did poorly'. Don't mention links or resources. Keep it fast and concise."
         "Acknowledge the student's efforts.")

def feedback_paragraph(s):
    """ One cached Llama call. Name-free prompts are reusable across similar students. """
    strong = [t["topic"] for t in s["topics"] if t["tier"] == "Strong"]
    focus  = [t["topic"] for t in s["topics"] if t["tier"] != "Strong"]
    pct = round(100 * s["overall_correct"] / s["overall_total"]) if s["overall_total"] else 0
    user = (f"A student scored {pct} % overall. "
            f"Strong topics: {', '.join(strong) or 'none yet'}. "
            f"Topics to grow: {', '.join(focus) or 'none'}. "
            "Write a warm 3-4 sentence paragraph in which you acknowledge the student's efforts, name their strengths"
            "Point to the areas to focus on next and name the path forward."
            "Do ot gree by name or mention links and resources.")
    if user in _CACHE:
        return _CACHE[user]
    out = llama(COACH, user, cap = 250)
    _CACHE[user] = out
    return out

def build_markdown(s):
    md = []
    pct = round(100 * s["overall_correct"] / s["overall_total"]) if s["overall_total"] else 0
    md.append("Quantitative Coach Report\n")
    md.append(f"Name: {s['name']}  ")
    if s["student_id"]: md.append(f"Student ID: {s['student_id']}  ")
    if s["email"]:      md.append(f"Email: {s['email']}  ")
    md.append(f"Overall Score: {s['overall_correct']}/{s['overall_total']} ({pct}%)\n")
    md.append("Question Scores (1 = correct, 0 = incorrect)\n")
    md.append("  ".join(f"Q{slot}={mark}" for slot, mark in sorted(s["questions"].items())))
    md.append("")
    md.append("Score Summary\n")
    md.append("| Topic | Score | Tier |")
    md.append("|---|---|---|")
    for t in sorted(s["topics"], key=lambda x: -x["percent"]):
        md.append(f"| {t['topic']} | {t['correct']}/{t['n']} ({t['percent']}%) "
                  f"| {t['tier']} |")
    md.append("")
    md.append("Feedback\n")
    md.append(f"Hi {s['name']}! " + feedback_paragraph(s) + "\n")
    strong = [t for t in s["topics"] if t["tier"] == "Strong"]
    if strong:
        md.append("Strengths")
        for t in strong:
            md.append(f"- {t['topic']}: strong work at {t['correct']}/{t['n']} ({t['percent']}%).")
        md.append("")
    develop = [t for t in s["topics"] if t["tier"] != "Strong"]
    if develop:
        md.append("Areas to Develop")
        for t in develop:
            md.append(f"-{t['topic']} ({t['percent']}%)")
        md.append("")
    plan_topics = sorted(develop, key=lambda t: (t["tier"] != "Needs Focus", t["percent"]))
    if plan_topics:
        md.append("Tailored Study Plan\n")
        sessions = [plan_topics[i:i + MAX_TOPICS_PER_SESSION]
                    for i in range(0, len(plan_topics), MAX_TOPICS_PER_SESSION)]
        for i, session in enumerate(sessions, 1):
            names = ", ".join(t["topic"] for t in session)
            md.append(f"Session {i}: {names}\n")
            for t in session:
                md.append(f"{t['topic']} - {t['tier']} ({t['percent']}%)")
                items = split_resources(t["resource"])
                if items:
                    md.append("")
                    for item in items:
                        md.append(f"- {item}")
                else:
                    md.append("Resources: (none set for this topic yet)")
                md.append("")

    if plan_topics:
        md.append(f"Start with Session 1 to get started becaue that's where your biggest gains are. You've got this, {s['name']}!")
    return "\n".join(md)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "results.csv"
    os.makedirs("reports", exist_ok=True)
    for s in score_csv(path):
        print(f"Writing report for {s['name']}...", flush=True)
        safe = re.sub(r"[^\w]+", "_", s["name"]).strip("_") or "student"
        with open(f"reports/{safe}.txt", "w", encoding="utf-8") as f:
            f.write(build_markdown(s))
    print("Done. Reports are in the ./reports/ folder.")

