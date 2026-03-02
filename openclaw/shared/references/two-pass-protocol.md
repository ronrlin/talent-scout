# Two-Pass Generation Protocol

Used by: `scout-resume` (generate mode), `scout-cover-letter`

## Why Two Passes?

A single generation pass tends to produce resumes and cover letters that:
- Include generic phrases ("proven track record", "results-driven leader")
- Mirror the job description too closely (keyword stuffing)
- Make claims that sound impressive but can't be defended in an interview
- Inflate responsibilities beyond what the candidate actually did

The two-pass protocol addresses this by separating creation from quality review.

## How It Works

### Pass 1: Generate
The first pass focuses on creating the best possible tailored document. It draws on:
- The candidate's base resume (ground truth)
- Job analysis with match assessment and positioning strategy
- Role lens guidance (engineering / product / program)
- Proven experience bullets from the corpus (if available)
- Additional context with supplementary real experiences (if available)

The goal is maximum alignment with the target role while staying grounded in real experience.

### Pass 2: Defensibility Review
The second pass critically evaluates the generated document as if reviewing someone else's work. It checks for:

1. **Generic content** — sentences that could appear on anyone's resume/cover letter
2. **JD parroting** — phrases that mirror the job description too closely
3. **Undefendable claims** — statements the candidate couldn't explain in an interview
4. **Inflated language** — overstated responsibilities or impact
5. **Unsubstantiated skills** — technologies listed without evidence in the experience section

The reviewer removes, rewrites, or tones down problematic content. The result is a document where every line is specific, grounded, and defensible.

## Quality Bar

After both passes, a hiring manager should be able to ask about ANY line on the document and receive a concrete, honest answer. Nothing should require backpedaling or clarification.
