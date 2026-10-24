const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";
export const STUDENT_ID = "demo-student";
export type Task = { id:number; title:string; subject:string; planned_minutes:number; due_date:string; status:"pending"|"completed" };
export type DailySummary = {
  date:string; score:number|null; scoring_version:string; tasks:{completed:number;total:number}; focused_minutes:number; interruptions:number; session_count:number;
  learning:{correct:number;questions:number;accuracy:number|null}; reflection:string;
  components:{task_completion:{score:number|null;weight:number;completed:number;total:number};focus:{score:number|null;weight:number;focused_minutes:number;target_minutes:number};learning:{score:number|null;weight:number;correct:number;questions:number};reflection:{score:number|null;weight:number;completed:boolean}};
  week:{focused_minutes:number;tasks_completed:number;tasks_total:number;quiz_accuracy:number|null;daily_focus:{date:string;minutes:number}[]};
};
async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response=await fetch(`${API_URL}${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers||{})}});
  if(!response.ok){const detail=await response.text().catch(()=>"");throw new Error(detail||`Request failed (${response.status})`)}
  return response.json() as Promise<T>;
}
export const getSummary=(date:string)=>request<DailySummary>(`/productivity/summary?student_id=${encodeURIComponent(STUDENT_ID)}&date=${date}`);
export const getTasks=(date:string)=>request<{items:Task[]}>(`/productivity/tasks?student_id=${encodeURIComponent(STUDENT_ID)}&date=${date}`);
export const addTask=(task:{title:string;subject:string;planned_minutes:number;due_date:string})=>request<Task>("/productivity/tasks",{method:"POST",body:JSON.stringify({...task,student_id:STUDENT_ID})});
export const updateTask=(id:number,completed:boolean)=>request<Task>(`/productivity/tasks/${id}`,{method:"PATCH",body:JSON.stringify({student_id:STUDENT_ID,completed})});
export const addSession=(body:{subject:string;started_at:string;ended_at:string;focused_seconds:number;interruptions:number;task_id:number|null;note:string})=>request("/productivity/sessions",{method:"POST",body:JSON.stringify({...body,student_id:STUDENT_ID})});
export const addAssessment=(body:{subject:string;total_questions:number;correct_answers:number;delayed_recall:boolean})=>request("/productivity/assessments",{method:"POST",body:JSON.stringify({...body,student_id:STUDENT_ID,taken_at:new Date().toISOString()})});
export const saveReflection=(date:string,reflection:string)=>request("/productivity/reflection",{method:"PUT",body:JSON.stringify({student_id:STUDENT_ID,date,reflection})});
export function localDate(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`}
