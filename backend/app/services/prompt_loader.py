from pathlib import Path
_BASE_DIR = Path(__file__).resolve().parent

def _load_markdown(filename: str) -> str:
    try:
        return (_BASE_DIR / filename).read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on deployment environment
        raise RuntimeError(f"Unable to load rubric file '{filename}'.") from exc
    
SPEAKING_RUBRIC = _load_markdown("speaking-rubric.md")
WRITING_RUBRIC = _load_markdown("writing-rubric.md")

SPEAKING_FEEDBACK_PROMPT_TEMPLATE = """
You are a certified TOEFL speaking evaluator. Listen to the student's response audio and assess it using the rubric below.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

Write markdown feedback for the student with the following structure:

## Overall Evaluation
- Provide the score (0-4) with a brief justification.
- Summarize the student's overall performance in 2-3 sentences.

## Strengths
- Bullet list of concrete, encouraging observations tied to the rubric.

## Priority Improvements
- Bullet list of actionable advice tailored to this student's current proficiency.

Do not propose improved or rewritten responses in this section.
"""

SPEAKING_IMPROVEMENT_PROMPT_TEMPLATE = """
You are now the student's TOEFL speaking coach. Using the evaluation below, craft improved responses that the student could realistically deliver next time.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

EVALUATION (do not repeat verbatim, use for guidance):
{feedback}

Listen again to the student's original audio response (provided). Produce exactly two improved responses that:
- Preserve the student's intent and personality.
- Incorporate the priority improvements from the evaluation.
- Sound natural for a learner at the student's current level.

Format the output in markdown as:

## Improved Response 1
<full transcript>

## Improved Response 2
<full transcript>

Do not provide scores or additional commentary beyond the improved transcripts.
"""

WRITING_FEEDBACK_PROMPT_TEMPLATE = """
You are a TOEFL writing evaluator. Review the student's essay according to the rubric below.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

STUDENT RESPONSE:
{answer}

Write markdown feedback for the student with the following structure:

## Overall Evaluation
- Provide the score (0-5) with a concise justification (2-3 sentences).

## Strengths
- Bullet list of specific positives tied to the rubric categories.

## Priority Improvements
- Bullet list of the highest-impact revisions the student should focus on.

Do not rewrite the essay or provide improved versions in this section.
"""

WRITING_IMPROVEMENT_PROMPT_TEMPLATE = """
You are now the student's TOEFL writing tutor. Using the evaluation below, deliver two revised essays that the student can study and emulate.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

EVALUATION (for reference):
{feedback}

ORIGINAL ESSAY:
{answer}

Produce exactly two improved essays that:
- Directly address the same task prompt.
- Incorporate the feedback while keeping a realistic tone and length for the student.
- Highlight better organization, vocabulary, and grammar without sounding far beyond the student's level.

Format the output in markdown as:

## Improved Essay 1
<full revised essay>

## Improved Essay 2
<full revised essay>

Do not include scores or additional commentary outside of the essays.
"""