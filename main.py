import os
import warnings
import whisper
from moviepy.editor import *
# from moviepy.config import change_settings # Not used currently, can remove if not needed
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import math
import subprocess
import torch
import soundfile as sf
import noisereduce as nr
import json # For saving/loading transcription
import gc   # For garbage collection
import argparse # For command-line arguments
import sys # To check arguments

# Suppress TensorFlow INFO/DEBUG messages (1=INFO, 2=WARNING, 3=ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Filter specific warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message=".*audioread.*")
warnings.filterwarnings('ignore', message=".*PySoundFile failed. Trying audioread instead.*") # Add this specific one
warnings.filterwarnings('ignore', message=".*noisereduce.*", category=UserWarning)


# --- Configuration ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" # Ensure this font exists or change path
FONT_SIZE = 18
VIDEO_SIZE = (1280, 720)
BACKGROUND_COLOR_PIL = (0, 0, 0)
TEXT_COLOR_NORMAL = (255, 255, 255)
TEXT_COLOR_HIGHLIGHT = (255, 255, 0)
FPS = 24
LINE_SPACING = 1.3 # Multiplier for calculated line height
WORD_SPACING = 15 # Pixels between words
MARGIN_X = 50 # Left/right margin for text block
MARGIN_Y = 50 # Top/bottom margin for text block
MAX_SENTENCES_ON_SCREEN = 8
PROGRESSIVE_HIGHLIGHT = True # Highlight words character by character

DEMUCS_MODEL = "htdemucs" # Demucs model for separation
RUN_SEPARATION = True # Set False to skip Demucs if stems exist
RUN_ENHANCEMENT = False # Set True to run noise reduction on instrumental
RUN_TRANSCRIPTION = True # Set False to skip Whisper if JSON exists

ENHANCED_SUFFIX = "_enhanced"
TRANSCRIPTION_SUFFIX = "_transcription.json"
WHISPER_MODEL_SIZE = "medium" # tiny, base, small, medium, large (affects VRAM/RAM usage and quality)
ENHANCEMENT_CHUNK_SECONDS = 20 # Process audio enhancement in chunks (seconds)
VIDEO_OUTPUT_PRESET = 'medium' # FFMPEG preset ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow') - faster uses less CPU/Mem but lower quality/larger file
VIDEO_THREADS_RATIO = 0.5 # Ratio of CPU cores to use for video encoding (e.g., 0.5 = half)
# --- End Configuration ---

# --- Font Loading ---
try:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    print(f"Font loaded: {FONT_PATH}")
except IOError:
    print(f"Warning: Font not found at {FONT_PATH}. Trying default PIL font.")
    try:
        font = ImageFont.load_default()
        print("Using default PIL font.")
    except Exception as e:
        print(f"CRITICAL: Could not load any font. Text rendering will fail. Error: {e}")
        font = None # Ensure font is None if loading fails completely

