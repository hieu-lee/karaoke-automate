import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message=".*audioread.*")
warnings.filterwarnings('ignore', message=".*noisereduce.*", category=UserWarning)

import whisper
from moviepy.editor import *
from moviepy.config import change_settings
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import math
import subprocess
import torch
import soundfile as sf
import noisereduce as nr
import json
import gc

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 18
VIDEO_SIZE = (1280, 720)
BACKGROUND_COLOR_PIL = (0, 0, 0)
TEXT_COLOR_NORMAL = (255, 255, 255)
TEXT_COLOR_HIGHLIGHT = (255, 255, 0)
FPS = 24
LINE_SPACING = 1.3
WORD_SPACING = 15
MARGIN_X = 50
MARGIN_Y = 50
MAX_SENTENCES_ON_SCREEN = 8

DEMUCS_MODEL = "htdemucs"
RUN_ENHANCEMENT = False
ENHANCED_SUFFIX = "_enhanced"
TRANSCRIPTION_SUFFIX = "_transcription.json"
WHISPER_MODEL_SIZE = "medium"
ENHANCEMENT_CHUNK_SECONDS = 20

try:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    print(f"Font loaded: {FONT_PATH}")
except IOError:
    print(f"Warning: Font not found at {FONT_PATH}. Using default PIL font.")
    try:
        font = ImageFont.load_default()
        print("Using default PIL font.")
    except Exception as e:
        print(f"CRITICAL: Could not load default PIL font. Text rendering will fail. Error: {e}")
        font = None

