import os
import sys
import re
import math
import subprocess
import argparse
from tqdm import tqdm

# Import faster-whisper lazily to avoid import errors if not installed yet
def get_whisper_model(model_size):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("錯誤：未偵測到 faster-whisper 套件。請先執行 'pip install faster-whisper' 安裝。")
        sys.exit(1)
        
    print(f"正在載入 Whisper 模型 ({model_size})... 這在第一次執行時可能需要下載模型檔。")
    
    # Auto-detect device (use CUDA if available)
    device = "cpu"
    compute_type = "float32"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
            print("偵測到 CUDA GPU，將使用 GPU 進行加速。")
    except Exception:
        pass
        
    return WhisperModel(model_size, device=device, compute_type=compute_type)

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def get_audio_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"無法取得音訊時長: {file_path}. 錯誤: {e}")
        return None

def convert_and_extract_segment(input_path, output_path, start_time=None, duration=None):
    """
    將音訊轉為 16kHz 單聲道 WAV，可選擇性擷取特定段落。
    """
    cmd = ["ffmpeg", "-y"]
    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])
    if duration is not None:
        cmd.extend(["-t", str(duration)])
        
    cmd.extend([
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ])
    
    try:
        # Hide output unless it fails
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg 轉換失敗: {e}")
        return False

# Regex for parsing file names
# Date prefix patterns like: 2026-06-27, 2026_06_27, 20260627
DATE_PATTERN = re.compile(r"^(\d{4}[-\-_]?\d{2}[-\-_]?\d{2})[\s,，_-]*(.*)$")

# Part patterns
CHINESE_NUMERALS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
PART_PATTERNS = [
    # Match part/pt/p suffix
    re.compile(r"[\s,，_-]*(?:part|pt|p)[\s_-]*([0-9a-zA-Z一二三四五六七八九十]+)$", re.IGNORECASE),
    # Match parentheses/brackets
    re.compile(r"[\s,，_-]*[\(\[（]([0-9a-zA-Z一二三四五六七八九十]+)[\)\]）]$"),
    # Match trailing number or letter
    re.compile(r"[\s,，_-]*([0-9a-zA-Z一二三四五六七八九十]+)$")
]

def parse_filename(filename):
    """
    解析檔名，回傳 (date, topic, part_str, part_num)
    """
    base_name, _ = os.path.splitext(filename)
    
    # 1. Parse date prefix
    date_match = DATE_PATTERN.match(base_name)
    if date_match:
        date_str = date_match.group(1)
        rest = date_match.group(2)
    else:
        date_str = ""
        rest = base_name
        
    topic = rest.strip()
    part_str = ""
    part_num = 1
    
    # 2. Parse part suffix
    for pattern in PART_PATTERNS:
        match = pattern.search(topic)
        if match:
            part_str = match.group(1)
            # Remove suffix from topic
            topic = topic[:match.start()].strip()
            
            # Map part_str to numeric value for sorting
            if part_str.isdigit():
                part_num = int(part_str)
            elif part_str in CHINESE_NUMERALS:
                part_num = CHINESE_NUMERALS[part_str]
            elif len(part_str) == 1 and part_str.isalpha():
                part_num = ord(part_str.upper())
            else:
                part_num = 999 # Unknown pattern, put at end
            break
            
    # Clean up trailing punctuation in topic
    topic = re.sub(r"[\s,，_-]+$", "", topic)
    return date_str, topic, part_str, part_num

def group_audio_files(file_paths):
    """
    將檔案進行分群排序。回傳 dict: {(date, topic): [file_info, ...]}
    """
    groups = {}
    for path in file_paths:
        filename = os.path.basename(path)
        date_str, topic, part_str, part_num = parse_filename(filename)
        
        # Use (date, topic) as the group key
        group_key = (date_str, topic)
        if group_key not in groups:
            groups[group_key] = []
            
        groups[group_key].append({
            'path': path,
            'filename': filename,
            'date': date_str,
            'topic': topic,
            'part_str': part_str,
            'part_num': part_num
        })
        
    # Sort files within each group by part_num
    for key in groups:
        groups[key].sort(key=lambda x: x['part_num'])
        
    return groups

def run_asr_on_file(model, audio_wav_path, original_filename, part_prefix=""):
    """
    針對單個 WAV 檔案執行 ASR，並回傳字幕項目清單
    """
    print(f"正在分析 {original_filename}...")
    segments, info = model.transcribe(audio_wav_path, language="zh", beam_size=5)
    
    entries = []
    duration = info.duration
    
    with tqdm(total=duration, unit="sec", desc="語音辨識進度") as pbar:
        last_pos = 0
        for segment in segments:
            pbar.update(segment.end - last_pos)
            last_pos = segment.end
            
            text = segment.text.strip()
            if part_prefix:
                text = f"{part_prefix} {text}"
                
            entries.append({
                'start': segment.start,
                'end': segment.end,
                'text': text
            })
            
    return entries, duration

