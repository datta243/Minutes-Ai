from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str
    owner: str = "Not specified"
    due_date: str = "Not specified"


class MeetingMinutes(BaseModel):
    title: str = "Meeting Minutes"
    date: str = "Not specified"
    location: str = "Not specified"
    attendees: list[str] = Field(default_factory=list)
    summary: str = ""
    discussion_points: list[str] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    markdown: str = ""


class ProcessResponse(BaseModel):
    transcript: str
    minutes: MeetingMinutes
    transcription_model: str
    summarization_model: str


class SubmitResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    error: str | None = None
