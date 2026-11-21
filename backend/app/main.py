import logging
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .schemas import ProcessResponse, SubmitResponse, JobStatusResponse
from .parse_minutes import parse_minutes

_log = logging.getLogger("minutesai.backend")

app = FastAPI(title="MinutesAI Local API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_colab_headers = lambda: {"x-api-key": settings.colab_api_key}
_colab_url = lambda path: settings.colab_inference_url.rstrip("/") + path


def remote_configured() -> bool:
    return bool(settings.colab_inference_url.strip() and settings.colab_api_key.strip())


def _require_remote():
    if not remote_configured():
        raise HTTPException(
            status_code=503,
            detail="Colab GPU is not connected. Start the Colab notebook and set COLAB_INFERENCE_URL and COLAB_API_KEY in backend/.env.",
        )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    if not remote_configured():
        return {"status": "needs_setup", "message": "Add COLAB_INFERENCE_URL and COLAB_API_KEY to backend/.env"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _colab_url("/health"),
                headers=_colab_headers(),
            )
            response.raise_for_status()
            remote = response.json()
        return {"status": "ok", "inference": "Google Colab GPU", "remote": remote}
    except Exception as exc:
        return {"status": "offline", "message": str(exc)}


# ---------------------------------------------------------------------------
# Async job flow — submit / status / result
# ---------------------------------------------------------------------------
@app.post("/api/submit", response_model=SubmitResponse)
async def submit_meeting(audio: UploadFile = File(...)):
    """Upload audio and get back a job_id immediately."""
    _require_remote()
    filename = audio.filename or "meeting-audio.wav"
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File is larger than the {settings.max_upload_mb} MB limit.")
    try:
        # /submit returns instantly — no long HTTP wait, no Cloudflare 524
        timeout = httpx.Timeout(connect=30, read=60, write=120, pool=30)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _colab_url("/submit"),
                headers=_colab_headers(),
                files={"audio": (filename, content, audio.content_type or "application/octet-stream")},
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=f"Colab error: {detail}")
        return response.json()
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upload to Colab timed out.")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Colab GPU: {exc}")


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str):
    """Poll the Colab server for processing status."""
    _require_remote()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _colab_url(f"/status/{job_id}"),
                headers=_colab_headers(),
            )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Job not found on Colab server.")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Colab GPU: {exc}")


@app.get("/api/result/{job_id}", response_model=ProcessResponse)
async def job_result(job_id: str):
    """Fetch the completed meeting minutes from Colab.

    Safety net: if the Colab parser failed silently (summary is empty or
    contains the full JSON blob), re-parse locally using parse_minutes.
    """
    _require_remote()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                _colab_url(f"/result/{job_id}"),
                headers=_colab_headers(),
            )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Job not found on Colab server.")
        if response.status_code == 202:
            raise HTTPException(status_code=202, detail="Job is still processing.")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=f"Colab error: {detail}")

        data = response.json()

        # --- Safety re-parse ---
        # If the Colab returned a result where parsing clearly failed
        # (summary is empty/contains JSON, discussion_points empty, etc.),
        # re-parse locally using the fixed parse_minutes.
        minutes = data.get("minutes", {})
        summary = minutes.get("summary", "")
        needs_reparse = (
            (not summary)  # empty summary
            or summary.lstrip().startswith("{")  # summary IS the raw JSON
            or (
                not minutes.get("discussion_points")
                and not minutes.get("takeaways")
                and not minutes.get("action_items")
                and minutes.get("markdown", "").lstrip().startswith("{")
            )
        )

        if needs_reparse:
            # The markdown field may contain the raw LLM output when parsing failed
            raw_llm = minutes.get("markdown", "")
            if raw_llm and raw_llm.lstrip().startswith("{"):
                _log.warning("Re-parsing minutes locally — Colab parser appears to have failed")
                reparsed = parse_minutes(raw_llm)
                data["minutes"] = reparsed.model_dump()
                _log.info("Local re-parse result: title=%s, date=%s, summary_len=%d",
                          reparsed.title, reparsed.date, len(reparsed.summary))

        return data
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Colab GPU: {exc}")
