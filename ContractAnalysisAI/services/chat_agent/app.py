from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

# ------------------------
# Initialize FastAPI
# ------------------------
app = FastAPI(title="Chat Agent Service")

# ------------------------
# Load HuggingFace Flan-T5 Small
# ------------------------
chat_model = pipeline(
    "text2text-generation",          # 👈 use text2text for Flan-T5
    model="google/flan-t5-small"
)

# ------------------------
# Request Schema
# ------------------------
class ChatRequest(BaseModel):
    document_id: str
    question: str

# ------------------------
# Routes
# ------------------------
@app.post("/chat")
async def chat_with_agent(req: ChatRequest):
    try:
        context = f"Contract ID: {req.document_id}\n"
        prompt = f"""
        You are a legal contract analysis assistant.
        Context: {context}
        Question: {req.question}
        Answer clearly and concisely:
        """

        outputs = chat_model(
            prompt,
            max_new_tokens=128
        )

        # Flan-T5 uses "generated_text"
        answer = outputs[0]["generated_text"].strip()
        return {"answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
