# 課程與演講錄音自動化整理工具 / Lecture & Seminar Audio Transcribe & Summarize Tool

[English](#english) | [繁體中文](#繁體中文)

---

## 繁體中文

這是一個為課程、演講或講座錄音設計的自動化整理工具。它能將多段錄音自動進行語音辨識、時間軸對齊與合併，並透過本地 BERT 模型進行標點符號還原與錯字校正，最終由 AI 助理主動薈萃出結構化的書面知識報告與重點整理筆記。

### 🌟 核心特色
1. **雙軌語音辨識 (ASR)**: 支援本地端執行輕量 Whisper 模型（`tiny`/`base`/`small`），或呼叫雲端 OpenAI Whisper API 進行高品質 `large-v3` 辨識。
2. **大檔案自動切片與重疊**: 針對大於 25MB 的檔案自動分切成 10 分鐘小段（重疊 5 秒），辨識後自動連續合併時間軸，避開 API 上傳限制。
3. **多音訊自動合併**: 支援 Part 1、Part 2 多錄音檔偵測，自動累加時間軸並附上 `[Part X]` 標記。
4. **本地標點符號與專名校正**: 使用本地 BERT 模型還原全形標點符號（，。？！：），並透過 `lecture_metadata.json` 自訂去除口頭禪與校正同音錯字。
5. **AI 智慧筆記生成**: 逐字稿產出後，AI 會主動且立即輸出高質感的「書面知識報告（含 Q&A）」與「重點整理（含 Mermaid 邏輯地圖、詞彙表、錯字對照表）」。

### 🛠️ 安裝與準備工作
1. 確保系統已安裝 `ffmpeg` 並加入環境變數中。
2. 安裝必要的 Python 套件：
   ```bash
   pip install faster-whisper requests transformers torch tqdm
   ```
3. 在專案根目錄建立 `.env` 檔案並填入您的 OpenAI 金鑰以啟用雲端辨識（本機 `.gitignore` 已設定自動忽略此檔，請放心）：
   ```env
   OPENAI_API_KEY=您的sk-...金鑰
   ```

### 🚀 快速使用指南

#### 執行語音轉文字 (ASR)
```powershell
# 1. 使用雲端 OpenAI 高品質辨識（推薦，2.5小時音訊約僅需 0.9 美元）
python lecture_to_notes.py "您的錄音檔路徑或資料夾" --openai

# 2. 使用本地輕量模型辨識（免付費，預設 base 模型）
python lecture_to_notes.py "您的錄音檔路徑或資料夾" --model base
```

#### 標點還原與格式化逐字稿
```powershell
python generate_final_transcript.py
```
*(程式將讀取 `lecture_metadata.json` 的校正詞庫與產出的 SRT，生成最終的 `主題-逐字稿.md`。)*

#### AI 筆記生成
當 `主題-逐字稿.md` 產生後，AI 助理會**自動監聽並立即輸出**：
* `主題-書面知識報告.md` (教科書級內容與 Q&A 彙整)
* `主題-重點整理.md` (摘要、Mermaid 邏輯架構圖、重點條列、詞彙表、錯字對照)

---

## English

An automated workflow tool designed to turn lecture and seminar audio recordings into highly structured, publication-grade learning materials. It supports automated transcription, multi-part audio merging, punctuation restoration, and automatic AI synthesis of study guides and reports.

### 🌟 Key Features
1. **Dual ASR Engines**: Support for local lightweight Whisper models (`tiny`/`base`/`small`) and cloud-based OpenAI Whisper API for high-precision `large-v3` transcription.
2. **Auto Chunking & Overlapping**: Automatically segments files >25MB into 10-minute clips with 5-second overlap to bypass API constraints and merges them seamlessly.
3. **Multi-Part Merging**: Automatically aggregates consecutive audio segments (e.g. Part 1, Part 2) with continuous timestamps and `[Part X]` tags.
4. **Local Punctuation & Custom Dictionary**: Utilizes a local BERT model to restore Traditional Chinese punctuation, filters oral tics, and corrects homophone errors using `lecture_metadata.json`.
5. **AI Synthesis Automation**: Once the transcript is prepared, the AI agent instantly synthesizes a "Knowledge Report (with Q&A)" and a "Study Guide (with Mermaid diagrams, glossaries, and correction tables)".

### 🛠️ Prerequisites & Setup
1. Ensure `ffmpeg` is installed and added to your system's PATH.
2. Install Python dependencies:
   ```bash
   pip install faster-whisper requests transformers torch tqdm
   ```
3. Create a `.env` file in the root directory and add your OpenAI API key (the `.gitignore` is already configured to keep this key safe):
   ```env
   OPENAI_API_KEY=your_sk_key_here
   ```

### 🚀 Quick Start

#### Run Speech-to-Text (ASR)
```powershell
# 1. Cloud-based OpenAI Whisper (Recommended for speed and accuracy)
python lecture_to_notes.py "path_to_audio_or_folder" --openai

# 2. Local Whisper (Free offline mode, defaults to base model)
python lecture_to_notes.py "path_to_audio_or_folder" --model base
```

#### Run Punctuation & Spelling Corrections
```powershell
python generate_final_transcript.py
```
*(This parses the output SRT and glossary from `lecture_metadata.json` to generate the final `<Subject>-逐字稿.md`.)*

#### Automatic AI Notes Generation
As soon as the transcript markdown is created, the AI agent **instantly triggers** the creation of:
* `<Subject>-書面知識報告.md` (Comprehensive textbooks and Q&A compilations)
* `<Subject>-重點整理.md` (Summaries, Mermaid logic maps, glossaries, and ASR logs)
