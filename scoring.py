"""
- Reads a Moodle grades export and the topic map.
- Returns, identity (name/id/email), overall score, per-question marks, and per-topic results (correct/total, %, tier, resource) per student. 

"""
import csv, re, sys
TOPIC_FILE = "Q Topics List and Resources.csv"
def load_topic_map(path=TOPIC_FILE):
    """slot matches to topic, and topic matches to resource text (single 'resource' column)."""
    topics, resources = {}, {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            slot = int(row["slot"])
            topics[slot] = row["topic"]
            if row.get("resource"):
                resources[row["topic"]] = row["resource"]
    return topics, resources
QUESTION_TOPICS, RESOURCES = load_topic_map()

def tier_for(percent):
    if percent >= 80: return "Strong"
    if percent >= 50: return "Developing"
    return "Needs Focus"

def _find_col(header, *needles):
    """Return index of the first column whose name contains any needle."""
    for i, col in enumerate(header):
        low = col.lower()
        if any(n in low for n in needles):
            return i
    return None

def score_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    last_i  = _find_col(header, "last name", "surname")
    first_i = _find_col(header, "first name")
    id_i    = _find_col(header, "id number", "id")
    email_i = _find_col(header, "email")
    slot_cols = {}
    for i, col in enumerate(header):
        m = re.search(r"Q\.?\s*(\d+)", col)
        if m:
            slot_cols[i] = int(m.group(1))
    students = []
    for row in rows[1:]:
        if not row or (last_i is not None and not row[last_i].strip()):
            continue
        name = " ".join(x for x in [
            row[first_i] if first_i is not None else "",
            row[last_i] if last_i is not None else "",
        ] if x).strip() or "Student"
        questions, by_topic = {}, {}
        for col_idx, slot in slot_cols.items():
            raw = row[col_idx].strip()
            try:
                correct = 1 if round(float(raw)) >= 1 else 0
            except ValueError:
                correct = 0
            questions[slot] = correct
            topic = QUESTION_TOPICS.get(slot)
            if topic:
                by_topic.setdefault(topic, []).append(correct)
        topics = []
        for topic, marks in by_topic.items():
            n, c = len(marks), sum(marks)
            pct = round(100 * c / n)
            topics.append({"topic": topic, "correct": c, "n": n,
                           "percent": pct, "tier": tier_for(pct),
                           "resource": RESOURCES.get(topic)})
        topics.sort(key=lambda t: t["percent"])
        students.append({
            "name": name,
            "student_id": row[id_i].strip() if id_i is not None else "",
            "email": row[email_i].strip() if email_i is not None else "",
            "overall_correct": sum(questions.values()),
            "overall_total": len(questions),
            "questions": questions,
            "topics": topics,
        })
    return students

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "results.csv"
    for s in score_csv(path):
        print(f"\n=== {s['name']}  {s['overall_correct']}/{s['overall_total']} ===")
        for t in s["topics"]:
            print(f"  {t['topic']:<26} {t['correct']}/{t['n']} ({t['percent']}%)  {t['tier']}")