def separate_vocals(input_file, output_dir, model_name=DEMUCS_MODEL):
    """Separates vocals using Demucs CLI."""
    print(f"\n--- Separating Vocals (Demucs: {model_name}) ---")
    start_time = time.time()
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    demucs_output_base_dir = os.path.join(output_dir)
    final_stem_dir = os.path.join(demucs_output_base_dir, model_name)

    print(f"Target output directory for stems: {final_stem_dir}")
    os.makedirs(os.path.dirname(final_stem_dir), exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    command = [
        "python", "-m", "demucs", "--two-stems", "vocals", "-n", model_name,
        "-o", demucs_output_base_dir, "-d", device,
        "--filename", "{stem}.{ext}", input_file
    ]
    print(f"Executing command: {' '.join(command)}")
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        print("Demucs stdout (first 500 chars):", process.stdout[:500])
        if process.stderr:
             print("Demucs stderr (first 500 chars):", process.stderr[:500])
        print(f"Demucs separation finished in {time.time() - start_time:.2f} seconds.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Demucs separation: {e}")
        print(f"Stderr: {e.stderr}")
        raise RuntimeError("Demucs separation failed.") from e
    except FileNotFoundError:
         print("Error: 'python -m demucs' command not found. Is Demucs installed and in PATH?")
         raise

    vocal_path = os.path.join(final_stem_dir, 'vocals.wav')
    instrumental_path = os.path.join(final_stem_dir, 'no_vocals.wav')

    if not os.path.exists(vocal_path) or not os.path.exists(instrumental_path):
        print(f"Error: Expected output files not found in {final_stem_dir}")
        print("Please check Demucs logs above.")
        raise FileNotFoundError(f"Expected files not found after Demucs run.")

    print(f"Vocal track: {vocal_path}")
    print(f"Instrumental track: {instrumental_path}")
    return vocal_path, instrumental_path

def transcribe_and_save(vocal_path, output_json_path, model_size=WHISPER_MODEL_SIZE):
    """
    Transcribes vocals using Whisper, saves results to JSON, and releases model.
    Returns the path to the JSON file.
    """
    print(f"\n--- Transcribing Vocals & Saving Timestamps (Whisper: {model_size}) ---")
    print(f"Input vocal file: {vocal_path}")
    print(f"Output JSON: {output_json_path}")
    start_time = time.time()
    fp16_enabled = torch.cuda.is_available()

    model = None
    try:
        print(f"Loading Whisper model '{model_size}' (fp16={fp16_enabled})...")
        model = whisper.load_model(model_size)
        print("Model loaded.")

        result = model.transcribe(vocal_path, word_timestamps=True, fp16=fp16_enabled)
        print(f"Transcription finished in {time.time() - start_time:.2f} seconds.")

    except Exception as e:
        print(f"Error during Whisper transcription: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if model is not None:
            print("Releasing Whisper model from memory...")
            del model
            if fp16_enabled:
                print("Clearing CUDA cache...")
                torch.cuda.empty_cache()
            print("Model released.")
        gc.collect()
        print("Garbage collection triggered.")

    sentences = []
    if 'segments' in result and result['segments']:
        for segment in result['segments']:
            sentence_words = []
            if 'words' in segment and segment['words']:
                for word_info in segment['words']:
                    text = word_info.get('word', '').strip()
                    start = word_info.get('start')
                    end = word_info.get('end')
                    if text and start is not None and end is not None and (end - start) > 0.001:
                        sentence_words.append({'text': text, 'start': float(start), 'end': float(end)})

            if sentence_words:
                sentences.append({
                    'words': sentence_words,
                    'start_time': sentence_words[0]['start'],
                    'end_time': sentence_words[-1]['end'],
                    'full_text': " ".join([w['text'] for w in sentence_words])
                })
        sentences.sort(key=lambda x: x['start_time'])
        print(f"Structured into {len(sentences)} sentences.")
    else:
        print("Warning: No segments found in transcription result.")

    try:
        print(f"Saving transcription data to {output_json_path}...")
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(sentences, f, indent=2, ensure_ascii=False)
        print("Transcription data saved.")
        if not os.path.exists(output_json_path):
             raise RuntimeError("JSON file was not created.")
        return output_json_path

    except Exception as e:
        print(f"Error saving transcription to JSON: {e}")
        raise

def enhance_instrumental_chunked(input_audio_path, output_audio_path, chunk_seconds=ENHANCEMENT_CHUNK_SECONDS):
    """
    Enhances instrumental using noisereduce, processing in chunks for memory efficiency.
    """
    print(f"\n--- Enhancing Instrumental Track (Chunked) ---")
    print(f"Input: {input_audio_path}")
    print(f"Output: {output_audio_path}")
    print(f"Chunk size: {chunk_seconds} seconds")
    start_time_enh = time.time()

    try:
        info = sf.info(input_audio_path)
        rate = info.samplerate
        num_frames = info.frames
        num_channels = info.channels
        dtype = info.subtype

        print(f"Audio Info: Rate={rate}, Frames={num_frames}, Channels={num_channels}, Duration={info.duration:.2f}s")

        chunk_size_frames = int(chunk_seconds * rate)
        if chunk_size_frames <= 0:
            print("Warning: Chunk size is zero or negative, processing entire file at once.")
            chunk_size_frames = num_frames

        processed_data_full = np.zeros((num_frames, num_channels) if num_channels > 1 else num_frames, dtype=np.float32)

        total_chunks = math.ceil(num_frames / chunk_size_frames)
        print(f"Processing in {total_chunks} chunks...")

        for i in range(total_chunks):
            start_frame = i * chunk_size_frames
            end_frame = min((i + 1) * chunk_size_frames, num_frames)
            current_chunk_frames = end_frame - start_frame
            print(f"Processing chunk {i+1}/{total_chunks} (Frames {start_frame} to {end_frame})...")

            chunk_start_time = time.time()
            data_chunk = None
            reduced_chunk = None
            try:
                with sf.SoundFile(input_audio_path, 'r') as infile:
                    infile.seek(start_frame)
                    data_chunk = infile.read(frames=current_chunk_frames, dtype='float32', always_2d=True if num_channels > 1 else False)

                if num_channels == 2:
                    print(f"  Processing L/R channels separately for chunk {i+1}...")
                    reduced_chunk_L = nr.reduce_noise(y=data_chunk[:, 0], sr=rate, prop_decrease=0.75)
                    reduced_chunk_R = nr.reduce_noise(y=data_chunk[:, 1], sr=rate, prop_decrease=0.75)
                    min_len = min(len(reduced_chunk_L), len(reduced_chunk_R), current_chunk_frames)
                    reduced_chunk = np.column_stack((reduced_chunk_L[:min_len], reduced_chunk_R[:min_len]))
                    end_frame = start_frame + reduced_chunk.shape[0]

                elif num_channels == 1:
                    reduced_chunk = nr.reduce_noise(y=data_chunk, sr=rate, prop_decrease=0.75)
                    end_frame = start_frame + len(reduced_chunk)
                else:
                    print(f"  Warning: Unsupported number of channels ({num_channels}), skipping reduction for this chunk.")
                    reduced_chunk = data_chunk

                if reduced_chunk.shape[0] > 0:
                    if num_channels > 1:
                         processed_data_full[start_frame:end_frame, :] = reduced_chunk[:current_chunk_frames, :]
                    else:
                         processed_data_full[start_frame:end_frame] = reduced_chunk[:current_chunk_frames]

                print(f"  Chunk {i+1} processed in {time.time() - chunk_start_time:.2f}s")

            finally:
                del data_chunk
                del reduced_chunk
                gc.collect()

        print(f"\nAll chunks processed. Saving final enhanced file to {output_audio_path}...")
        save_subtype = dtype if dtype else None
        sf.write(output_audio_path, processed_data_full, rate, subtype=save_subtype)

        print(f"Chunked enhancement finished in {time.time() - start_time_enh:.2f} seconds.")
        if not os.path.exists(output_audio_path):
            raise RuntimeError("Enhanced file was not created after chunk processing.")
        print(f"Enhanced instrumental saved to: {output_audio_path}")
        return output_audio_path

    except ImportError:
        print("Error: 'noisereduce' or 'soundfile' library not found. Install them.")
        raise
    except FileNotFoundError:
        print(f"Error: Input audio not found at {input_audio_path}")
        raise
    except Exception as e:
        print(f"Error during chunked audio enhancement: {e}")
        import traceback
        traceback.print_exc()
        print("Warning: Enhancement failed. Continuing with the original instrumental track.")
        return input_audio_path
    finally:
        if 'processed_data_full' in locals():
            del processed_data_full
        gc.collect()
        print("Enhancement final cleanup, garbage collection triggered.")


word_size_cache = {}
sentence_width_cache = {}

def get_word_size(word_text, font_obj):
    if not font_obj: return (10 * len(word_text), 15)
    key = (word_text, font_obj.path, font_obj.size)
    if key in word_size_cache: return word_size_cache[key]
    try:
        if hasattr(font_obj, 'getbbox'):
           bbox = font_obj.getbbox(word_text)
           size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        else:
           size = font_obj.getsize(word_text)
        word_size_cache[key] = size
        return size
    except Exception as e:
        print(f"Warning: Could not get size for '{word_text}'. Estimating. Error: {e}")
        fallback_size = (font_obj.size * len(word_text) * 0.6, font_obj.size * 1.1)
        word_size_cache[key] = fallback_size
        return fallback_size

def get_line_height(font_obj):
    if not font_obj: return 20
    if hasattr(font_obj, 'getmetrics'):
        ascent, descent = font_obj.getmetrics()
        height = ascent + descent
    else:
        height = font_obj.size
    return int(height * LINE_SPACING)

def get_sentence_render_width(sentence_words, font_obj):
    if not font_obj: return 500
    sentence_key = tuple(w['text'] for w in sentence_words)
    cache_key = (sentence_key, font_obj.path, font_obj.size)
    if cache_key in sentence_width_cache:
        return sentence_width_cache[cache_key]

    width = 0
    for i, word_info in enumerate(sentence_words):
        word_width, _ = get_word_size(word_info['text'], font_obj)
        width += word_width
        if i < len(sentence_words) - 1:
            width += WORD_SPACING
    sentence_width_cache[cache_key] = width
    return width

_global_sentences_for_frame = []

def make_karaoke_frame_sentence(t):
    """Generates a single frame at time t using _global_sentences_for_frame."""
    global font
    frame_pil = Image.new('RGB', VIDEO_SIZE, BACKGROUND_COLOR_PIL)
    draw = ImageDraw.Draw(frame_pil)

    if not _global_sentences_for_frame or not font:
        return np.array(frame_pil)

    first_incomplete_idx = -1
    for i, sentence in enumerate(_global_sentences_for_frame):
        if t < sentence['end_time']:
            first_incomplete_idx = i
            break
    if first_incomplete_idx == -1:
        first_incomplete_idx = max(0, len(_global_sentences_for_frame) - MAX_SENTENCES_ON_SCREEN)

    start_render_idx = first_incomplete_idx
    end_render_idx = min(len(_global_sentences_for_frame), start_render_idx + MAX_SENTENCES_ON_SCREEN)
    sentences_to_render = _global_sentences_for_frame[start_render_idx:end_render_idx]

    if not sentences_to_render: return np.array(frame_pil)

    line_height = get_line_height(font)
    total_render_height = len(sentences_to_render) * line_height
    current_y = max(MARGIN_Y // 2, (VIDEO_SIZE[1] - total_render_height) // 2)

    for sentence in sentences_to_render:
        sentence_width = get_sentence_render_width(sentence['words'], font)
        if sentence_width >= VIDEO_SIZE[0]:
            current_x = MARGIN_X // 2
        else:
            current_x = (VIDEO_SIZE[0] - sentence_width) // 2

        text_top_offset = 0
        if hasattr(font, 'getbbox'):
            try:
                rep_char = sentence['words'][0]['text'][0] if sentence['words'] else 'A'
                bbox = font.getbbox(rep_char)
                text_top_offset = -bbox[1]
            except Exception: pass
        y_pos_baseline = current_y

        for word_info in sentence['words']:
            word_text = word_info['text']
            word_width, _ = get_word_size(word_text, font)
            color = TEXT_COLOR_HIGHLIGHT if t >= word_info['end'] else TEXT_COLOR_NORMAL
            try:
                draw.text((current_x, y_pos_baseline), word_text, font=font, fill=color, anchor='ls')
            except Exception as e:
                 print(f"Error drawing text '{word_text}': {e}")
            current_x += word_width + WORD_SPACING
        current_y += line_height

    frame_np = np.array(frame_pil)
    return frame_np


def create_karaoke_video_from_json(audio_track_path, transcription_json_path, output_path):
    """
    Creates karaoke video by loading sentences from a JSON file.
    """
    print(f"\n--- Creating Sentence Karaoke Video ---")
    print(f"Using audio: {audio_track_path}")
    print(f"Loading transcription from: {transcription_json_path}")
    print(f"Output video: {output_path}")
    start_time = time.time()

    global _global_sentences_for_frame, word_size_cache, sentence_width_cache, font
    word_size_cache = {}
    sentence_width_cache = {}
    _global_sentences_for_frame = []

    try:
        with open(transcription_json_path, 'r', encoding='utf-8') as f:
            loaded_sentences = json.load(f)
        if not isinstance(loaded_sentences, list):
             raise ValueError("Transcription JSON root should be a list of sentences.")
        _global_sentences_for_frame = loaded_sentences
        print(f"Loaded {len(_global_sentences_for_frame)} sentences from JSON.")
        if not _global_sentences_for_frame:
            print("Warning: Transcription file contained no sentences.")

    except FileNotFoundError:
        print(f"Error: Transcription file not found at {transcription_json_path}")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {transcription_json_path}. Invalid format? Error: {e}")
        return
    except Exception as e:
        print(f"Error loading or processing transcription JSON: {e}")
        return

    audio = None
    video_clip = None
    try:
        print("Loading audio...")
        audio = AudioFileClip(audio_track_path)
        duration = audio.duration
        if _global_sentences_for_frame:
             last_time = _global_sentences_for_frame[-1]['end_time']
             duration = max(audio.duration, last_time + 1.5)

        print(f"Audio loaded. Effective Duration: {duration:.2f} seconds.")

        if font:
            print("Pre-calculating text rendering sizes...")
            unique_words = set(w['text'] for s in _global_sentences_for_frame for w in s['words'])
            for text in unique_words: get_word_size(text, font)
            print(f"Calculated sizes for {len(unique_words)} unique words.")
            for sentence in _global_sentences_for_frame: get_sentence_render_width(sentence['words'], font)
            print(f"Calculated widths for {len(_global_sentences_for_frame)} sentences.")
        else:
            print("Skipping text size pre-calculation as font failed to load.")


        print("Generating video frames dynamically...")
        num_threads = max(1, os.cpu_count() // 2)
        print(f"Using {num_threads} threads for video writing.")

        video_clip = VideoClip(make_frame=make_karaoke_frame_sentence, duration=duration)
        video_clip = video_clip.set_audio(audio).set_fps(FPS)


        print(f"Writing video file to {output_path}...")
        video_clip.write_videofile(output_path,
                                   codec='libx264',
                                   audio_codec='aac',
                                   threads=num_threads,
                                   preset='medium',
                                   logger='bar',
                                   ffmpeg_params=["-pix_fmt", "yuv420p"])

        print(f"\nVideo creation finished in {time.time() - start_time:.2f} seconds.")

    except Exception as e:
        import traceback
        print(f"\nError during video creation: {e}")
        traceback.print_exc()
    finally:
        print("Cleaning up video resources...")
        if audio: audio.close()
        if video_clip: video_clip.close()
        _global_sentences_for_frame = []
        word_size_cache = {}
        sentence_width_cache = {}
        gc.collect()
        print("Video cleanup complete.")

def main():
    input_file = "/content/input.mp3"
    output_dir = "/content/output"

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'")
        return

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    run_separation = True
    vocal_path = ""
    instrumental_path = ""
    final_stem_dir = os.path.join(output_dir, DEMUCS_MODEL)
    expected_vocal_path = os.path.join(final_stem_dir, 'vocals.wav')
    expected_instrumental_path = os.path.join(final_stem_dir, 'no_vocals.wav')

    if run_separation:
        try:
            vocal_path, instrumental_path = separate_vocals(input_file, output_dir, DEMUCS_MODEL)
        except Exception as e:
            print(f"Vocal separation failed: {e}")
            return
    else:
        print("\n--- Skipping Vocal Separation (Checking for Existing Files) ---")
        if os.path.exists(expected_vocal_path) and os.path.exists(expected_instrumental_path):
            vocal_path = expected_vocal_path
            instrumental_path = expected_instrumental_path
            print(f"Using existing files:\n - Vocal: {vocal_path}\n - Instrumental: {instrumental_path}")
        else:
            print(f"Error: Pre-separated files not found at expected paths.")
            return

    transcription_json_path = os.path.join(output_dir, f"{base_name}{TRANSCRIPTION_SUFFIX}")
    run_transcription = False
    if run_transcription:
        try:
            transcription_json_path_returned = transcribe_and_save(vocal_path, transcription_json_path, WHISPER_MODEL_SIZE)
            if not os.path.exists(transcription_json_path_returned) or transcription_json_path_returned != transcription_json_path:
                 print(f"Error: Transcription JSON file missing post-run: {transcription_json_path}")
                 return
            print(f"Transcription data saved to {transcription_json_path}")
        except Exception as e:
            print(f"Transcription failed: {e}")
            return
    else:
        print(f"\n--- Skipping Transcription (Checking for JSON File) ---")
        if not os.path.exists(transcription_json_path):
            print(f"Error: Transcription JSON file not found: {transcription_json_path}")
            return
        else:
             print(f"Using existing transcription file: {transcription_json_path}")

    final_instrumental_path = instrumental_path
    if RUN_ENHANCEMENT:
        instr_dir = os.path.dirname(instrumental_path)
        instr_filename = os.path.basename(instrumental_path)
        instr_base, instr_ext = os.path.splitext(instr_filename)
        enhanced_instrumental_path = os.path.join(instr_dir, f"{instr_base}{ENHANCED_SUFFIX}{instr_ext}")
        try:
            final_instrumental_path = enhance_instrumental_chunked(instrumental_path, enhanced_instrumental_path)
        except Exception as e:
            print(f"Audio enhancement step failed: {e}. Video will use original instrumental.")
            final_instrumental_path = instrumental_path
    else:
        print("\n--- Skipping Audio Enhancement ---")


    output_video_filename = f"{base_name}_karaoke_sentences_{DEMUCS_MODEL}"
    if RUN_ENHANCEMENT and final_instrumental_path != instrumental_path and ENHANCED_SUFFIX in final_instrumental_path:
        output_video_filename += ENHANCED_SUFFIX
    output_video_path = os.path.join(output_dir, f"{output_video_filename}.mp4")

    try:
        create_karaoke_video_from_json(final_instrumental_path,
                                        transcription_json_path,
                                        output_video_path)
        print(f"\nKaraoke video creation process completed.")
        if os.path.exists(output_video_path):
             print(f"Output video saved to: {output_video_path}")
        else:
             print(f"Warning: Output video file was not found at {output_video_path} after processing.")
    except Exception as e:
        print(f"Video creation failed in main block: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    input_path = "/content/input.mp3"
    if not os.path.exists(input_path):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!! Error: Input file '{input_path}' not found! !!!")
        print("!!! Please upload your input audio file first.    !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        gc.collect()
        main()
        gc.collect()
        print("\n--- Script Finished ---")