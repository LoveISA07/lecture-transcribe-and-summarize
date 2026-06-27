import re
import os

def parse_time(time_str):
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
    if not match:
        raise ValueError(f"Invalid timestamp format: {time_str}")
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000.0

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def process_srt(file_path, offset=0, part_label=None):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Normalize newlines
    content = content.replace("\r\n", "\n")
    # Split by double newlines to get blocks
    blocks = content.strip().split("\n\n")
    entries = []
    
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            # First line is index, second is timestamp, rest is text
            time_line = lines[1]
            text = "\n".join(lines[2:])
            
            # Match timestamp format
            match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", time_line)
            if match:
                start_sec = parse_time(match.group(1)) + offset
                end_sec = parse_time(match.group(2)) + offset
                
                # Strip existing Part prefix if any
                text = re.sub(r"^\[Part\s+[^\]]+\]", "", text).strip()
                
                if part_label:
                    text = f"[Part {part_label}] {text}"
                    
                entries.append((start_sec, end_sec, text))
    return entries

def main():
    part1_path = r"c:\Users\User\Documents\Antigravity\MP3解析\2026-06-27-跑者營養1.srt"
    part2_path = r"c:\Users\User\Documents\Antigravity\MP3解析\2026-06-27, 跑者營養.srt"
    
    # We rename the current file to back it up just in case
    temp_part2 = r"c:\Users\User\Documents\Antigravity\MP3解析\2026-06-27-跑者營養2.srt"
    if os.path.exists(part2_path) and not os.path.exists(temp_part2):
        os.rename(part2_path, temp_part2)
        part2_path = temp_part2
    elif os.path.exists(temp_part2):
        part2_path = temp_part2
        
    offset = 5938.293625 # Duration of part 1 in seconds
    
    print("Parsing Part 1...")
    entries = process_srt(part1_path, offset=0, part_label="1")
    print(f"Loaded {len(entries)} entries from Part 1.")
    
    print("Parsing Part 2...")
    part2_entries = process_srt(part2_path, offset=offset, part_label="2")
    print(f"Loaded {len(part2_entries)} entries from Part 2.")
    
    entries.extend(part2_entries)
    
    output_path = r"c:\Users\User\Documents\Antigravity\MP3解析\2026-06-27, 跑者營養.srt"
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(entries, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")
            
    print(f"Successfully merged SRTs into {output_path}")

if __name__ == "__main__":
    main()
