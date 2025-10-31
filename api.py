from typing import List, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette import status

from gemini_utils import audio_understanding, writing_feedback

app = FastAPI()

ALLOWED_MODELS = {"gemini-2.5-flash", "gemini-2.5-pro"}

MARKER_PROMPT = """
Assume you are a marker for the TOEFL test. Grade the following student's speaking test.
If there are two audio files, then one is the question (a dialogue or monologue); the other is the student's answer.
RUBRICS:
```
## Page 1

# TOEFL iBT®
# Independent Speaking Rubric

<table>
  <thead>
    <tr>
      <th>SCORE</th>
      <th>GENERAL DESCRIPTION</th>
      <th>DELIVERY</th>
      <th>LANGUAGE USE</th>
      <th>TOPIC DEVELOPMENT</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>4</b></td>
      <td>The response fulfills the demands of the task, with at most minor lapses in completeness. It is highly intelligible and exhibits sustained, coherent discourse. A response at this level is characterized by all of the following:</td>
      <td>Generally well-paced flow (fluid expression). Speech is clear. It may include minor lapses, or minor difficulties with pronunciation or intonation patterns, which do not affect overall intelligibility.</td>
      <td>The response demonstrates effective use of grammar and vocabulary. It exhibits a fairly high degree of automaticity with good control of basic and complex structures (as appropriate). Some minor (or systematic) errors are noticeable but do not obscure meaning.</td>
      <td>Response is sustained and sufficient to the task. It is generally well developed and coherent; relationships between ideas are clear (or there is a clear progression of ideas).</td>
    </tr>
    <tr>
      <td><b>3</b></td>
      <td>The response addresses the task appropriately but may fall short of being fully developed. It is generally intelligible and coherent, with some fluidity of expression, though it exhibits some noticeable lapses in the expression of ideas. A response at this level is characterized by at least two of the following:</td>
      <td>Speech is generally clear, with some fluidity of expression, though minor difficulties with pronunciation, intonation, or pacing are noticeable and may require listener effort at times (though overall intelligibility is not significantly affected).</td>
      <td>The response demonstrates fairly automatic and effective use of grammar and vocabulary, and fairly coherent expression of relevant ideas. Response may exhibit some imprecise or inaccurate use of vocabulary or grammatical structures or be somewhat limited in the range of structures used. This may affect overall fluency, but it does not seriously interfere with the communication of the message.</td>
      <td>Response is mostly coherent and sustained and conveys relevant ideas/information. Overall development is somewhat limited, usually lacks elaboration or specificity. Relationships between ideas may at times not be immediately clear.</td>
    </tr>
    <tr>
      <td><b>2</b></td>
      <td>The response addresses the task, but development of the topic is limited. It contains intelligible speech, although problems with delivery and/or overall coherence occur; meaning may be obscured in places. A response at this level is characterized by at least two of the following:</td>
      <td>Speech is basically intelligible, though listener effort is needed because of unclear articulation, awkward intonation, or choppy rhythm/pace; meaning may be obscured in places.</td>
      <td>The response demonstrates limited range and control of grammar and vocabulary. These limitations often prevent full expression of ideas. For the most part, only basic sentence structures are used successfully and spoken with fluidity. Structures and vocabulary may express mainly simple (short) and/or general propositions, with simple or unclear connections made among them (serial listing, conjunction, juxtaposition).</td>
      <td>The response is connected to the task, though the number of ideas presented or the development of ideas is limited. Mostly basic ideas are expressed with limited elaboration (details and support). At times relevant substance may be vaguely expressed or repetitious. Connections of ideas may be unclear.</td>
    </tr>
    <tr>
      <td><b>1</b></td>
      <td>The response is very limited in content and/or coherence or is only minimally connected to the task, or speech is largely unintelligible. A response at this level is characterized by at least two of the following:</td>
      <td>Consistent pronunciation, stress and intonation difficulties cause considerable listener effort; delivery is choppy, fragmented, or telegraphic; frequent pauses and hesitations.</td>
      <td>Range and control of grammar and vocabulary severely limit or prevent expression of ideas and connections among ideas. Some low-level responses may rely heavily on practiced or formulaic expressions.</td>
      <td>Limited relevant content is expressed. The response generally lacks substance beyond expression of very basic ideas. Speaker may be unable to sustain speech to complete the task and may rely heavily on repetition of the prompt.</td>
    </tr>
    <tr>
      <td><b>0</b></td>
      <td>Speaker makes no attempt to respond OR response is unrelated to the topic.</td>
      <td></td>
      <td></td>
      <td></td>
    </tr>
  </tbody>
</table>

&lt;img&gt;toefl ibt®&lt;/img&gt;

---


## Page 2

# TOEFL iBT®
# Integrated Speaking Rubric

<table>
  <thead>
    <tr>
      <th>SCORE</th>
      <th>GENERAL DESCRIPTION</th>
      <th>DELIVERY</th>
      <th>LANGUAGE USE</th>
      <th>TOPIC DEVELOPMENT</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>4</b></td>
      <td>The response fulfills the demands of the task, with at most minor lapses in completeness. It is highly intelligible and exhibits sustained, coherent discourse. A response at this level is characterized by all of the following:</td>
      <td>Speech is generally clear, fluid and sustained. It may include minor lapses or minor difficulties with pronunciation or intonation. Pace may vary at times as the speaker attempts to recall information. Overall intelligibility remains high.</td>
      <td>The response demonstrates good control of basic and complex grammatical structures that allow for coherent, efficient (automatic) expression of relevant ideas. Contains generally effective word choice. Though some minor (or systematic) errors or imprecise use may be noticeable, they do not require listener effort (or obscure meaning).</td>
      <td>The response presents a clear progression of ideas and conveys the relevant information required by the task. It includes appropriate detail, though it may have minor errors or minor omissions.</td>
    </tr>
    <tr>
      <td><b>3</b></td>
      <td>The response addresses the task appropriately, but may fall short of being fully developed. It is generally intelligible and coherent, with some fluidity of expression, though it exhibits some noticeable lapses in the expression of ideas. A response at this level is characterized by at least two of the following:</td>
      <td>Speech is generally clear, with some fluidity of expression, but it exhibits minor difficulties with pronunciation, intonation, or pacing and may require some listener effort at times. Overall intelligibility remains good, however.</td>
      <td>The response demonstrates fairly automatic and effective use of grammar and vocabulary, and fairly coherent expression of relevant ideas. Response may exhibit some imprecise or inaccurate use of vocabulary or grammatical structures or be somewhat limited in the range of structures used. Such limitations do not seriously interfere with the communication of the message.</td>
      <td>The response is sustained and conveys relevant information required by the task. However, it exhibits some incompleteness, inaccuracy, lack of specificity with respect to content, or choppiness in the progression of ideas.</td>
    </tr>
    <tr>
      <td><b>2</b></td>
      <td>The response is connected to the task, though it may be missing some relevant information or contain inaccuracies. It contains some intelligible speech, but at times problems with intelligibility and/or overall coherence may obscure meaning. A response at this level is characterized by at least two of the following:</td>
      <td>Speech is clear at times, though it exhibits problems with pronunciation, intonation, or pacing and so may require significant listener effort. Speech may not be sustained at a consistent level throughout. Problems with intelligibility may obscure meaning in places (but not throughout).</td>
      <td>The response is limited in the range and control of vocabulary and grammar demonstrated (some complex structures may be used, but typically contain errors). This results in limited or vague expression of relevant ideas and imprecise or inaccurate connections. Automaticity of expression may only be evident at the phrasal level.</td>
      <td>The response conveys some relevant information but is clearly incomplete or inaccurate. It is incomplete if it omits key ideas, makes vague reference to key ideas, or demonstrates limited development of important information. An inaccurate response demonstrates misunderstanding of key ideas from the stimulus. Typically, ideas expressed may not be well-connected or cohesive so that familiarity with the stimulus is necessary to follow what is being discussed.</td>
    </tr>
    <tr>
      <td><b>1</b></td>
      <td>The response is very limited in content or coherence or is only minimally connected to the task. Speech may be largely unintelligible. A response at this level is characterized by at least two of the following:</td>
      <td>Consistent pronunciation and intonation problems cause considerable listener effort and frequently obscure meaning. Delivery is choppy, fragmented, or telegraphic. Speech contains frequent pauses and hesitations.</td>
      <td>Range and control of grammar and vocabulary severely limit or prevent expression of ideas and connections among ideas. Some low-level responses may rely heavily on practiced or formulaic expressions.</td>
      <td>The response fails to provide much relevant content. Ideas that are expressed are often inaccurate, limited to vague utterances, or repetitions (including repetition of prompt).</td>
    </tr>
    <tr>
      <td><b>0</b></td>
      <td>Speaker makes no attempt to respond OR response is unrelated to the topic.</td>
      <td></td>
      <td></td>
      <td></td>
    </tr>
  </tbody>
</table>

<footer>Copyright © 2024 by ETS. TOEFL and TOEFL iBT are registered trademarks of ETS in the United States and other countries. The Eight-Point logo is a trademark of ETS.</footer>
&lt;img&gt;toefl ibt®&lt;/img&gt;
```
QUESTION:

"""

