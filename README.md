# MinutesAI — AI-Powered Meeting Minutes Generator

MinutesAI is a full-stack AI application that converts meeting audio into structured meeting minutes. It uses automatic speech recognition and a large language model to generate summaries, identify discussion points, extract key takeaways, and organize action items.

The application combines a React frontend, FastAPI backend, and AI inference running on Google Colab with a Tesla T4 GPU.

## Features

- 🎙️ **Audio Transcription** — Convert meeting audio into text using Whisper.
- 📝 **Meeting Summarization** — Generate concise meeting summaries using Llama.
- 📌 **Discussion Points** — Extract important topics discussed during the meeting.
- 💡 **Key Takeaways** — Identify the main conclusions and insights.
- ✅ **Action Items** — Extract tasks, owners, and due dates when available.
- 📅 **Meeting Details** — Extract meeting title, date, location, and attendees.
- ⚡ **Asynchronous Processing** — Process longer audio files without blocking the application.
- 📊 **Progress Tracking** — Track the processing status of submitted jobs.
- 🧩 **Structured Output** — Parse model-generated content into separate fields for display.

## Demo

<!-- Add your project screenshot or demo video here -->

<!-- Example:
![MinutesAI Demo](screenshots/minutesai-demo.png)
-->

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| Speech Recognition | OpenAI Whisper Medium |
| Large Language Model | Llama 3.2 3B Instruct |
| Model Quantization | 4-bit |
| GPU Inference | Google Colab, Tesla T4 |
| API Tunneling | Cloudflare Quick Tunnel |

## Architecture

```text
                 ┌──────────────────────┐
                 │      React UI        │
                 │   React + Vite       │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Local FastAPI     │
                 │      Backend        │
                 └──────────┬───────────┘
                            │
                    Cloudflare Tunnel
                            │
                            ▼
                 ┌──────────────────────┐
                 │  Colab FastAPI API  │
                 │   Async Job Queue   │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Whisper Medium    │
                 │  Audio Transcriber  │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │  Llama 3.2 3B       │
                 │  Meeting Summarizer │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Structured Minutes  │
                 │ Summary, Takeaways, │
                 │ Discussion, Actions │
                 └──────────────────────┘
```

## How It Works

1. The user uploads a meeting audio file through the React frontend.
2. The frontend sends the audio to the local FastAPI backend.
3. The backend submits the audio to the Colab inference server through a Cloudflare tunnel.
4. The Colab server creates an asynchronous job and returns a job ID.
5. Whisper transcribes the audio into text.
6. Llama processes the transcript and generates structured meeting minutes.
7. The backend parses and validates the model output.
8. The frontend polls the job status and displays the completed meeting minutes.

## AI Models

### Whisper Medium

Model: `openai/whisper-medium.en`

Used for automatic speech recognition and converting meeting audio into text.

### Llama 3.2 3B Instruct

Model: `meta-llama/Llama-3.2-3B-Instruct`

Used for summarization and extracting structured meeting information.

The model is loaded using 4-bit quantization to reduce GPU memory requirements.

## Project Structure

```text
MinutesAI/
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── ...
│   ├── package.json
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── parse_minutes.py
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
│
├── MinutesAI_Colab_GPU_Server.ipynb
│
├── README.md
└── ...
```

