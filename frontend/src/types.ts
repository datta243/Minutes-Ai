export type ActionItem = { task: string; owner: string; due_date: string };
export type Minutes = {
  title: string; date: string; location: string; attendees: string[];
  summary: string; discussion_points: string[]; takeaways: string[];
  action_items: ActionItem[]; markdown: string;
};
export type ProcessResult = {
  transcript: string; minutes: Minutes;
  transcription_model: string; summarization_model: string;
};

export type SubmitResponse = { job_id: string };
export type JobStatus = {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  stage: "queued" | "transcribing" | "summarizing" | "completed";
  error: string | null;
};
