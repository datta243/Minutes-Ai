import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from .config import settings

class ModelManager:
    def __init__(self):
        self.asr = None
        self.tokenizer = None
        self.llm = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load(self):
        token = settings.hf_token
        print(f"Loading Whisper model: {settings.whisper_model}")
        self.asr = pipeline(
            "automatic-speech-recognition",
            model=settings.whisper_model,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device=0 if self.device == "cuda" else -1,
            token=token,
            return_timestamps=True,
        )

        print(f"Loading Llama model: {settings.llama_model} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(settings.llama_model, token=token)
        self.tokenizer.pad_token = self.tokenizer.eos_token

        if self.device == "cuda":
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
                bnb_4bit_quant_type="nf4",
            )
            self.llm = AutoModelForCausalLM.from_pretrained(
                settings.llama_model,
                device_map="auto",
                quantization_config=quant_config,
                token=token,
            )
        else:
            self.llm = AutoModelForCausalLM.from_pretrained(
                settings.llama_model,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
                token=token,
            )
            self.llm.to("cpu")
        self.llm.eval()

    def transcribe(self, audio_path: str) -> str:
        if self.asr is None:
            raise RuntimeError("Whisper model is not loaded")
        result = self.asr(audio_path)
        return (result.get("text") or "").strip()

    def summarize(self, transcript: str) -> str:
        if self.llm is None or self.tokenizer is None:
            raise RuntimeError("Llama model is not loaded")
        system_message = (
            "You produce minutes of meetings from transcripts, with summary, key discussion "
            "points, takeaways and action items with owners. Do not invent missing facts. "
            "Use 'Not specified' when date, location, attendees, owners, or due dates are absent. "
            "Return valid JSON only, with keys: title, date, location, attendees, summary, "
            "discussion_points, takeaways, action_items. action_items must be objects with "
            "task, owner, due_date. Also include a markdown field with a readable full report."
        )
        user_prompt = (
            "Create meeting minutes from the following transcript. Include a summary with "
            "attendees, location and date; discussion points; takeaways; and action items with owners. "
            "Do not infer details that are not present.\n\nTRANSCRIPT:\n" + transcript
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt},
        ]
        inputs = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        )
        input_device = next(self.llm.parameters()).device
        inputs = inputs.to(input_device)
        with torch.inference_mode():
            output = self.llm.generate(
                inputs,
                max_new_tokens=1800,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0][inputs.shape[-1]:]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()

models = ModelManager()
