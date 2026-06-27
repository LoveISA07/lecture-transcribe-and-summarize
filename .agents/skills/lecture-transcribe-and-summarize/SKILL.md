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

### 2. Punctuation Restoration & Correction
- **Tool**: `generate_final_transcript.py`
- **Execution**: The agent runs this script to restore punctuation (using a local BERT punctuation model) and apply custom spelling corrections/oral tic removal defined in `lecture_metadata.json`.
- **Output**: `<Subject>-逐字稿.md`

### 3. Automatic Synthesis (No User Command Needed)
- **Execution**: As soon as the transcript is generated, the agent **proactively and immediately** synthesizes the following two files:
  - **`<Subject>-書面知識報告.md`**
  - **`<Subject>-重點整理.md`**
- **Q&A Handling**: If a Q&A session is present at the end of the lecture transcript, it is structured as a dedicated section at the end of the Knowledge Report.

## Common Mistakes
1. **Running on wrong directory**: Make sure to run commands with full paths or from the directory containing `lecture_to_notes.py`.
2. **Missing API Key**: For OpenAI transcription, ensure `OPENAI_API_KEY` is set in the local `.env` file, and that `.env` is added to `.gitignore` to avoid leaking it to GitHub.