WRITING_PROMPT = """
You are a TOEFL writing evaluator. Review the student's response based on the CRITERIA below.

CRITERIA:
CRITERIA

QUESTION:
{question}

STUDENT RESPONSE:
{answer}

Provide detailed feedback and a score estimate in Markdown format. Include strengths, weaknesses, and actionable suggestions tied to the criteria.
"""
@app.post("/speaking-feedback")
async def speaking_feedback(
    guidance_text: str = Form(..., description="Question in text."),
    question_audio: UploadFile | None = File(None, description="Question Audio (Optional)."),
    answer_audio: UploadFile | None = File(None, description="Student's Answer (MP3 or WAV)."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
    # Backward-compatible field names used by the existing frontend
    audio_clip_one: UploadFile | None = File(None, description="Alt field: First audio clip."),
    audio_clip_two: UploadFile | None = File(None, description="Alt field: Second audio clip."),
) -> dict:
    """Provide feedback on up to two TOEFL speaking practice clips."""

    final_prompt = MARKER_PROMPT + "**" + guidance_text + "**"

    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )
    # Collect up to two clips from any of the accepted field names
    candidates = [question_audio, answer_audio, audio_clip_one, audio_clip_two]
    audio_files = [clip for clip in candidates if clip is not None][:2]

    if not audio_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one audio clip must be provided.",
        )

    def _map_mime(ct: str | None) -> str | None:
        if not ct:
            return None
        ct = ct.lower()
        if ct in {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}:
            return "audio/wav"
        if ct in {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mp3", "audio/x-mpeg-3"}:
            return "audio/mpeg"
        return None

    audio_payloads: List[Tuple[bytes, str | None]] = []
    for index, audio in enumerate(audio_files, start=1):
        try:
            data = await audio.read()
        except Exception as exc:  # pragma: no cover - depends on file backend
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to read audio clip {index}.",
            ) from exc
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio clip {index} is empty.",
            )
        audio_payloads.append((data, _map_mime(getattr(audio, "content_type", None))))

    try:
        # Pass (bytes, mime) items when available; the helper will sniff if None
        formatted = [
            (b, m) if m is not None else (b,)
            for (b, m) in audio_payloads
        ]
        if len(formatted) == 1:
            one = formatted[0]
            if len(one) == 1:
                payload = one[0]  # bytes only; helper will sniff
            else:
                payload = [one]   # list with (bytes, mime)
        else:
            payload = formatted  # list of items
        feedback = audio_understanding(payload, prompt=final_prompt, model=model_choice)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "feedback": feedback,
        "clips_received": len(audio_payloads),
    }


@app.post("/writing-feedback")
async def writing_feedback_endpoint(
    question_text: str = Form(..., description="Writing task question."),
    answer_text: str = Form(..., description="Student's written response."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
) -> dict:
    """Return Gemini-generated feedback for a TOEFL writing task."""

    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )

    if not question_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question text must not be empty.",
        )

    if not answer_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student response must not be empty.",
        )

    final_prompt = WRITING_PROMPT.format(
        question=question_text.strip(),
        answer=answer_text.strip(),
    )

    try:
        feedback = writing_feedback(final_prompt, model=model_choice)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"feedback": feedback}