def run_asr_openai(api_key, audio_path, original_filename, prompt=None):
    """
    透過 OpenAI Whisper API 進行語音辨識
    """
    print(f"正在透過 OpenAI API 分析 {original_filename}...")
    
    # 獲取音訊時長
    duration = get_audio_duration(audio_path)
    
    try:
        import requests
    except ImportError:
        print("錯誤：呼叫 OpenAI API 需要 requests 套件。請先執行 'pip install requests' 安裝。")
        sys.exit(1)
        
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    with open(audio_path, "rb") as f:
        files = {
            "file": (os.path.basename(audio_path), f, "audio/wav"),
            "model": (None, "whisper-1"),
            "language": (None, "zh"),
            "response_format": (None, "verbose_json")
        }
        if prompt:
            files["prompt"] = (None, prompt)
        
        try:
            response = requests.post(url, headers=headers, files=files)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            print(f"\nOpenAI API 呼叫失敗: {e}")
            if 'response' in locals() and response.text:
                print(f"錯誤詳情: {response.text}")
            sys.exit(1)
            
    entries = []
    segments = result.get("segments", [])
    
    for segment in segments:
        entries.append({
            'start': segment.get('start', 0.0),
            'end': segment.get('end', 0.0),
            'text': segment.get('text', '').strip()
        })
        
    if not duration:
        duration = result.get("duration", (entries[-1]['end'] if entries else 0.0))
        
    return entries, duration

def process_single_audio(model, input_path, temp_dir, use_openai=False, openai_api_key=None, prompt=None):
    """
    處理單一音訊檔（包括切段邏輯）
    """
    file_size = os.path.getsize(input_path)
    filename = os.path.basename(input_path)
    
    # 檢查是否需要切段 (> 25MB)
    size_mb = file_size / (1024 * 1024)
    print(f"檔案大小: {size_mb:.2f} MB")
    
    # 預先獲取時長
    total_duration = get_audio_duration(input_path)
    if not total_duration:
        print("無法讀取音訊時長，將直接嘗試整檔轉換。")
        # Direct conversion
        wav_path = os.path.join(temp_dir, "temp_full.wav")
        if not convert_and_extract_segment(input_path, wav_path):
            return []
        if use_openai:
            entries, _ = run_asr_openai(openai_api_key, wav_path, filename, prompt=prompt)
        else:
            entries, _ = run_asr_on_file(model, wav_path, filename)
        return entries
        
    if file_size > 25 * 1024 * 1024:
        print(f"檔案大於 25MB，啟動自動切段邏輯（10分鐘/段，5秒重疊）")
        start = 0
        chunk_idx = 0
        all_entries = []
        
        while start < total_duration:
            end = min(start + 600, total_duration)
            duration = end - start
            if duration < 5 and chunk_idx > 0:
                break
                
            chunk_wav = os.path.join(temp_dir, f"chunk_{chunk_idx:03d}.wav")
            print(f"正在預處理切段 {chunk_idx + 1}: {format_timestamp(start)} --> {format_timestamp(end)}")
            
            if convert_and_extract_segment(input_path, chunk_wav, start, duration):
                if use_openai:
                    chunk_entries, _ = run_asr_openai(openai_api_key, chunk_wav, f"{filename} (第 {chunk_idx+1} 段)", prompt=prompt)
                else:
                    chunk_entries, _ = run_asr_on_file(model, chunk_wav, f"{filename} (第 {chunk_idx+1} 段)")
                
                # Shift timestamps for this chunk by 'start' seconds
                for entry in chunk_entries:
                    entry['start'] += start
                    entry['end'] += start
                    all_entries.append(entry)
                    
            start += 595 # 10 minutes - 5 seconds overlap = 595s
            chunk_idx += 1
            
        # Sort all entries chronologically (since overlapping regions might cause minor timestamp overlap)
        all_entries.sort(key=lambda x: x['start'])
        return all_entries
    else:
        # Direct conversion
        wav_path = os.path.join(temp_dir, "temp_full.wav")
        print("正在轉換為 16kHz WAV 格式...")
        if not convert_and_extract_segment(input_path, wav_path):
            return []
        if use_openai:
            entries, _ = run_asr_openai(openai_api_key, wav_path, filename, prompt=prompt)
        else:
            entries, _ = run_asr_on_file(model, wav_path, filename)
        return entries

