#!/usr/bin/env python3
"""
Python Bridge for Karaoke Automate Desktop App
Handles IPC communication with Electron main process
"""

import sys
import json
import os
import threading
import time
from pathlib import Path

# Get the absolute path to this script's directory
script_dir = Path(__file__).parent.absolute()

print(f"Script directory: {script_dir}", file=sys.stderr)
print(f"Python path: {sys.path[:3]}", file=sys.stderr)

try:
    # Import the main karaoke processing functions from the local main.py
    from main import (
        separate_vocals, transcribe_and_save, enhance_instrumental_chunked,
        create_karaoke_video_from_json, download_audio_from_youtube
    )
    MAIN_MODULE_AVAILABLE = True
    print("Successfully imported main module functions", file=sys.stderr)
except ImportError as e:
    print(f"Warning: Could not import main module: {e}", file=sys.stderr)
    print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
    print(f"Files in script directory: {list(script_dir.glob('*.py'))}", file=sys.stderr)
    MAIN_MODULE_AVAILABLE = False

class PythonBridge:
    def __init__(self):
        self.running = True
        self.current_task = None
        
    def send_message(self, message):
        """Send a JSON message to Electron via stdout"""
        try:
            print(json.dumps(message), flush=True)
        except Exception as e:
            print(f"Error sending message: {e}", file=sys.stderr)
    
    def send_response(self, request_id, success=True, data=None, error=None):
        """Send a response to a specific request"""
        response = {
            "type": "response",
            "id": request_id,
            "success": success,
            "data": data,
            "error": error
        }
        self.send_message(response)
    
    def send_progress(self, request_id, progress, message=""):
        """Send progress update for a long-running task"""
        progress_msg = {
            "type": "progress",
            "id": request_id,
            "progress": progress,
            "message": message
        }
        self.send_message(progress_msg)
    
    def send_log(self, level, message):
        """Send a log message"""
        log_msg = {
            "type": "log",
            "level": level,
            "message": message,
            "timestamp": time.time()
        }
        self.send_message(log_msg)
    
    def process_audio_task(self, request_id, data):
        """Process audio file to create karaoke video"""
        try:
            if not MAIN_MODULE_AVAILABLE:
                raise Exception("Main processing module not available")
            
            # Extract parameters
            input_file = data.get("input_file")
            output_dir = data.get("output_dir")
            youtube_url = data.get("youtube_url")
            options = data.get("options", {})
            
            if not input_file and not youtube_url:
                raise ValueError("Either input_file or youtube_url must be provided")
            
            if not output_dir:
                raise ValueError("output_dir is required")
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            self.send_progress(request_id, 5, "Starting audio processing...")
            
            # Step 1: Download from YouTube if URL provided
            if youtube_url:
                self.send_progress(request_id, 10, "Downloading audio from YouTube...")
                try:
                    download_result = download_audio_from_youtube(youtube_url, output_dir)
                    # The function returns a tuple (audio_file, video_id), we need just the file path
                    if isinstance(download_result, tuple):
                        input_file, video_id = download_result
                    else:
                        input_file = download_result
                    self.send_progress(request_id, 20, f"Downloaded: {os.path.basename(input_file)}")
                except Exception as e:
                    raise Exception(f"YouTube download failed: {str(e)}")
            
            # Step 2: Separate vocals
            self.send_progress(request_id, 25, "Separating vocals from instrumental...")
            try:
                vocal_path, instrumental_path = separate_vocals(input_file, output_dir)
                self.send_progress(request_id, 45, "Vocal separation completed")
            except Exception as e:
                raise Exception(f"Vocal separation failed: {str(e)}")
            
            # Step 3: Enhance instrumental (optional)
            if options.get("enhance_instrumental", False):
                self.send_progress(request_id, 50, "Enhancing instrumental track...")
                try:
                    enhanced_path = os.path.join(output_dir, "instrumental_enhanced.wav")
                    instrumental_path = enhance_instrumental_chunked(instrumental_path, enhanced_path)
                    self.send_progress(request_id, 60, "Instrumental enhancement completed")
                except Exception as e:
                    self.send_log("warning", f"Instrumental enhancement failed: {str(e)}")
                    # Continue with original instrumental
            
            # Step 4: Transcribe vocals
            self.send_progress(request_id, 65, "Transcribing vocals...")
            try:
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                transcription_path = os.path.join(output_dir, f"{base_name}_transcription.json")
                transcribe_and_save(vocal_path, transcription_path, options.get("whisper_model", "medium"))
                self.send_progress(request_id, 80, "Transcription completed")
            except Exception as e:
                raise Exception(f"Transcription failed: {str(e)}")
            
            # Step 5: Create karaoke video
            self.send_progress(request_id, 85, "Creating karaoke video...")
            try:
                output_video = os.path.join(output_dir, f"{base_name}_karaoke.mp4")
                create_karaoke_video_from_json(instrumental_path, transcription_path, output_video)
                self.send_progress(request_id, 100, "Karaoke video created successfully!")
            except Exception as e:
                raise Exception(f"Video creation failed: {str(e)}")
            
            # Return success response
            result = {
                "output_video": output_video,
                "vocal_track": vocal_path,
                "instrumental_track": instrumental_path,
                "transcription": transcription_path
            }
            
            self.send_response(request_id, True, result)
            
        except Exception as e:
            self.send_log("error", f"Audio processing failed: {str(e)}")
            self.send_response(request_id, False, error=str(e))
    
    def handle_request(self, request):
        """Handle incoming request from Electron"""
        try:
            request_type = request.get("type")
            request_id = request.get("id")
            data = request.get("data", {})
            
            if request_type == "process_audio":
                # Run in separate thread to avoid blocking
                thread = threading.Thread(
                    target=self.process_audio_task,
                    args=(request_id, data),
                    daemon=True
                )
                thread.start()
                self.current_task = thread
                
            elif request_type == "ping":
                self.send_response(request_id, True, {"message": "pong"})
                
            elif request_type == "get_status":
                status = {
                    "main_module_available": MAIN_MODULE_AVAILABLE,
                    "current_task_running": self.current_task and self.current_task.is_alive(),
                    "python_version": sys.version,
                    "working_directory": os.getcwd()
                }
                self.send_response(request_id, True, status)
                
            elif request_type == "stop":
                self.running = False
                self.send_response(request_id, True, {"message": "Stopping..."})
                
            else:
                self.send_response(request_id, False, error=f"Unknown request type: {request_type}")
                
        except Exception as e:
            self.send_log("error", f"Error handling request: {str(e)}")
            if "request_id" in locals():
                self.send_response(request_id, False, error=str(e))
    
    def run(self):
        """Main loop - listen for messages from Electron"""
        self.send_log("info", "Python bridge started")
        
        try:
            while self.running:
                try:
                    # Read line from stdin
                    line = sys.stdin.readline()
                    if not line:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse JSON request
                    try:
                        request = json.loads(line)
                        self.handle_request(request)
                    except json.JSONDecodeError as e:
                        self.send_log("error", f"Invalid JSON received: {e}")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.send_log("error", f"Error in main loop: {str(e)}")
                    
        except Exception as e:
            self.send_log("error", f"Fatal error in bridge: {str(e)}")
        finally:
            self.send_log("info", "Python bridge stopping")

def main():
    """Entry point"""
    bridge = PythonBridge()
    bridge.run()

if __name__ == "__main__":
    main() 