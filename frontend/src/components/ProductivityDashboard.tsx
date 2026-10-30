
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  Clock3,
  ClipboardList,
  Target,
  RefreshCw,
  Plus,
} from "lucide-react";

const API = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const STUDENT_ID = "demo-student";

type Task = {
  id: number;
  title: string;
  subject: string;
  planned_minutes: number;
  due_date: string;
  status: "pending" | "completed";
};

type Summary = {
  date: string;
  score: number | null;
  tasks: { completed: number; total: number };
  focused_minutes: number;
  interruptions: number;
  session_count: number;
  learning: {
    correct: number;
    questions: number;
    accuracy: number | null;
  };
  reflection: string;
  week: {
    focused_minutes: number;
    tasks_completed: number;
    tasks_total: number;
    quiz_accuracy: number | null;
    daily_focus: { date: string; minutes: number }[];
  };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="productivity-metric">
      <div className="productivity-metric-icon">{icon}</div>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

export default function ProductivityDashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [plannedMinutes, setPlannedMinutes] = useState(25);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [summaryData, taskData] = await Promise.all([
        request<Summary>(
          `/productivity/summary?student_id=${encodeURIComponent(STUDENT_ID)}`,
        ),
        request<{ items: Task[] }>(
          `/productivity/tasks?student_id=${encodeURIComponent(STUDENT_ID)}`,
        ),
      ]);

      setSummary(summaryData);
      setTasks(taskData.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load productivity data.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  async function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !subject.trim() || saving) return;

    setSaving(true);
    setError("");

    try {
      await request<Task>("/productivity/tasks", {
        method: "POST",
        body: JSON.stringify({
          student_id: STUDENT_ID,
          title: title.trim(),
          subject: subject.trim(),
          planned_minutes: plannedMinutes,
        }),
      });

      setTitle("");
      setSubject("");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add task.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleTask(task: Task) {
    setError("");

    try {
      await request<Task>(`/productivity/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          student_id: STUDENT_ID,
          completed: task.status !== "completed",
        }),
      });

      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update task.");
    }
  }

  if (loading && !summary) {
    return <main className="productivity-page"><p>Loading productivity data...</p></main>;
  }

  const focusTarget = 120;
  const focusPercent = Math.min(
    100,
    Math.round(((summary?.focused_minutes ?? 0) / focusTarget) * 100),
  );

  return (
    <main className="productivity-page">
      <header className="productivity-heading">
        <div>
          <p className="productivity-eyebrow">YOUR STUDY SPACE</p>
          <h2>Productivity dashboard</h2>
          <p>Track your study activity and daily progress.</p>
        </div>

        <button
          className="productivity-refresh"
          onClick={() => void loadDashboard()}
          disabled={loading}
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      {error && (
        <div className="productivity-error" role="alert">
          {error}
        </div>
      )}

      <section className="productivity-metrics">
        <Metric
          label="Daily score"
          value={summary?.score == null ? "—" : `${summary.score}/100`}
          detail="Based on recorded activity"
          icon={<Target size={21} />}
        />
        <Metric
          label="Focused study"
          value={`${summary?.focused_minutes ?? 0} min`}
          detail={`${focusTarget} min daily reference target`}
          icon={<Clock3 size={21} />}
        />
        <Metric
          label="Tasks completed"
          value={`${summary?.tasks.completed ?? 0}/${summary?.tasks.total ?? 0}`}
          detail="Tasks due today"
          icon={<CheckCircle2 size={21} />}
        />
        <Metric
          label="Quiz accuracy"
          value={
            summary?.learning.accuracy == null
              ? "—"
              : `${summary.learning.accuracy}%`
          }
          detail={`${summary?.learning.questions ?? 0} questions recorded today`}
          icon={<ClipboardList size={21} />}
        />
      </section>

      <section className="productivity-panel">
        <h3>Today's focus</h3>
        <div className="productivity-progress-track">
          <div
            className="productivity-progress-fill"
            style={{ width: `${focusPercent}%` }}
          />
        </div>
        <p>
          {summary?.focused_minutes ?? 0} of {focusTarget} minutes
          {" "}({focusPercent}% of the reference target)
        </p>
        <div className="productivity-secondary-stats">
          <span>Sessions: {summary?.session_count ?? 0}</span>
          <span>Interruptions: {summary?.interruptions ?? 0}</span>
        </div>
      </section>

      <section className="productivity-panel">
        <h3>Last seven days</h3>
        <div className="productivity-week">
          {(summary?.week.daily_focus ?? []).map((day) => (
            <div className="productivity-day" key={day.date}>
              <div className="productivity-bar-area">
                <div
                  className="productivity-bar"
                  style={{
                    height: `${Math.max(
                      day.minutes > 0 ? 6 : 2,
                      Math.min(100, (day.minutes / focusTarget) * 100),
                    )}%`,
                  }}
                  title={`${day.minutes} focused minutes`}
                />
              </div>
              <span>{day.date.slice(5)}</span>
              <small>{day.minutes}m</small>
            </div>
          ))}
        </div>
        <p className="productivity-week-caption">
          Total focus: {summary?.week.focused_minutes ?? 0} minutes ·
          {" "}Tasks: {summary?.week.tasks_completed ?? 0}/
          {summary?.week.tasks_total ?? 0} completed
        </p>
      </section>

      <section className="productivity-panel">
        <h3>Add a study task</h3>
        <form className="productivity-task-form" onSubmit={addTask}>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Task, e.g. Revise cell biology"
            maxLength={160}
            required
          />
          <input
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="Subject"
            maxLength={80}
            required
          />
          <select
            value={plannedMinutes}
            onChange={(event) => setPlannedMinutes(Number(event.target.value))}
          >
            <option value={25}>25 minutes</option>
            <option value={45}>45 minutes</option>
            <option value={60}>60 minutes</option>
            <option value={90}>90 minutes</option>
          </select>
          <button type="submit" disabled={saving}>
            <Plus size={17} /> {saving ? "Adding..." : "Add task"}
          </button>
        </form>

        <h3 className="productivity-task-heading">Tasks due today</h3>
        {tasks.length === 0 ? (
          <p className="productivity-empty">No tasks due today yet.</p>
        ) : (
          <ul className="productivity-task-list">
            {tasks.map((task) => (
              <li key={task.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={task.status === "completed"}
                    onChange={() => void toggleTask(task)}
                  />
                  <span className={task.status === "completed" ? "task-done" : ""}>
                    <strong>{task.title}</strong>
                    <small>{task.subject} · {task.planned_minutes} min</small>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="productivity-panel">
        <h3>Daily reflection</h3>
        <p className="productivity-reflection">
          {summary?.reflection?.trim()
            ? summary.reflection
            : "No reflection recorded today."}
        </p>
        <p className="productivity-week-caption">
          This dashboard shows recorded activity. Study sessions, quiz results,
          and reflections must be saved to the backend before they appear here.
        </p>
      </section>
    </main>
  );
}
