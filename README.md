# MinutesAI — AI Meeting Minutes Generator

A full-stack app based on the supplied Week 3 Day 5 notebook, using Google Colab Free as the temporary GPU inference server:
1. Upload an audio file.
2. Transcribe it with `openai/whisper-medium.en`.
3. Analyze the transcript with `meta-llama/Llama-3.2-3B-Instruct`.
4. Produce meeting summary, attendees/location/date, discussion points, takeaways, and action items with owners.

## Architecture
- `frontend/`: React + Vite + TypeScript
- `backend/`: FastAPI proxy running on your laptop
- `MinutesAI_Colab_GPU_Server.ipynb`: Whisper + Llama inference API running on Colab GPU
- Inference runs in the Python backend. A CUDA GPU is strongly recommended.

## Requirements
- Python 3.10 or 3.11
- Node.js 20+
- NVIDIA GPU with a compatible CUDA/PyTorch installation recommended
- Hugging Face account/token with access to `meta-llama/Llama-3.2-3B-Instruct`
  (accept Meta's model terms on Hugging Face first)

## 1. Start the Colab GPU server

1. Upload `MinutesAI_Colab_GPU_Server.ipynb` to Google Colab.
2. Choose Runtime → Change runtime type → T4 GPU (if available).
3. Add a Colab Secret named `HF_TOKEN` with your Hugging Face token.
4. Confirm you have accepted the Llama 3.2 3B Instruct model terms on Hugging Face.
5. Run all notebook cells. Copy the printed `COLAB_INFERENCE_URL` and `COLAB_API_KEY`.

Keep the Colab runtime open while using the app. Colab Free sessions are temporary.

## 2. Configure the local backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and paste the `COLAB_INFERENCE_URL` and `COLAB_API_KEY` printed by the Colab notebook.

Install a PyTorch build matching your CUDA version from https://pytorch.org/get-started/locally/.
For a CPU-only test, install CPU PyTorch; inference will be much slower.

Run:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## 3. Configure the frontend

In another terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

The Vite dev server proxies `/api` to FastAPI at `http://localhost:8000`.

## Model behavior
- Whisper: `openai/whisper-medium.en` (English model, as in the notebook).
- Llama: `meta-llama/Llama-3.2-3B-Instruct`.
- If CUDA + bitsandbytes are available, Llama is loaded in 4-bit NF4 with double quantization and bfloat16 compute, matching the notebook's quantization setup.
- Your laptop does not load either AI model; it only runs the frontend and proxy.
- The local FastAPI service forwards audio to the Colab inference API. Colab loads the models once per runtime.
- The generated report is parsed into structured sections. If the model returns malformed JSON, the backend falls back to retaining the raw generated Markdown.

## Notes
- The notebook includes an OpenAI transcription alternative in its headings/imports, but its executed transcription path uses the Hugging Face Whisper pipeline. This implementation follows that active Whisper path.
- The sample app stores no meeting history yet. Audio is processed in a temporary file and removed after processing.
- Do not expose your Hugging Face token in frontend code or commit `.env`.