*The structure above represents the main project components. File names may vary depending on your repository version.*

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Google account for Google Colab
- Hugging Face account with access to the selected Llama model
- Cloudflare Quick Tunnel (`cloudflared`)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/MinutesAI.git
cd MinutesAI
```

### 2. Set Up the Colab GPU Server

1. Open `MinutesAI_Colab_GPU_Server.ipynb` in Google Colab.
2. Select a GPU runtime, such as Tesla T4 when available.
3. Configure your Hugging Face authentication.
4. Run the notebook cells to install dependencies and load the models.
5. Start the Colab FastAPI server.
6. Start the Cloudflare Quick Tunnel to expose the API.

The tunnel provides a temporary public URL for connecting your local backend to Colab.

### 3. Configure the Backend

Navigate to the backend directory:

```bash
cd backend
```

Create a `.env` file based on `.env.example`.

Configure the Colab inference URL:

```env
COLAB_INFERENCE_URL=https://your-cloudflare-tunnel-url
```

Use the actual URL generated by your Cloudflare tunnel. Do not include a specific endpoint path if the backend expects only the base URL.

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The local API will be available at:

```text
http://localhost:8000
```

### 4. Set Up the Frontend

Open a new terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open the local URL shown in your terminal, usually:

```text
http://localhost:5173
```

## API Endpoints

The Colab inference server provides asynchronous endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check API health and parser version |
| POST | `/submit` | Submit audio for processing |
| GET | `/status/{job_id}` | Get job status and progress |
| GET | `/result/{job_id}` | Retrieve completed meeting minutes |

The local backend exposes corresponding proxy routes under `/api`.

## Structured Meeting Output

MinutesAI generates structured meeting information similar to:

```json
{
  "title": "Project Meeting",
  "date": "November 21, 2026",
  "location": "Meeting Room",
  "attendees": [
    "Project Manager",
    "Developer"
  ],
  "summary": "The team discussed project progress.",
  "discussion_points": [
    "Current development status",
    "Upcoming milestones"
  ],
  "takeaways": [
    "Complete the remaining development tasks."
  ],
  "action_items": [
    {
      "task": "Complete API integration",
      "owner": "Developer",
      "due_date": "Not specified"
    }
  ]
}
```

This is an illustrative example of the expected output structure.

## Challenges and Solutions

### 1. Long-Running AI Inference

Processing longer audio files can take several minutes.

**Solution:** Implemented asynchronous job processing with job IDs and status polling to avoid holding a single HTTP request open during inference.

### 2. Cloudflare Tunnel Timeouts

Long synchronous requests caused gateway timeouts.

**Solution:** Changed the workflow to submit jobs asynchronously and retrieve results through separate status and result endpoints.

### 3. Unreliable LLM JSON Output

Llama can generate malformed JSON, including unescaped control characters and quotation marks inside long text fields.

**Solution:** Implemented a multi-pass parsing strategy:

1. Attempt standard JSON parsing.
2. Sanitize literal control characters and retry.
3. Use a regex-based fallback to extract structured fields.
4. Add logging and regression tests for parsing failures.

### 4. Colab and Local Backend Integration

The local backend and Colab inference server run in separate environments.

**Solution:** Used FastAPI endpoints and Cloudflare Quick Tunnel to connect the local application with the remote GPU inference server.

## Testing

The project includes parser tests and regression tests for structured meeting output.

Run backend tests from the backend directory:

```bash
pytest
```

The Denver City Council sample was used to test extraction of meeting details, discussion points, takeaways, and action items.

## Limitations

- Google Colab Free GPU availability is not guaranteed.
- Colab sessions and Cloudflare Quick Tunnel URLs are temporary.
- The inference server must be running for the application to process audio.
- Processing time depends on audio duration and available GPU resources.
- AI-generated summaries and action items may contain errors and should be reviewed before sharing.
- Meeting details such as attendees, owners, and due dates may be unavailable if they are not clearly mentioned in the audio.

## Future Improvements

- Export meeting minutes as PDF.
- Support additional audio formats and languages.
- Add user authentication and meeting history.
- Improve speaker identification.
- Deploy the backend and inference service to persistent cloud infrastructure.
- Add editing and sharing features for generated minutes.

## Acknowledgements

- [OpenAI Whisper](https://github.com/openai/whisper)
- [Meta Llama](https://huggingface.co/meta-llama)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Google Colab](https://colab.research.google.com/)
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

---

**Built as a hands-on AI Engineering project to explore speech recognition, LLM integration, asynchronous APIs, and full-stack application development.**