# --- Demucs Function ---
def separate_vocals(input_file, output_dir, model_name=DEMUCS_MODEL):
    """Separates vocals using Demucs CLI."""
    print(f"\n--- Separating Vocals (Demucs: {model_name}) ---")
    start_time = time.time()
    # Use the output_dir directly for demucs output base
    demucs_output_base_dir = output_dir
    final_stem_dir = os.path.join(demucs_output_base_dir, model_name)

    print(f"Target output directory for stems: {final_stem_dir}")
    # Demucs creates the model_name subdir automatically, ensure base output_dir exists
    os.makedirs(demucs_output_base_dir, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Command structure changed slightly in newer demucs: output dir via -o, name structure via --filename
    command = [
        "python", "-m", "demucs", "--two-stems", "vocals", "-n", model_name,
        "-o", demucs_output_base_dir, # Specify base output directory
        "-d", device,
        "--filename", "{model}/{stem}.{ext}", # Demucs will create the 'model_name' subdir
        input_file
    ]
    print(f"Executing command: {' '.join(command)}")
    try:
        # Use Popen for potentially better handling of large outputs if needed, but run is simpler
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        # Limit printing stdout/stderr if it's too verbose
        print("Demucs stdout (first 500 chars):\n", process.stdout[:500])
        if process.stderr:
             print("Demucs stderr (first 500 chars):\n", process.stderr[:500])
        print(f"Demucs separation finished in {time.time() - start_time:.2f} seconds.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Demucs separation (Return Code: {e.returncode}):")
        print(f"Stderr:\n{e.stderr}")
        raise RuntimeError("Demucs separation failed.") from e
    except FileNotFoundError:
         print("Error: 'python -m demucs' command not found. Is Demucs installed and in your PATH?")
         raise

    vocal_path = os.path.join(final_stem_dir, 'vocals.wav')
    instrumental_path = os.path.join(final_stem_dir, 'no_vocals.wav')

    if not os.path.exists(vocal_path) or not os.path.exists(instrumental_path):
        print(f"Error: Expected output files not found in {final_stem_dir}")
        print("Please check Demucs logs above. Files expected:")
        print(f" - {vocal_path}")
        print(f" - {instrumental_path}")
        raise FileNotFoundError(f"Expected files not found after Demucs run.")

    print(f"Vocal track: {vocal_path}")
    print(f"Instrumental track: {instrumental_path}")
    return vocal_path, instrumental_path

# --- Transcription Function ---
def transcribe_and_save(vocal_path, output_json_path, model_size=WHISPER_MODEL_SIZE):
    """
    Transcribes vocals using Whisper, saves results to JSON, and releases model.
    Returns the path to the JSON file.
    """
    print(f"\n--- Transcribing Vocals & Saving Timestamps (Whisper: {model_size}) ---")
    print(f"Input vocal file: {vocal_path}")
    print(f"Output JSON: {output_json_path}")
    start_time = time.time()
    fp16_enabled = torch.cuda.is_available() # Use FP16 if CUDA is available

    model = None # Ensure model variable exists for finally block
    try:
        print(f"Loading Whisper model '{model_size}' (fp16={fp16_enabled})...")
        model = whisper.load_model(model_size)
        print("Model loaded.")

        print("Starting transcription...")
        result = model.transcribe(vocal_path, word_timestamps=True, fp16=fp16_enabled)
        print(f"Transcription finished in {time.time() - start_time:.2f} seconds.")

    except Exception as e:
        print(f"Error during Whisper transcription: {e}")
        import traceback
        traceback.print_exc()
        raise # Re-raise the exception to stop the process
    finally:
        # --- CRITICAL MEMORY RELEASE ---
        if model is not None:
            print("Releasing Whisper model from memory...")
            del model # Remove reference to the model object
            if fp16_enabled:
                print("Clearing CUDA cache...")
                torch.cuda.empty_cache() # Clear GPU memory if CUDA was used
            print("Model released.")
        gc.collect() # Explicitly trigger garbage collection
        print("Garbage collection triggered.")
        # --- END MEMORY RELEASE ---

    # --- Process and Structure Results ---
    sentences = []
    if 'segments' in result and result['segments']:
        for segment in result['segments']:
            sentence_words = []
            # Check if 'words' exists and is not empty
            if 'words' in segment and segment['words']:
                for word_info in segment['words']:
                    # Sanitize word_info before accessing keys
                    text = word_info.get('word', '').strip()
                    start = word_info.get('start')
                    end = word_info.get('end')
                    # Ensure necessary fields are present and valid
                    if text and start is not None and end is not None and isinstance(start, (int, float)) and isinstance(end, (int, float)) and (end - start) > 0.001:
                        sentence_words.append({'text': text, 'start': float(start), 'end': float(end)})
                    # else:
                    #     print(f"Debug: Skipping invalid word data: {word_info}") # Optional debug line

            if sentence_words:
                # Ensure start/end times are derived correctly from valid words
                sentences.append({
                    'words': sentence_words,
                    'start_time': sentence_words[0]['start'],
                    'end_time': sentence_words[-1]['end'],
                    'full_text': " ".join([w['text'] for w in sentence_words])
                })

        # Ensure sentences are sorted by start time, just in case segments weren't ordered
        sentences.sort(key=lambda x: x['start_time'])
        print(f"Structured into {len(sentences)} sentences.")
    else:
        print("Warning: No segments or words found in transcription result. JSON will be empty.")

    # --- Save to JSON ---
    try:
        print(f"Saving transcription data to {output_json_path}...")
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(sentences, f, indent=2, ensure_ascii=False) # Use indent for readability
        print("Transcription data saved.")
        if not os.path.exists(output_json_path):
             raise RuntimeError("JSON file was not created.")
        return output_json_path # Return the path to the created file

    except Exception as e:
        print(f"Error saving transcription to JSON: {e}")
        raise # Stop if saving fails

# --- Audio Enhancement Function (Chunked Processing) ---
def enhance_instrumental_chunked(input_audio_path, output_audio_path, chunk_seconds=ENHANCEMENT_CHUNK_SECONDS):
    """
    Enhances instrumental using noisereduce, processing in chunks for memory efficiency.
    """
    print(f"\n--- Enhancing Instrumental Track (Chunked) ---")
    print(f"Input: {input_audio_path}")
    print(f"Output: {output_audio_path}")
    print(f"Chunk size: {chunk_seconds} seconds")
    start_time_enh = time.time()

    processed_data_full = None # Initialize outside try

    try:
        # Get audio info without loading data
        info = sf.info(input_audio_path)
        rate = info.samplerate
        num_frames = info.frames
        num_channels = info.channels
        dtype = info.subtype # Get data type for output consistency if possible

        print(f"Audio Info: Rate={rate}, Frames={num_frames}, Channels={num_channels}, Duration={info.duration:.2f}s")

        if num_channels not in [1, 2]:
             print(f"Warning: Unsupported number of channels ({num_channels}). Skipping enhancement.")
             return input_audio_path # Return original path if channels unsupported

        # Calculate chunk size in frames
        chunk_size_frames = int(chunk_seconds * rate)
        if chunk_size_frames <= 0:
            print("Warning: Chunk size is zero or negative, processing entire file at once.")
            chunk_size_frames = num_frames

        # Allocate output array (use float32 for processing, convert back later if needed)
        # Determine shape based on channels AFTER checking channel count
        processed_data_shape = (num_frames, num_channels) if num_channels > 1 else (num_frames,)
        processed_data_full = np.zeros(processed_data_shape, dtype=np.float32)

        total_chunks = math.ceil(num_frames / chunk_size_frames)
        print(f"Processing in {total_chunks} chunks...")

        # --- Process Chunks ---
        with sf.SoundFile(input_audio_path, 'r') as infile:
            for i in range(total_chunks):
                start_frame = i * chunk_size_frames
                frames_to_read = min(chunk_size_frames, num_frames - start_frame)
                print(f"Processing chunk {i+1}/{total_chunks} (Frames {start_frame} to {start_frame + frames_to_read})...")

                # Load only the current chunk
                chunk_start_time = time.time()
                data_chunk = None # Ensure defined for finally
                reduced_chunk = None

                try:
                    infile.seek(start_frame)
                    # Read as float32 for noisereduce
                    data_chunk = infile.read(frames=frames_to_read, dtype='float32', always_2d=(num_channels > 1))

                    if data_chunk.shape[0] == 0: # Skip empty chunks (shouldn't happen with correct logic)
                        print(f"  Skipping empty chunk {i+1}.")
                        continue

                    # --- Apply Noise Reduction ---
                    if num_channels == 2:
                        # Process channels separately to potentially save memory vs processing interleaved
                        print(f"  Processing L/R channels separately for chunk {i+1}...")
                        reduced_chunk_L = nr.reduce_noise(y=data_chunk[:, 0], sr=rate, prop_decrease=0.75)
                        reduced_chunk_R = nr.reduce_noise(y=data_chunk[:, 1], sr=rate, prop_decrease=0.75)
                        # Combine back, ensuring length matches original chunk
                        current_chunk_len = data_chunk.shape[0]
                        reduced_chunk = np.column_stack((reduced_chunk_L[:current_chunk_len], reduced_chunk_R[:current_chunk_len]))
                    else: # Mono
                        reduced_chunk = nr.reduce_noise(y=data_chunk, sr=rate, prop_decrease=0.75)
                        # Ensure length matches original chunk
                        current_chunk_len = len(data_chunk)
                        reduced_chunk = reduced_chunk[:current_chunk_len]

                    # --- Place processed chunk into the full output array ---
                    end_frame = start_frame + reduced_chunk.shape[0] # Actual end frame based on reduced chunk size
                    if num_channels > 1:
                         processed_data_full[start_frame:end_frame, :] = reduced_chunk
                    else:
                         processed_data_full[start_frame:end_frame] = reduced_chunk

                    print(f"  Chunk {i+1} processed in {time.time() - chunk_start_time:.2f}s")

                finally:
                    # Explicitly delete potentially large chunk data
                    del data_chunk
                    del reduced_chunk
                    if num_channels == 2 and 'reduced_chunk_L' in locals():
                        del reduced_chunk_L
                        del reduced_chunk_R
                    gc.collect() # Collect garbage after each chunk

        # --- Save the final combined audio ---
        print(f"\nAll chunks processed. Saving final enhanced file to {output_audio_path}...")
        # Try to save with the original subtype if known, otherwise let soundfile choose default for float32
        save_subtype = dtype if dtype and 'float' not in dtype.lower() else None # Use original unless it was float
        sf.write(output_audio_path, processed_data_full, rate, subtype=save_subtype)

        print(f"Chunked enhancement finished in {time.time() - start_time_enh:.2f} seconds.")
        if not os.path.exists(output_audio_path):
            raise RuntimeError("Enhanced file was not created after chunk processing.")
        print(f"Enhanced instrumental saved to: {output_audio_path}")
        return output_audio_path

    except ImportError:
        print("Error: 'noisereduce' or 'soundfile' library not found. Please install them (pip install noisereduce soundfile).")
        raise
    except FileNotFoundError:
        print(f"Error: Input audio not found at {input_audio_path}")
        raise
    except Exception as e:
        print(f"Error during chunked audio enhancement: {e}")
        import traceback
        traceback.print_exc()
        print("Warning: Enhancement failed. Continuing with the original instrumental track.")
        return input_audio_path # Return original on failure
    finally:
        # Clean up the potentially large full array
        if processed_data_full is not None:
            del processed_data_full
        gc.collect()
        print("Enhancement final cleanup performed.")


# --- Helper Functions (Text Rendering - Optimized Caching) ---
word_size_cache = {}
sentence_width_cache = {}

def get_word_size(word_text, font_obj):
    """Gets the rendered size (width, height) of a word using the font, with caching."""
    if not font_obj: return (10 * len(word_text), 15) # Basic fallback
    key = (word_text, font_obj.path, font_obj.size)
    if key in word_size_cache: return word_size_cache[key]

    try:
        # Use getbbox for more accurate sizing if available (Pillow >= 8.0.0)
        # bbox = (left, top, right, bottom) relative to anchor point (0,0)
        # For text size, we want (right - left, bottom - top)
        bbox = font_obj.getbbox(word_text)
        size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except AttributeError: # Fallback for older Pillow or unexpected issues
        try:
            size = font_obj.getsize(word_text) # Deprecated but works as fallback
        except Exception as e_size:
            print(f"Warning: Could not get size for '{word_text}' using getbbox or getsize. Estimating. Error: {e_size}")
            # Estimate based on font size and length
            size = (int(font_obj.size * len(word_text) * 0.6), int(font_obj.size * 1.2))

    word_size_cache[key] = size
    return size

def get_line_height(font_obj):
    """Calculates the line height based on font metrics or size."""
    if not font_obj: return 20 # Basic fallback
    try:
        # getmetrics provides ascent/descent, good for line spacing
        ascent, descent = font_obj.getmetrics()
        height = ascent + descent
    except AttributeError:
        # Fallback using font size if getmetrics is not available
        height = font_obj.size
    # Apply spacing multiplier
    return int(height * LINE_SPACING)

def get_sentence_render_width(sentence_words, font_obj):
    """Calculates the total rendered width of a sentence, including word spacing, with caching."""
    if not font_obj or not sentence_words: return 0 # Basic fallback or empty sentence
    # Create a tuple of words as part of the cache key
    sentence_key = tuple(w['text'] for w in sentence_words)
    cache_key = (sentence_key, font_obj.path, font_obj.size)
    if cache_key in sentence_width_cache:
        return sentence_width_cache[cache_key]

    width = 0
    for i, word_info in enumerate(sentence_words):
        word_width, _ = get_word_size(word_info['text'], font_obj) # Use cached size
        width += word_width
        if i < len(sentence_words) - 1:
            width += WORD_SPACING # Add spacing between words

    sentence_width_cache[cache_key] = width
    return width

# --- Karaoke Frame Generation ---
# Global variable to hold sentences - avoids passing large data structures repeatedly
_global_sentences_for_frame = []

def make_karaoke_frame_sentence(t):
    """Generates a single video frame at time 't' with word highlighting."""
    global font # Access the globally loaded font

    # Create a blank frame
    frame_pil = Image.new('RGB', VIDEO_SIZE, BACKGROUND_COLOR_PIL)
    draw = ImageDraw.Draw(frame_pil)

    # If no sentences or font loaded, return blank frame
    if not _global_sentences_for_frame or not font:
        return np.array(frame_pil)

    # --- Determine which sentences to display ---
    # Find the index of the first sentence that hasn't finished yet
    first_incomplete_idx = -1
    for i, sentence in enumerate(_global_sentences_for_frame):
        if t < sentence['end_time']:
            first_incomplete_idx = i
            break

    # If all sentences are finished, show the last few
    if first_incomplete_idx == -1:
        first_incomplete_idx = max(0, len(_global_sentences_for_frame) - MAX_SENTENCES_ON_SCREEN)

    # Determine the slice of sentences to render based on the current one
    start_render_idx = first_incomplete_idx
    end_render_idx = min(len(_global_sentences_for_frame), start_render_idx + MAX_SENTENCES_ON_SCREEN)
    sentences_to_render = _global_sentences_for_frame[start_render_idx:end_render_idx]

    if not sentences_to_render: return np.array(frame_pil) # Should not happen if logic is correct

    # --- Calculate Layout ---
    line_height = get_line_height(font)
    total_render_height = len(sentences_to_render) * line_height
    # Center the block vertically, ensuring it stays within margins
    start_y_baseline = max(MARGIN_Y // 2, (VIDEO_SIZE[1] - total_render_height) // 2)
    # Adjust slightly so the first line's text top is roughly at the calculated start position
    try:
        rep_char = 'A' # Use a representative char for ascent calculation
        bbox_rep = font.getbbox(rep_char, anchor='ls') # Baseline-left anchor
        text_top_offset_from_baseline = bbox_rep[1] # Usually negative (ascent)
        start_y_baseline -= text_top_offset_from_baseline # Shift baseline down so top aligns better
    except Exception:
        start_y_baseline += int(font.size * 0.1) # Small estimated adjustment if bbox fails


    current_y_baseline = start_y_baseline

    # --- Render Each Sentence ---
    for sentence in sentences_to_render:
        sentence_width = get_sentence_render_width(sentence['words'], font)
        # Center horizontally or align left if too wide
        if sentence_width >= VIDEO_SIZE[0] - MARGIN_X:
            current_x = MARGIN_X // 2 # Align left with margin
        else:
            current_x = (VIDEO_SIZE[0] - sentence_width) // 2 # Center align

        # --- Render Words in the Sentence ---
        for word_info in sentence['words']:
            word_text = word_info['text']
            word_start = word_info['start']
            word_end = word_info['end']
            word_width, word_height = get_word_size(word_text, font) # Use cached size

            # --- Determine Highlight State ---
            is_fully_highlighted = t >= word_end
            highlight_progress = 0.0
            if PROGRESSIVE_HIGHLIGHT:
                if is_fully_highlighted:
                    highlight_progress = 1.0
                elif t > word_start:
                    word_duration = word_end - word_start
                    if word_duration > 0.01: # Avoid division by zero/instability
                        highlight_progress = max(0.0, min(1.0, (t - word_start) / word_duration))
                    # else: highlight_progress remains 0.0 until t >= word_end

            # --- Draw Word ---
            try:
                # Draw base word (normal color) - using baseline anchor ('ls' = left-baseline)
                draw.text((current_x, current_y_baseline), word_text, font=font, fill=TEXT_COLOR_NORMAL, anchor='ls')

                # Draw highlighted part (if any)
                if PROGRESSIVE_HIGHLIGHT and highlight_progress > 0:
                    highlight_width = int(word_width * highlight_progress)
                    if highlight_width > 0:
                        # Use bounding box to accurately determine position and height for pasting
                        try:
                             bbox = font.getbbox(word_text, anchor='ls') # Relative to (current_x, current_y_baseline)
                             word_visual_height = bbox[3] - bbox[1]
                             word_visual_top_offset = bbox[1] # Offset from baseline UP to visual top (negative)

                             if word_width > 0 and word_visual_height > 0:
                                # Create a temporary RGBA image for the highlighted text
                                temp_img = Image.new('RGBA', (word_width, word_visual_height), (0, 0, 0, 0))
                                temp_draw = ImageDraw.Draw(temp_img)
                                # Draw highlighted text onto temp image, aligning baseline
                                temp_draw.text((0, -word_visual_top_offset), word_text, font=font, fill=TEXT_COLOR_HIGHLIGHT, anchor='ls')

                                # Crop the portion to highlight
                                highlight_img = temp_img.crop((0, 0, highlight_width, word_visual_height))

                                # Paste the cropped highlight onto the main frame
                                paste_x = current_x
                                paste_y = current_y_baseline + word_visual_top_offset # Calculate visual top edge
                                frame_pil.paste(highlight_img, (paste_x, paste_y), highlight_img) # Use alpha mask

                                # Explicitly delete temp PIL objects
                                del temp_img, temp_draw, highlight_img

                        except Exception as e_render:
                           # Fallback: If complex progressive rendering fails, draw full highlight if needed
                           print(f"Warning: Progressive render failed for '{word_text}'. {e_render}. Falling back.")
                           if is_fully_highlighted: # Only draw full if time exceeds end
                               draw.text((current_x, current_y_baseline), word_text, font=font, fill=TEXT_COLOR_HIGHLIGHT, anchor='ls')

                elif not PROGRESSIVE_HIGHLIGHT and is_fully_highlighted:
                    # Non-progressive: highlight whole word at once when t passes word_end
                    draw.text((current_x, current_y_baseline), word_text, font=font, fill=TEXT_COLOR_HIGHLIGHT, anchor='ls')

            except Exception as e_draw:
                 print(f"Error drawing text '{word_text}' at ({current_x}, {current_y_baseline}): {e_draw}")

            # Move x position for the next word
            current_x += word_width + WORD_SPACING

        # Move y position for the next line's baseline
        current_y_baseline += line_height

    # Return frame as numpy array for MoviePy
    frame_np = np.array(frame_pil)
    # Clean up frame-specific PIL objects
    del draw
    del frame_pil
    # gc.collect() # Optional: Force GC per frame if memory is extremely tight, but likely slows down rendering significantly
    return frame_np


# --- Video Creation Function ---
def create_karaoke_video_from_json(audio_track_path, transcription_json_path, output_path):
    """Creates the karaoke video using audio and the pre-processed transcription JSON."""
    print(f"\n--- Creating Sentence Karaoke Video ---")
    print(f"Using audio: {audio_track_path}")
    print(f"Loading transcription from: {transcription_json_path}")
    print(f"Output video: {output_path}")
    start_time = time.time()

    global _global_sentences_for_frame, word_size_cache, sentence_width_cache, font
    word_size_cache = {} # Reset caches for new video
    sentence_width_cache = {}
    _global_sentences_for_frame = [] # Clear previous sentences

    # --- Load Sentences from JSON ---
    try:
        with open(transcription_json_path, 'r', encoding='utf-8') as f:
            loaded_sentences = json.load(f)
        if not isinstance(loaded_sentences, list):
             raise ValueError("Transcription JSON root must be a list of sentence objects.")
        _global_sentences_for_frame = loaded_sentences # Set the global variable for make_karaoke_frame_sentence
        print(f"Loaded {len(_global_sentences_for_frame)} sentences from JSON.")
        if not _global_sentences_for_frame:
            print("Warning: Transcription file contained no sentences. Video will have audio but no text.")
            # Decide whether to stop or create an empty video
            # return # Option: Stop if no sentences

    except FileNotFoundError:
        print(f"Error: Transcription file not found at {transcription_json_path}")
        raise # Cannot proceed without transcription
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {transcription_json_path}. Invalid format? Error: {e}")
        raise
    except Exception as e:
        print(f"Error loading or processing transcription JSON: {e}")
        raise

    # --- Prepare Video Generation ---
    audio = None
    video_clip = None
    try:
        print("Loading audio...")
        audio = AudioFileClip(audio_track_path)
        # Determine duration: use audio duration or extend slightly past the last word
        duration = audio.duration
        if _global_sentences_for_frame:
             last_word_end_time = _global_sentences_for_frame[-1]['end_time']
             # Add a small buffer (e.g., 1.5 seconds) after the last word ends
             duration = max(audio.duration, last_word_end_time + 1.5)

        print(f"Audio loaded. Effective Video Duration: {duration:.2f} seconds.")

        # Pre-calculate text rendering sizes if font is available
        if font and _global_sentences_for_frame:
            print("Pre-calculating text rendering sizes (this may take a moment)...")
            unique_words = set(w['text'] for s in _global_sentences_for_frame for w in s['words'])
            for text in unique_words: get_word_size(text, font)
            print(f"Calculated sizes for {len(unique_words)} unique words.")
            # Pre-calculate full sentence widths as well
            for sentence in _global_sentences_for_frame: get_sentence_render_width(sentence['words'], font)
            print(f"Calculated widths for {len(_global_sentences_for_frame)} sentences.")
        elif not font:
            print("Skipping text size pre-calculation as font failed to load.")

        # --- Generate Video ---
        print("Generating video frames dynamically...")
        # Calculate number of threads based on CPU cores and ratio
        num_threads = max(1, int(os.cpu_count() * VIDEO_THREADS_RATIO))
        print(f"Using {num_threads} threads and '{VIDEO_OUTPUT_PRESET}' preset for video writing.")

        # Create the video clip using the frame generation function
        video_clip = VideoClip(make_frame=make_karaoke_frame_sentence, duration=duration)
        # Set audio and FPS
        video_clip = video_clip.set_audio(audio).set_fps(FPS)

        print(f"Writing video file to {output_path}...")
        video_clip.write_videofile(output_path,
                                   codec='libx264',       # Common, good quality/compression
                                   audio_codec='aac',     # Common audio codec
                                   threads=num_threads,   # Control CPU usage
                                   preset=VIDEO_OUTPUT_PRESET, # Speed vs compression trade-off
                                   logger='bar',          # Show progress bar
                                   ffmpeg_params=["-pix_fmt", "yuv420p"]) # Ensures compatibility

        print(f"\nVideo creation finished in {time.time() - start_time:.2f} seconds.")

    except Exception as e:
        import traceback
        print(f"\nError during video creation: {e}")
        traceback.print_exc()
        raise # Re-raise to indicate failure in the main function
    finally:
        # --- Clean up ---
        print("Cleaning up video resources...")
        if audio:
             try: audio.close()
             except Exception: pass # Ignore potential errors on close
        if video_clip:
             try: video_clip.close()
             except Exception: pass # Ignore potential errors on close

        # Clear global data and caches
        _global_sentences_for_frame = []
        word_size_cache = {}
        sentence_width_cache = {}
        gc.collect() # Final garbage collect for this stage
        print("Video cleanup complete.")

# --- Main Execution Logic ---
def main(args):
    """Main function to orchestrate the karaoke video creation process."""
    input_file = args.input_file
    # Define output directory relative to the script or a fixed path
    # Let's create it in the same directory as the input file for simplicity
    output_dir_base = os.path.dirname(input_file)
    if not output_dir_base: # If input file is in the current directory
        output_dir_base = "."
    output_dir = os.path.join(output_dir_base, "output_karaoke")

    print(f"Input file: {input_file}")
    print(f"Output directory: {output_dir}")

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'")
        sys.exit(1) # Exit if input doesn't exist

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    vocal_path = ""
    instrumental_path = ""
    final_stem_dir = os.path.join(output_dir, DEMUCS_MODEL) # Demucs output subdir
    expected_vocal_path = os.path.join(final_stem_dir, 'vocals.wav')
    expected_instrumental_path = os.path.join(final_stem_dir, 'no_vocals.wav')

    # --- Step 1: Separate Vocals (Conditional) ---
    if RUN_SEPARATION:
        try:
            # Pass the main output dir, demucs function will handle the model subdir
            vocal_path, instrumental_path = separate_vocals(input_file, output_dir, DEMUCS_MODEL)
        except Exception as e:
            print(f"Vocal separation failed: {e}. Cannot continue.")
            return # Stop execution if separation fails
    else:
        print(f"\n--- Skipping Vocal Separation (Checking for Existing Files in {final_stem_dir}) ---")
        if os.path.exists(expected_vocal_path) and os.path.exists(expected_instrumental_path):
            vocal_path = expected_vocal_path
            instrumental_path = expected_instrumental_path
            print(f"Using existing files:\n - Vocal: {vocal_path}\n - Instrumental: {instrumental_path}")
        else:
            print(f"Error: Pre-separated files not found. Set RUN_SEPARATION=True or place files at:")
            print(f" - {expected_vocal_path}")
            print(f" - {expected_instrumental_path}")
            return # Stop if files are missing and separation is skipped

    # --- Step 2: Transcribe Vocals (Conditional) ---
    # Place transcription JSON directly in the main output directory
    transcription_json_path = os.path.join(output_dir, f"{base_name}{TRANSCRIPTION_SUFFIX}")

    if RUN_TRANSCRIPTION:
        try:
            # Check if vocal path is valid before proceeding
            if not vocal_path or not os.path.exists(vocal_path):
                 print(f"Error: Vocal file path is invalid or file missing: {vocal_path}")
                 return

            transcription_json_path_returned = transcribe_and_save(vocal_path, transcription_json_path, WHISPER_MODEL_SIZE)
            # Verify the file was actually created
            if not os.path.exists(transcription_json_path_returned) or transcription_json_path_returned != transcription_json_path:
                 print(f"Error: Transcription JSON file missing after run: {transcription_json_path}")
                 return
            print(f"Transcription data saved to {transcription_json_path}")
        except Exception as e:
            print(f"Transcription failed: {e}. Cannot continue.")
            return # Stop if transcription fails
    else:
        print(f"\n--- Skipping Transcription (Checking for JSON File: {transcription_json_path}) ---")
        if not os.path.exists(transcription_json_path):
            print(f"Error: Transcription JSON file not found. Set RUN_TRANSCRIPTION=True or provide the file.")
            return
        else:
             print(f"Using existing transcription file: {transcription_json_path}")

    # --- Step 3: Enhance Instrumental Audio (Optional) ---
    final_instrumental_path = instrumental_path # Default to non-enhanced
    enhancement_succeeded = False
    if RUN_ENHANCEMENT:
        # Check if instrumental path is valid
        if not instrumental_path or not os.path.exists(instrumental_path):
             print(f"Warning: Instrumental file path invalid or missing: {instrumental_path}. Skipping enhancement.")
        else:
            # Define enhanced file path within the same demucs stem directory
            instr_dir = os.path.dirname(instrumental_path) # Should be final_stem_dir
            instr_filename = os.path.basename(instrumental_path)
            instr_base, instr_ext = os.path.splitext(instr_filename)
            enhanced_instrumental_path = os.path.join(instr_dir, f"{instr_base}{ENHANCED_SUFFIX}{instr_ext}")

            try:
                returned_path = enhance_instrumental_chunked(instrumental_path, enhanced_instrumental_path)
                # Check if enhancement actually produced the output file and didn't just return the input path on error
                if returned_path == enhanced_instrumental_path and os.path.exists(enhanced_instrumental_path):
                    final_instrumental_path = returned_path
                    enhancement_succeeded = True
                    print("Using enhanced instrumental track for video.")
                else:
                    print("Enhancement did not produce the expected output file or failed silently. Using original instrumental.")
                    final_instrumental_path = instrumental_path # Explicitly fall back
            except Exception as e:
                print(f"Audio enhancement step failed: {e}. Using original instrumental track.")
                final_instrumental_path = instrumental_path # Ensure fallback on explicit error

    else:
        print("\n--- Skipping Audio Enhancement ---")
        final_instrumental_path = instrumental_path # Ensure it's set if skipping


    # --- Step 4: Create Karaoke Video ---
    # Check if the final instrumental path is valid before creating video
    if not final_instrumental_path or not os.path.exists(final_instrumental_path):
        print(f"Error: Final instrumental audio track not found at {final_instrumental_path}. Cannot create video.")
        return

    # Construct output video filename
    output_video_filename = f"{base_name}_karaoke_{WHISPER_MODEL_SIZE}"
    if RUN_ENHANCEMENT and enhancement_succeeded:
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
             print(f"Warning: Output video file was not found at {output_video_path} after processing. Check logs for errors.")
    except Exception as e:
        print(f"Video creation failed: {e}")
        # Full traceback might have been printed inside the function already
        # import traceback
        # traceback.print_exc()


if __name__ == "__main__":
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Create a karaoke-style video from an audio file using Demucs and Whisper.")
    parser.add_argument("input_file", help="Path to the input audio file (e.g., song.mp3, recording.wav)")
    # Add optional arguments for configuration overrides if desired in the future
    # parser.add_argument("-m", "--model", default=WHISPER_MODEL_SIZE, help="Whisper model size")
    # parser.add_argument("--no-enhance", action="store_false", dest="enhance", help="Disable instrumental enhancement")

    # Check if any arguments were provided (other than the script name)
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        print("\nError: Input file path is required.")
        sys.exit(1)

    args = parser.parse_args()

    # --- Run Main Logic ---
    start_time_script = time.time()
    print("--- Starting Karaoke Video Generation Script ---")
    gc.collect() # Initial garbage collect

    try:
        main(args)
    except Exception as e:
        print(f"\n--- An uncaught error occurred in main execution: {e} ---")
        import traceback
        traceback.print_exc()
    finally:
        gc.collect() # Final garbage collect
        end_time_script = time.time()
        print(f"\n--- Script Finished in {end_time_script - start_time_script:.2f} seconds ---")