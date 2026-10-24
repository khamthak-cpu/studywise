
const API_URL = (
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://localhost:8000"
).replace(/\/+$/, "");

export const STUDENT_ID = "demo-student";

export type Task = {
  id: number;
  title: string;
  subject: string;
  planned_minutes: number;
  due_date: string;
  status: "pending" | "completed";
};

export type DailySummary = {
  student_id: string;
  date: string;
  score: number | null;
  scoring_version: string;
  tasks: {
    completed: number;
    total: number;
  };
  focused_minutes: number;
  interruptions: number;
  session_count: number;
  learning: {
    correct: number;
    questions: number;
    accuracy: number | null;
  };
  reflection: string;
  components: {
    task_completion: {
      score: number | null;
      weight: number;
      completed: number;
      total: number;
    };
    focus: {
      score: number | null;
      weight: number;
      focused_minutes: number;
      target_minutes: number;
    };
    learning: {
      score: number | null;
      weight: number;
      correct: number;
      questions: number;
    };
    reflection: {
      score: number | null;
      weight: number;
      completed: boolean;
    };
  };
  week: {
    focused_minutes: number;
    tasks_completed: number;
    tasks_total: number;
    quiz_accuracy: number | null;
    daily_focus: {
      date: string;
      minutes: number;
    }[];
  };
};

type RequestOptions = Omit<RequestInit, "headers"> & {
  headers?: HeadersInit;
};

async function request<T>(
  path: string,
  init: RequestOptions = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new Error(
      `Cannot connect to StudyWise API at ${API_URL}. ` +
        "Check that FastAPI is running and the API URL is correct.",
    );
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const body = await response.json();

      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item: { msg?: string }) => item.msg ?? "Invalid input")
          .join("; ");
      } else if (typeof body.message === "string") {
        message = body.message;
      }
    } catch {
      // Keep the HTTP status message if the response is not JSON.
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function validateDate(date: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error("Date must use YYYY-MM-DD format.");
  }

  const parsed = new Date(`${date}T00:00:00Z`);

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== date
  ) {
    throw new Error("Please provide a valid calendar date.");
  }

  return date;
}

function queryDate(date: string): string {
  return encodeURIComponent(validateDate(date));
}

// Daily productivity summary
export function getSummary(date: string): Promise<DailySummary> {
  return request<DailySummary>(
    `/productivity/summary?student_id=${encodeURIComponent(STUDENT_ID)}&date=${queryDate(date)}`,
  );
}

// Tasks for a selected date
export function getTasks(
  date: string,
): Promise<{ items: Task[] }> {
  return request<{ items: Task[] }>(
    `/productivity/tasks?student_id=${encodeURIComponent(STUDENT_ID)}&date=${queryDate(date)}`,
  );
}

export type NewTask = {
  title: string;
  subject: string;
  planned_minutes: number;
  due_date: string;
};

// Create a task
export function addTask(task: NewTask): Promise<Task> {
  if (!task.title.trim()) {
    throw new Error("Task title cannot be empty.");
  }

  if (!task.subject.trim()) {
    throw new Error("Subject cannot be empty.");
  }

  if (
    !Number.isInteger(task.planned_minutes) ||
    task.planned_minutes < 5 ||
    task.planned_minutes > 480
  ) {
    throw new Error("Planned minutes must be between 5 and 480.");
  }

  return request<Task>("/productivity/tasks", {
    method: "POST",
    body: JSON.stringify({
      ...task,
      title: task.title.trim(),
      subject: task.subject.trim(),
      student_id: STUDENT_ID,
      due_date: validateDate(task.due_date),
    }),
  });
}

// Mark a task as completed or pending
export function updateTask(
  id: number,
  completed: boolean,
): Promise<Task> {
  if (!Number.isInteger(id) || id < 1) {
    throw new Error("Invalid task ID.");
  }

  return request<Task>(`/productivity/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({
      student_id: STUDENT_ID,
      completed,
    }),
  });
}

export type NewSession = {
  subject: string;
  started_at: string;
  ended_at: string;
  focused_seconds: number;
  interruptions: number;
  task_id: number | null;
  note: string;
};

// Record a focus session
export function addSession(body: NewSession): Promise<unknown> {
  const start = new Date(body.started_at);
  const end = new Date(body.ended_at);

  if (
    Number.isNaN(start.getTime()) ||
    Number.isNaN(end.getTime()) ||
    end <= start
  ) {
    throw new Error("Session end time must be after its start time.");
  }

  if (!body.subject.trim()) {
    throw new Error("Subject cannot be empty.");
  }

  if (
    !Number.isInteger(body.focused_seconds) ||
    body.focused_seconds < 1 ||
    body.focused_seconds > 86400
  ) {
    throw new Error("Focused time must be between 1 second and 24 hours.");
  }

  if (body.focused_seconds > (end.getTime() - start.getTime()) / 1000) {
    throw new Error("Focused time cannot exceed the session duration.");
  }

  if (
    !Number.isInteger(body.interruptions) ||
    body.interruptions < 0 ||
    body.interruptions > 1000
  ) {
    throw new Error("Interruptions must be between 0 and 1000.");
  }

  return request<unknown>("/productivity/sessions", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      subject: body.subject.trim(),
      started_at: start.toISOString(),
      ended_at: end.toISOString(),
      student_id: STUDENT_ID,
    }),
  });
}

export type NewAssessment = {
  subject: string;
  total_questions: number;
  correct_answers: number;
  delayed_recall: boolean;
};

// Record quiz results
export function addAssessment(
  body: NewAssessment,
): Promise<unknown> {
  if (!body.subject.trim()) {
    throw new Error("Subject cannot be empty.");
  }

  if (
    !Number.isInteger(body.total_questions) ||
    body.total_questions < 1 ||
    body.total_questions > 500
  ) {
    throw new Error("Questions must be between 1 and 500.");
  }

  if (
    !Number.isInteger(body.correct_answers) ||
    body.correct_answers < 0 ||
    body.correct_answers > body.total_questions
  ) {
    throw new Error("Correct answers must be between 0 and total questions.");
  }

  return request<unknown>("/productivity/assessments", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      subject: body.subject.trim(),
      student_id: STUDENT_ID,
      taken_at: new Date().toISOString(),
    }),
  });
}

// Save daily reflection
export function saveReflection(
  date: string,
  reflection: string,
): Promise<unknown> {
  if (reflection.length > 1000) {
    throw new Error("Reflection must be 1000 characters or fewer.");
  }

  return request<unknown>("/productivity/reflection", {
    method: "PUT",
    body: JSON.stringify({
      student_id: STUDENT_ID,
      date: validateDate(date),
      reflection: reflection.trim(),
    }),
  });
}

// Local date in YYYY-MM-DD format
export function localDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}
