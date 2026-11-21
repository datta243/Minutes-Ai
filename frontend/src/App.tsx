import { useEffect, useRef, useState, useCallback } from "react";
import {
  AudioLines, UploadCloud, FileAudio, Sparkles, Clock3, CheckCircle2,
  FileText, ListChecks, Users, MapPin, CalendarDays, Download, Copy,
  ChevronDown, ChevronUp, LoaderCircle, Mic2, ShieldCheck, Zap, RefreshCw,
  AlertCircle
} from "lucide-react";
import type { ProcessResult, JobStatus } from "./types";

const POLL_INTERVAL = 3000;

const prettyError = (value: unknown) =>
  value instanceof Error ? value.message : "Something went wrong. Please try again.";

type Stage = "idle" | "uploading" | "queued" | "transcribing" | "summarizing" | "completed" | "failed";

const STAGE_LABELS: Record<Stage, string> = {
  idle: "Preparing your recording",
  uploading: "Uploading audio to server",
  queued: "Queued — waiting for GPU",
  transcribing: "Transcribing audio with Whisper",
  summarizing: "Generating structured minutes with Llama 3.2",
  completed: "Complete",
  failed: "Processing failed",
};

const STAGE_PROGRESS: Record<Stage, number> = {
  idle: 0, uploading: 10, queued: 20, transcribing: 45, summarizing: 75, completed: 100, failed: 0,
};

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState("");
  const [showTranscript, setShowTranscript] = useState(false);
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetch("/api/health").then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => setHealth("online")).catch(() => setHealth("offline"));
  }, []);

  // --- Cleanup polling on unmount ---
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // --- Poll for job status ---
  const startPolling = useCallback((id: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${id}`);
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: "Lost connection to server." }));
          throw new Error(body.detail || "Status check failed.");
        }
        const status: JobStatus = await res.json();

        // Map Colab stage to our UI stage
        if (status.status === "queued") setStage("queued");
        else if (status.status === "processing" && status.stage === "transcribing") setStage("transcribing");
        else if (status.status === "processing" && status.stage === "summarizing") setStage("summarizing");
        else if (status.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setStage("completed");
          // Fetch the actual result
          try {
            const resResult = await fetch(`/api/result/${id}`);
            if (!resResult.ok) {
              const body = await resResult.json().catch(() => ({ detail: "Failed to fetch result." }));
              throw new Error(body.detail || "Failed to fetch result.");
            }
            const data: ProcessResult = await resResult.json();
            setResult(data);
            setLoading(false);
          } catch (e) {
            setError(prettyError(e));
            setStage("failed");
            setLoading(false);
          }
        } else if (status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setError(status.error || "Processing failed on the server.");
          setStage("failed");
          setLoading(false);
        }
      } catch (e) {
        // Network error during polling — don't stop, it might recover
        console.warn("Poll error:", e);
      }
    }, POLL_INTERVAL);
  }, []);

  const chooseFile = (picked?: File) => {
    if (!picked) return;
    const allowed = /\.(mp3|wav|m4a|mp4|mpeg|mpga|webm|ogg|flac)$/i;
    if (!allowed.test(picked.name)) {
      setError("Choose an MP3, WAV, M4A, MP4, WEBM, OGG or FLAC audio file.");
      return;
    }
    setFile(picked); setResult(null); setError(""); setJobId(null); setStage("idle");
  };

  const processAudio = async () => {
    if (!file) return;
    setLoading(true); setError(""); setResult(null); setJobId(null);
    setStage("uploading");
    const form = new FormData(); form.append("audio", file);
    try {
      const response = await fetch("/api/submit", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Upload failed.");
      const id = data.job_id as string;
      setJobId(id);
      setStage("queued");
      startPolling(id);
    } catch (e) {
      setError(prettyError(e));
      setStage("failed");
      setLoading(false);
    }
  };

  const retryJob = () => {
    setError(""); setResult(null); setJobId(null); setStage("idle");
    // Re-trigger with the same file
    if (file) processAudio();
  };

  const resetAll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setFile(null); setResult(null); setError(""); setJobId(null); setStage("idle"); setLoading(false);
  };

  const downloadReport = () => {
    if (!result) return;
    const m = result.minutes;
    const content = m.markdown || [
      `# ${m.title}`, `Date: ${m.date}`, `Location: ${m.location}`,
      `Attendees: ${m.attendees.join(", ")}`, "", "## Summary", m.summary,
      "", "## Discussion points", ...m.discussion_points.map(x => `- ${x}`),
      "", "## Takeaways", ...m.takeaways.map(x => `- ${x}`),
      "", "## Action items", ...m.action_items.map(x => `- ${x.task} — ${x.owner} (${x.due_date})`)
    ].join("\n");
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    a.download = `${(m.title || "meeting-minutes").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
    a.click(); URL.revokeObjectURL(url);
  };

  const copyTranscript = async () => {
    if (result) await navigator.clipboard.writeText(result.transcript);
  };

  const isProcessing = loading && stage !== "idle";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><AudioLines size={21}/></div><span>minutes<span className="brand-ai">ai</span></span></div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="nav-item active"><FileText size={18}/> Meeting workspace</button>
        <div className="sidebar-bottom">
          <div className="sidebar-tip"><div className="tip-icon"><Sparkles size={16}/></div><strong>Less note-taking.<br/>More doing.</strong><p>Turn conversations into clear next steps.</p></div>
          <div className="profile"><div className="avatar">M</div><div><strong>My workspace</strong><small>Personal account</small></div><ChevronDown size={15}/></div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>Meeting minutes</strong></div>
          <div className="top-actions"><div className={`api-status ${health}`}><span/>{health === "online" ? "API connected" : health === "offline" ? "API offline" : "Checking API"}</div><div className="top-avatar">M</div></div>
        </header>

        <div className="content">
          <section className="hero">
            <div className="eyebrow"><Sparkles size={14}/> YOUR AI MEETING ASSISTANT</div>
            <h1>Make every meeting<br/><span>move work forward.</span></h1>
            <p className="hero-copy">Upload a recording and get a clear summary, key decisions, and action items — in minutes.</p>
            <div className="trust-row"><span><ShieldCheck size={15}/> Private processing</span><i/><span><Zap size={15}/> Whisper + Llama 3.2</span></div>
          </section>

          <section className="upload-card">
            <div className="section-heading"><div><h2>New meeting</h2><p>Start with an audio recording</p></div><div className="step-pill"><span>01</span> UPLOAD AUDIO</div></div>
            <div
              className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); chooseFile(e.dataTransfer.files[0]); }}
              onClick={() => !loading && inputRef.current?.click()}
              role="button" tabIndex={0}
              onKeyDown={e => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
            >
              <input ref={inputRef} type="file" accept=".mp3,.wav,.m4a,.mp4,.mpeg,.mpga,.webm,.ogg,.flac,audio/*" hidden onChange={e => chooseFile(e.target.files?.[0])}/>
              <div className="upload-icon">{file ? <FileAudio size={25}/> : <UploadCloud size={25}/>}</div>
              {file ? <><strong className="file-name">{file.name}</strong><p>{(file.size / (1024 * 1024)).toFixed(1)} MB · Ready to process</p></> : <><strong>Drop your audio file here</strong><p>or <span>browse files</span> from your device</p><small>MP3, WAV, M4A, MP4, WEBM · Up to 200 MB</small></>}
            </div>
            {file && !loading && <button className="remove-file" onClick={resetAll}>Remove file</button>}
            {error && <div className="error-box"><AlertCircle size={16}/> {error}{stage === "failed" && file && <button className="retry-btn" onClick={retryJob}><RefreshCw size={14}/> Retry</button>}</div>}
            <div className="upload-footer"><div className="privacy-note"><ShieldCheck size={16}/> Your audio is processed by your backend and deleted after processing.</div><button className="primary-btn" disabled={!file || loading} onClick={processAudio}>{loading ? <><LoaderCircle className="spin" size={17}/> Processing...</> : <><Sparkles size={17}/> Generate minutes <span>→</span></>}</button></div>
            {isProcessing && <div className="progress-wrap"><div className="progress-track"><div className="progress-bar" style={{ width: `${STAGE_PROGRESS[stage]}%`, transition: "width 0.6s ease" }}/></div><div className="progress-label"><LoaderCircle size={14} className="spin"/>{STAGE_LABELS[stage]}</div>{jobId && <small>Job ID: {jobId} · Polling every {POLL_INTERVAL / 1000}s. Large recordings can take several minutes.</small>}</div>}
          </section>

          {result && <section className="results">
            <div className="results-head"><div><div className="eyebrow"><CheckCircle2 size={14}/> GENERATION COMPLETE</div><h2>Your meeting minutes</h2><p>Review the AI-generated notes and action items below.</p></div><button className="secondary-btn" onClick={downloadReport}><Download size={16}/> Download report</button></div>
            <div className="report-card">
              <div className="report-title"><div className="report-icon"><FileText size={20}/></div><div><h3>{result.minutes.title || "Meeting Minutes"}</h3><span>Generated with MinutesAI</span></div></div>
              <div className="meta-grid">
                <div><CalendarDays size={16}/><div><small>DATE</small><strong>{result.minutes.date || "Not specified"}</strong></div></div>
                <div><MapPin size={16}/><div><small>LOCATION</small><strong>{result.minutes.location || "Not specified"}</strong></div></div>
                <div><Users size={16}/><div><small>ATTENDEES</small><strong>{result.minutes.attendees?.length ? result.minutes.attendees.join(", ") : "Not specified"}</strong></div></div>
              </div>
              <div className="report-section"><h4><FileText size={16}/> Executive summary</h4><p className="summary-text">{result.minutes.summary || "No summary available."}</p></div>
              <div className="report-section"><h4><AudioLines size={16}/> Key discussion points</h4>{result.minutes.discussion_points?.length ? <ul>{result.minutes.discussion_points.map((x,i)=><li key={i}>{x}</li>)}</ul> : <p className="muted">No discussion points identified in the transcript.</p>}</div>
              <div className="report-section"><h4><Sparkles size={16}/> Key takeaways</h4>{result.minutes.takeaways?.length ? <ul>{result.minutes.takeaways.map((x,i)=><li key={i}>{x}</li>)}</ul> : <p className="muted">No takeaways identified in the transcript.</p>}</div>
              <div className="report-section"><h4><ListChecks size={16}/> Action items <span className="count">{result.minutes.action_items?.length || 0}</span></h4>
                {result.minutes.action_items?.length ? <div className="action-list">{result.minutes.action_items.map((a,i)=><div className="action-row" key={i}><div className="action-check"><CheckCircle2 size={17}/></div><div className="action-main"><strong>{a.task}</strong><small>Owner: {a.owner || "Not specified"}</small></div><span className="due">{a.due_date || "No due date"}</span></div>)}</div> : <p className="muted">No action items identified in the transcript.</p>}
              </div>
              <div className="report-footer"><span><ShieldCheck size={14}/> Review AI-generated details before sharing.</span><span>{result.summarization_model}</span></div>
            </div>
            <div className="transcript-card">
              <div className="transcript-toggle" role="button" tabIndex={0} onClick={() => setShowTranscript(v=>!v)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") setShowTranscript(v=>!v); }}><span><Mic2 size={17}/> Original transcript</span><span className="transcript-actions"><button className="icon-btn" onClick={e=>{e.stopPropagation();copyTranscript();}} title="Copy transcript"><Copy size={15}/></button>{showTranscript ? <ChevronUp size={17}/> : <ChevronDown size={17}/>}</span></div>
              {showTranscript && <div className="transcript-body">{result.transcript}</div>}
            </div>
            <div className="model-note"><Clock3 size={14}/> Transcribed using {result.transcription_model} · Summarized using {result.summarization_model}</div>
          </section>}

          {!result && !isProcessing && <section className="how-it-works"><div className="section-heading"><div><h2>From audio to action</h2><p>Three steps. One productive meeting.</p></div></div><div className="steps"><div className="step"><div className="step-symbol"><UploadCloud size={19}/></div><div><b>01 · Upload</b><p>Add your meeting recording</p></div></div><div className="step-line"/><div className="step"><div className="step-symbol"><AudioLines size={19}/></div><div><b>02 · Transcribe</b><p>Whisper converts speech to text</p></div></div><div className="step-line"/><div className="step"><div className="step-symbol"><Sparkles size={19}/></div><div><b>03 · Summarize</b><p>Llama creates useful minutes</p></div></div></div></section>}

          <footer className="footer">Built for better meetings <span>·</span> Powered by open-source AI</footer>
        </div>
      </main>
    </div>
  );
}

export default App;
