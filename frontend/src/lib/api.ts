
const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function askStudyWise(question: string): Promise<string> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const raw = await response.text();

  let data: unknown;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw;
  }

  if (!response.ok) {
    const detail =
      data &&
      typeof data === "object" &&
      "detail" in data
        ? String(data.detail)
        : `Request failed: ${response.status}`;

    throw new Error(detail);
  }

  if (typeof data === "string") return data;

  if (data && typeof data === "object") {
    const result = data as Record<string, unknown>;

    for (const key of ["answer", "response", "message", "output", "content"]) {
      if (typeof result[key] === "string") {
        return result[key] as string;
      }
    }
  }

  throw new Error("The backend response format was not recognized.");
}
