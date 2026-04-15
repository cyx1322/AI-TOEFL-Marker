from pydantic import BaseModel, EmailStr, Field
from fastapi import Form

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class WritingImprovementsRequest(BaseModel):
    question_text: str = Form(..., description="Writing task question."),
    answer_text: str = Form(..., description="Student's written response.")
    feedback_text: str = Form(..., description="Feedback generated previously."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),