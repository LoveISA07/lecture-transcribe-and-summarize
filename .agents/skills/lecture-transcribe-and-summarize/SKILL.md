---
name: lecture-transcribe-and-summarize
description: >-
  Automatically transcribes lecture/class audio files (locally or via OpenAI API)
  and synthesizes formatted transcripts, key summaries (with Mermaid logic maps),
  and comprehensive knowledge reports (with Q&A) without waiting for user commands.
---

# Lecture Transcribe and Summarize Workflow

## Overview
This skill automates the end-to-end process of turning raw lecture/class audio recordings (MP3, WAV, M4A) or pre-existing SRT files into high-quality, structured learning materials.

The output consists of three main files:
1. `<Subject>-逐字稿.md`: Formatted transcript with paragraphing, punctuation restored, and key terms bolded.
2. `<Subject>-重點整理.md`: Synthesized overview, including a Mermaid logic map, chapter-by-chapter summaries (with core arguments, bullet points, and details), a vocabulary table, and an ASR corrections table.
3. `<Subject>-書面知識報告.md`: A formal, textbook-grade book report summarizing all theoretical concepts and incorporating any Q&A sessions from the class.

## Quick Start
To trigger this skill, place your audio recording in the project folder and tell the agent:
"幫我轉錄並整理課程錄音：<檔名>.mp3"
Or if you already have an SRT file:
"幫我用現有的 SRT 整理筆記：<檔名>.srt"

## Workflow Steps
The agent executes the following steps automatically:

### 1. Speech-to-Text (ASR)
- **Tool**: `lecture_to_notes.py`
- **Execution**: The agent runs ASR to transcribe the audio. The user can specify `--openai` for cloud-based OpenAI Whisper API (which loads the API key from the local `.env` file) or run it locally using `--model base` or `--model small`.
- **Merging**: If multiple audio parts (e.g. Part 1, Part 2) are detected, the script automatically prompts the user to merge them, shifting timestamps and prefixing segments with `[Part X]`.
- **Output**: `<Subject>.srt`

### 2. Punctuation, Basic Correction & LLM Contextual Refinement
- **Step 2a: Generate Initial Metadata**: Before running the formatter on a new lecture, the Agent **MUST** read the raw `.srt` file, identify potential ASR errors (homophones, misheard English terms, brand typos), and estimate chapter transitions based on the content. Write these into `<Subject>_metadata.json` in the same directory.
- **Step 2b: Run Formatter**:
  - **Tool**: `generate_final_transcript.py`
  - **Execution**: Run `python generate_final_transcript.py "<Subject>.srt"`. It will automatically detect and load `<Subject>_metadata.json` to apply the corrections and chapter headers.
  - **Output**: `<Subject>-逐字稿.md`
- **Step 2c: LLM Contextual Refinement (CRITICAL)**:
  - **Action**: The Agent **MUST** read the generated `<Subject>-逐字稿.md`, use its LLM understanding to analyze the entire text paragraph-by-paragraph, and **directly edit the file** to correct any remaining homophones, garbled sentences, or contextually incorrect terms (e.g. correcting `床的經驗` to `臨床的經驗`, `郭忠祐` to `血糖波動`).
  - **Goal**: Ensure the final transcript is highly readable, grammatically correct, and professionally accurate before summarizing.

### 3. Automatic Synthesis (No User Command Needed)
- **Execution**: As soon as the refined transcript is ready, the agent **proactively and immediately** synthesizes the following two files:
  - **`<Subject>-書面知識報告.md`**
  - **`<Subject>-重點整理.md`**
- **Q&A Handling**: If a Q&A session is present at the end of the lecture transcript, it is structured as a dedicated section at the end of the Knowledge Report.

## Common Mistakes
1. **Running on wrong directory**: Make sure to run commands with full paths or from the directory containing `lecture_to_notes.py`.
2. **Missing API Key**: For OpenAI transcription, ensure `OPENAI_API_KEY` is set in the local `.env` file, and that `.env` is added to `.gitignore` to avoid leaking it to GitHub.
3. **Skipping Metadata Generation**: Do not run the formatter without generating the `<Subject>_metadata.json` file first, otherwise the transcript will not contain spelling corrections.
4. **Skipping Step 2c (LLM Refinement)**: Do not immediately synthesize summaries after Step 2b. Always perform a contextual review of the transcript first to fix remaining ASR errors.
