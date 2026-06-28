import os
import re
import json
import sys
import argparse

# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

def format_chapter_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}"
    else:
        return f"00:{minutes:02d}"

def parse_srt(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = content.strip().split("\n\n")
    entries = []
    
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            time_line = lines[1]
            text = " ".join(lines[2:])
            
            # Parse timestamps
            match = re.match(r"(\d{2}):(\d{2}):(\d{2}),\d{3} --> (\d{2}):(\d{2}):(\d{2}),\d{3}", time_line)
            if match:
                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                start_sec = h * 3600 + m * 60 + s
                
                eh, em, es = int(match.group(4)), int(match.group(5)), int(match.group(6))
                end_sec = eh * 3600 + em * 60 + es
                
                entries.append({
                    'start': start_sec,
                    'end': end_sec,
                    'text': text
                })
    return entries

def restore_punctuation(text, pipe):
    try:
        # Predict punctuation using BERT token-classification
        res = pipe(text)
        chars = list(text)
        puncs = [""] * len(chars)
        
        for pred in res:
            entity = pred['entity']
            if entity.startswith("S-"):
                punc_mark = entity.split("-")[1]
                idx = pred['start']
                if 0 <= idx < len(puncs):
                    puncs[idx] = punc_mark
                    
        output = []
        for c, p in zip(chars, puncs):
            output.append(c)
            output.append(p)
        return "".join(output)
    except Exception as e:
        print(f"\n警告：標點符號恢復失敗: {e}", file=sys.stderr)
        return text

def clean_base_text(text, oral_tics):
    # 1. Extract Part label if any
    part_match = re.match(r"^\[Part\s+([^\]]+)\]", text)
    part_val = part_match.group(1) if part_match else None
    clean_text = re.sub(r"^\[Part\s+[^\]]+\]", "", text).strip()
    
    # 2. Remove oral tics
    for tic in oral_tics:
        clean_text = clean_text.replace(tic, "")
        
    # 3. Remove all existing punctuation and spaces to feed clean Hanzi to BERT
    clean_text = re.sub(r"[\s，。、？！；：,.;!?：]+", "", clean_text)
    
    return clean_text, part_val

def apply_corrections(text, corrections):
    # Keep original text and append corrected text in parentheses: raw -> raw (correct)
    if not corrections:
        return text
    # Sort corrections by raw string length descending to prevent overlapping replacement issues
    sorted_raws = sorted(corrections.keys(), key=len, reverse=True)
    placeholders = {}
    
    for idx, raw in enumerate(sorted_raws):
        if raw in text:
            ph = f"__CORR_PH_{idx}__"
            text = text.replace(raw, ph)
            correct = corrections[raw]
            placeholders[ph] = f"{raw} ({correct})"
            
    for ph, replaced_text in placeholders.items():
        text = text.replace(ph, replaced_text)
        
    return text

def bold_keywords(text, keywords):
    if not keywords:
        return text
    # Bold keywords using placeholder trick to prevent overlapping matching
    sorted_kws = sorted(keywords, key=len, reverse=True)
    placeholders = {}
    
    for idx, kw in enumerate(sorted_kws):
        if kw in text:
            ph = f"__KW_PH_{idx}__"
            text = text.replace(kw, ph)
            placeholders[ph] = f"**{kw}**"
            
    for ph, bold_text in placeholders.items():
        text = text.replace(ph, bold_text)
        
    return text

def main():
    parser = argparse.ArgumentParser(description="Restore punctuation and format transcript from SRT.")
    parser.add_argument("srt_file", help="Path to the input SRT file.")
    parser.add_argument("--metadata", help="Path to the metadata JSON file. If omitted, will search for <srt_base>_metadata.json or use defaults.")
    parser.add_argument("--output", help="Path to the output markdown file. Defaults to <srt_base>-逐字稿.md")
    
    args = parser.parse_args()
    
    srt_file = os.path.abspath(args.srt_file)
    if not os.path.exists(srt_file):
        print(f"錯誤：找不到 SRT 檔案 '{srt_file}'")
        sys.exit(1)
        
    srt_dir = os.path.dirname(srt_file)
    srt_base = os.path.splitext(os.path.basename(srt_file))[0]
    
    # Resolve metadata file
    metadata_file = None
    if args.metadata:
        metadata_file = os.path.abspath(args.metadata)
    else:
        potential_meta = os.path.join(srt_dir, f"{srt_base}_metadata.json")
        if os.path.exists(potential_meta):
            metadata_file = potential_meta
        else:
            # Fallback to the generic one in the same dir if it exists, or None
            generic_meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lecture_metadata.json")
            # Only use generic_meta if it is not specific to another lecture, but actually it is specific.
            # It's better to default to empty if the specific one doesn't exist.
            metadata_file = None

    # Resolve output file
    if args.output:
        output_file = os.path.abspath(args.output)
    else:
        output_file = os.path.join(srt_dir, f"{srt_base}-逐字稿.md")
        
    # Load metadata
    meta = {
        "chapters": [],
        "corrections": {},
        "keywords": [],
        "oral_tics": ["那個", "就是", "然後", "嗯", "對", "好的", "的那個"]
    }
    
    if metadata_file and os.path.exists(metadata_file):
        print(f"載入詮釋資料 (Metadata): {metadata_file}")
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                loaded_meta = json.load(f)
                meta.update(loaded_meta)
        except Exception as e:
            print(f"警告：讀取 metadata 失敗: {e}，將使用預設值。")
    else:
        print("未偵測到專屬 metadata 檔案，將使用預設設定進行標點還原。")
        
    chapters = meta.get("chapters", [])
    corrections = meta.get("corrections", {})
    keywords = meta.get("keywords", [])
    oral_tics = meta.get("oral_tics", ["那個", "就是", "然後", "嗯", "對", "好的", "的那個"])
    
    # If no chapters defined, create a default one spanning the entire lecture
    if not chapters:
        chapters = [{
            "title": "課程內容",
            "start": 0,
            "end": 999999,
            "part": "1"
        }]
        
    print("正在載入本地端標點符號恢復模型 (BERT)...")
    try:
        from transformers import pipeline
        pipe = pipeline("token-classification", model="p208p2002/zh-wiki-punctuation-restore")
    except Exception as e:
        print(f"錯誤：無法載入 transformers 管道: {e}")
        sys.exit(1)
        
    entries = parse_srt(srt_file)
    print(f"解析原始 SRT 完成，共有 {len(entries)} 條字幕項目。")
    
    cleaned_entries = []
    for entry in entries:
        clean_text, part_val = clean_base_text(entry['text'], oral_tics)
        if clean_text:
            cleaned_entries.append({
                'start': entry['start'],
                'end': entry['end'],
                'text': clean_text,
                'part': part_val
            })
            
    print(f"基礎清理完成，剩餘 {len(cleaned_entries)} 條有效文字項目。開始劃分段落大綱...")
    
    # Pre-group into paragraphs
    paragraphs = []
    current_chapter_idx = -1
    current_para_entries = []
    current_para_len = 0
    
    for entry in cleaned_entries:
        start_sec = entry['start']
        
        # Check chapter transition
        next_chapter_idx = current_chapter_idx
        for c_idx, ch in enumerate(chapters):
            if ch['start'] <= start_sec < ch['end']:
                next_chapter_idx = c_idx
                break
                
        # Flush if chapter changed
        if next_chapter_idx != current_chapter_idx:
            if current_para_entries:
                paragraphs.append({
                    'type': 'text',
                    'text': "".join(current_para_entries)
                })
                current_para_entries = []
                current_para_len = 0
                
            current_chapter_idx = next_chapter_idx
            ch = chapters[current_chapter_idx]
            part_label = entry['part'] or ch.get('part', '1')
            time_display = format_chapter_time(ch['start'])
            paragraphs.append({
                'type': 'header',
                'text': f"## {ch['title']} [Part {part_label}｜{time_display}]"
            })
            
        # Flush if length > 350
        if current_para_len > 350:
            paragraphs.append({
                'type': 'text',
                'text': "".join(current_para_entries)
            })
            current_para_entries = []
            current_para_len = 0
            
        current_para_entries.append(entry['text'])
        current_para_len += len(entry['text'])
        
    if current_para_entries:
        paragraphs.append({
            'type': 'text',
            'text': "".join(current_para_entries)
        })
        
    text_paras_count = sum(1 for p in paragraphs if p['type'] == 'text')
    print(f"劃分完成！共 {len(paragraphs)} 個區塊，其中 {text_paras_count} 個段落需要進行標點符號推論。")
    
    # Process paragraph-by-paragraph with progress logging
    processed_count = 0
    final_output_lines = []
    
    for p in paragraphs:
        if p['type'] == 'header':
            final_output_lines.append(p['text'] + "\n\n")
        else:
            processed_count += 1
            sys.stdout.write(f"\r正在處理段落: {processed_count}/{text_paras_count}...")
            sys.stdout.flush()
            
            # 1. Restore punctuation using BERT
            punctuated_text = restore_punctuation(p['text'], pipe)
            # 2. Apply corrections in "raw(correct)" format
            corrected_text = apply_corrections(punctuated_text, corrections)
            # 3. Bold keywords
            final_text = bold_keywords(corrected_text, keywords)
            final_output_lines.append(final_text + "\n\n")
            
    print("\n推論與校正完成！正在將完整的格式化逐字稿寫入檔案...")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# 課程逐字稿：{srt_base}\n\n")
        f.write(f"> 來源檔案：{os.path.basename(srt_file)}\n\n")
        f.write("".join(final_output_lines))
        
    print(f"成功將帶有標點符號與括號校正的完整格式化逐字稿輸出至: {output_file}")

if __name__ == "__main__":
    main()