def save_srt(entries, output_path):
    """
    將字幕清單存成 SRT 格式
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, entry in enumerate(entries, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_timestamp(entry['start'])} --> {format_timestamp(entry['end'])}\n")
            f.write(f"{entry['text']}\n\n")

def main():
    parser = argparse.ArgumentParser(description="課程錄音自動化整理工具 - ASR 部分")
    parser.add_argument("input_path", type=str, help="輸入音訊檔案或資料夾路徑")
    parser.add_argument("--model", type=str, default="base", choices=["tiny", "base", "small"], help="Whisper 本地模型大小")
    parser.add_argument("--domain", type=str, default=None, help="領域（糖尿病/跑者營養等，作為 LLM 提示參考，此處僅供記錄）")
    parser.add_argument("--skip-asr", action="store_true", help="跳過 ASR（Option 1 中此參數會提示將 SRT 檔案交給 Antigravity）")
    parser.add_argument("--asr-only", action="store_true", default=True, help="只執行 ASR（在協同方案中此為預設）")
    parser.add_argument("--openai", action="store_true", help="使用 OpenAI 雲端 Whisper API 進行辨識")
    parser.add_argument("--prompt", type=str, default=None, help="提供給 OpenAI Whisper API 的提示詞（例如核心醫學術語），可大幅提升特定名詞辨識率")
    
    args = parser.parse_args()
    
    # 建立暫存資料夾
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(args.input_path)) if os.path.isfile(args.input_path) else args.input_path, ".temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    
    if args.skip_asr:
        print("跳過 ASR 辨識步驟。")
        print("請直接將現有的 SRT 檔案路徑或內容分享給 Antigravity，我將為您進行 Pass 0 ~ Pass 2B 的 LLM 結構化筆記整理！")
        return

    # Check input path existence
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"錯誤：輸入路徑不存在：{input_path}")
        sys.exit(1)
        
    # Determine files to process
    audio_extensions = (".mp3", ".m4a", ".wav", ".wma", ".flac", ".ogg")
    files_to_process = []
    
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(audio_extensions):
                    files_to_process.append(os.path.join(root, file))
    else:
        if input_path.lower().endswith(audio_extensions):
            files_to_process.append(input_path)
            
    if not files_to_process:
        print("錯誤：找不到任何支援的音訊檔案。")
        sys.exit(1)
        
    # Perform grouping
    groups = group_audio_files(files_to_process)
    
    # Decide processing list based on user confirmation
    groups_to_process = []
    
    # Boundary case: If only 1 file in directory or single file input
    is_single_file_mode = len(files_to_process) == 1
    
    if is_single_file_mode:
        # Single file, no prompting
        key = list(groups.keys())[0]
        groups_to_process.append((key, groups[key], "y"))
    else:
        # Multiple files, group them and prompt
        print(f"\n偵測到 {len(groups)} 個課程/主題群組：")
        print("="*60)
        
        idx = 1
        group_keys = list(groups.keys())
        for key in group_keys:
            date_str, topic = key
            files_in_group = groups[key]
            
            # Estimate total duration
            total_dur = 0
            for f in files_in_group:
                dur = get_audio_duration(f['path'])
                if dur:
                    total_dur += dur
                    
            dur_str = format_timestamp(total_dur)
            date_display = f"[{date_str}] " if date_str else ""
            print(f"群組 {idx}：{date_display}{topic} (共 {len(files_in_group)} 段錄音，總長約 {dur_str})")
            for f in files_in_group:
                part_display = f" - Part {f['part_str']}" if f['part_str'] else ""
                print(f"  └── {f['filename']}{part_display}")
            idx += 1
            print("-"*60)
            
        # If multiple groups, ask all / select / skip
        if len(groups) > 1:
            choice = input("偵測到多個主題群組。請選擇處理模式 (all: 全部合併處理, select: 逐一確認, skip: 全部跳過) [all/select/skip]: ").strip().lower()
            if choice == "all":
                for key in group_keys:
                    groups_to_process.append((key, groups[key], "y"))
            elif choice == "skip":
                print("已取消處理。")
                sys.exit(0)
            else: # select
                for key in group_keys:
                    date_str, topic = key
                    files_in_group = groups[key]
                    date_display = f"[{date_str}] " if date_str else ""
                    g_choice = input(f"是否合併處理群組 '{date_display}{topic}'？ (y: 合併, n: 跳過, split: 各檔案獨立處理) [y/n/split]: ").strip().lower()
                    if g_choice in ("y", "split"):
                        groups_to_process.append((key, groups[key], g_choice))
        else:
            # Single group with multiple files
            key = group_keys[0]
            date_str, topic = key
            date_display = f"[{date_str}] " if date_str else ""
            g_choice = input(f"是否合併處理群組 '{date_display}{topic}'？ (y: 合併, n: 跳過, split: 各檔案獨立處理) [y/n/split]: ").strip().lower()
            if g_choice in ("y", "split"):
                groups_to_process.append((key, groups[key], g_choice))
                
    if not groups_to_process:
        print("沒有選定任何需要處理的檔案。")
        sys.exit(0)
        
    # Load Whisper Model or check OpenAI API Key
    model = None
    openai_api_key = None
    if args.openai:
        # 嘗試讀取本地 .env 檔案
        for dotenv_path in [".env", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]:
            if os.path.exists(dotenv_path):
                with open(dotenv_path, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ[k.strip()] = v.strip().strip("'\"")
                break
                
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            print("錯誤：您選擇了使用 OpenAI API，但未偵測到環境變數 'OPENAI_API_KEY' 或本地 .env 檔案中的設定。")
            print("請先在終端機中設定環境變數，例如：")
            print("  $env:OPENAI_API_KEY=\"您的金鑰\" (PowerShell)")
            print("  set OPENAI_API_KEY=您的金鑰 (CMD)")
            sys.exit(1)
        print("已偵測到 OPENAI_API_KEY，將使用 OpenAI 雲端 Whisper 進行語音辨識。")
    else:
        model = get_whisper_model(args.model)
    
    # Process selected groups
    for key, file_list, mode in groups_to_process:
        date_str, topic = key
        date_prefix = f"{date_str}, " if date_str else ""
        
        # Output directory is the same folder as the first file of the group
        out_dir = os.path.dirname(file_list[0]['path'])
        
        if mode == "y":
            # MERGED MODE
            print(f"\n====== 開始合併處理群組：{topic} ======")
            merged_entries = []
            cumulative_offset = 0
            
            for idx, file_info in enumerate(file_list, 1):
                part_prefix = f"[Part {file_info['part_str']}]" if file_info['part_str'] else f"[Part {idx}]"
                # If only one file in group, do not add [Part X] tag (as per boundary conditions)
                if len(file_list) == 1:
                    part_prefix = ""
                    
                print(f"\n處理分段 {idx}/{len(file_list)}: {file_info['filename']}")
                
                # Transcribe this file
                entries = process_single_audio(
                    model, 
                    file_info['path'], 
                    temp_dir, 
                    use_openai=args.openai, 
                    openai_api_key=openai_api_key,
                    prompt=args.prompt
                )
                
                # Shift timestamps and add to merged list
                for entry in entries:
                    entry['start'] += cumulative_offset
                    entry['end'] += cumulative_offset
                    if part_prefix:
                        # Prefix subtitle text with part identifier
                        entry['text'] = f"{part_prefix} {entry['text']}"
                    merged_entries.append(entry)
                    
                # Get file duration to update offset
                dur = get_audio_duration(file_info['path']) or (entries[-1]['end'] if entries else 0)
                cumulative_offset += dur
                
            # Save merged SRT
            output_name = f"{date_prefix}{topic}.srt"
            output_path = os.path.join(out_dir, output_name)
            save_srt(merged_entries, output_path)
            print(f"\n[成功] 已產出合併字幕檔: {output_path}")
            print("="*60)
            print(f"請在 Antigravity 聊天室中，告訴我此 SRT 檔案的路徑：")
            print(f"[SRT路徑](file:///{output_path.replace(os.sep, '/')})")
            print("我將會讀取此檔案並利用雲端 LLM 為您生成「逐字稿」與「重點整理」筆記！")
            print("="*60)
            
        elif mode == "split":
            # SPLIT MODE
            print(f"\n====== 開始獨立處理群組中的每個檔案：{topic} ======")
            for file_info in file_list:
                print(f"\n獨立處理檔案: {file_info['filename']}")
                entries = process_single_audio(
                    model, 
                    file_info['path'], 
                    temp_dir, 
                    use_openai=args.openai, 
                    openai_api_key=openai_api_key,
                    prompt=args.prompt
                )
                
                # Save individual SRT (without Part X tags, since it's split)
                file_base, _ = os.path.splitext(file_info['filename'])
                output_path = os.path.join(out_dir, f"{file_base}.srt")
                save_srt(entries, output_path)
                print(f"[成功] 已產出單檔字幕: {output_path}")
                print(f"請將字幕路徑提供給 Antigravity：[SRT路徑](file:///{output_path.replace(os.sep, '/')})")

    # Clean up temp files
    try:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    except Exception:
        pass

if __name__ == "__main__":
    main()
