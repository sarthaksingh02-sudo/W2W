import os
import time
import subprocess
import threading
import logging
import numpy as np
import cv2
from collections import deque
from typing import Optional, Tuple, Any

# Configure logging
logger = logging.getLogger("cv_engine.stream")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class FFmpegVideoSource:
    """
    Robust RTSP video ingestor.
    Prioritizes FFmpeg with NVDEC.
    Falls back to OpenCV (CPU) if FFmpeg binaries are missing.
    """

    def __init__(
        self,
        source_id: str,
        rtsp_url: str,
        gpu_id: int = 0,
        buffer_size: int = 30,
        resize_dim: Optional[Tuple[int, int]] = None,
        reconnect_delay: int = 5
    ):
        self.source_id = source_id
        # Handle numeric string for webcam (e.g. "0" -> 0)
        if isinstance(rtsp_url, str) and rtsp_url.isdigit():
            self.rtsp_url = int(rtsp_url)
        else:
            self.rtsp_url = rtsp_url
            
        self.gpu_id = gpu_id
        self.buffer_size = buffer_size
        self.resize_dim = resize_dim
        self.reconnect_delay = reconnect_delay

        self.running = False
        self.mode = "init" # 'ffmpeg' or 'opencv'
        self.process: Optional[subprocess.Popen] = None
        self.cap: Optional[cv2.VideoCapture] = None
        
        self.thread: Optional[threading.Thread] = None
        self.frame_buffer: deque = deque(maxlen=buffer_size)
        
        self.width = 0
        self.height = 0
        self.fps = 30.0

    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg/ffprobe is available."""
        try:
            subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.STDOUT)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_stream_info(self) -> bool:
        """Probes stream info. Falls back to OpenCV probe if ffprobe fails."""
        # 1. Try FFprobe (Skip if local webcam int)
        if self.check_ffmpeg() and not isinstance(self.rtsp_url, int):
            try:
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,r_frame_rate",
                    "-of", "csv=s=x:p=0", self.rtsp_url
                ]
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8").strip()
                logger.info(f"[{self.source_id}] FFprobe Output: {output}")
                parts = output.split("x")
                if len(parts) >= 3:
                     self.width = int(parts[0])
                     self.height = int(parts[1])
                     rate = parts[2]
                     if "/" in rate:
                         num, den = rate.split("/")
                         self.fps = float(num) / float(den) if float(den) > 0 else 30.0
                     else:
                         self.fps = float(rate)
                self.mode = "ffmpeg"
                return True
            except Exception as e:
                logger.warn(f"[{self.source_id}] FFprobe failed: {e}. Trying OpenCV fallback...")

        if not self.rtsp_url and self.rtsp_url != 0:
            logger.error(f"[{self.source_id}] No RTSP URL provided in config.")
            return False

        # 2. OpenCV Fallback
        logger.info(f"[{self.source_id}] Probing stream: {self.rtsp_url}...")
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|timeout;5000000" # 5s timeout
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            cap.release()
            self.mode = "opencv"
            logger.info(f"[{self.source_id}] OpenCV Probe Success. Mode set to OpenCV implementation.")
            return True
        
        logger.error(f"[{self.source_id}] Could not open video source: {self.rtsp_url}")
        return False

    def build_ffmpeg_command(self) -> list:
        # Construct FFmpeg command (same as before)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-hwaccel", "cuda", "-hwaccel_device", str(self.gpu_id),
            "-rtsp_transport", "tcp", "-fflags", "nobuffer", "-flags", "low_delay",
            "-strict", "experimental", "-i", self.rtsp_url,
        ]
        
        filters = []
        if self.resize_dim:
             # Try npp scale
             filters.append(f"scale_npp={self.resize_dim[0]}:{self.resize_dim[1]}:format=bgr24")
        else:
             filters.append("hwdownload,format=bgr24")
        
        if filters:
             cmd.extend(["-vf", ",".join(filters)])
        else:
             cmd.extend(["-f", "rawvideo", "-pix_fmt", "bgr24"])

        cmd.extend(["-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"])
        return cmd

    def start(self):
        if self.running: return
        if self.width == 0:
            if not self.get_stream_info():
                logger.error("Failed to probe stream.")
                return

        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=2)
        self._terminate()

    def _terminate(self):
        if self.process:
            try: self.process.terminate() 
            except: self.process.kill()
            self.process = None
        if self.cap:
             self.cap.release()
             self.cap = None

    def _worker(self):
        if self.resize_dim:
            w, h = self.resize_dim
        else:
            w, h = self.width, self.height
        frame_size = w * h * 3

        while self.running:
            if self.mode == "ffmpeg":
                cmd = self.build_ffmpeg_command()
                try:
                    self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**7)
                    while self.running:
                        in_bytes = self.process.stdout.read(frame_size)
                        if len(in_bytes) != frame_size: break # Reconnect
                        frame = np.frombuffer(in_bytes, np.uint8).reshape((h, w, 3))
                        self.frame_buffer.append((time.time(), frame))
                except Exception as e:
                    logger.error(f"FFmpeg error: {e}")
                finally:
                    self._terminate()
            
            elif self.mode == "opencv":
                try:
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    if not self.cap.isOpened(): raise Exception("OpenCV Open Failed")
                    while self.running:
                        ret, frame = self.cap.read()
                        if not ret: break
                        if self.resize_dim:
                            frame = cv2.resize(frame, self.resize_dim)
                        self.frame_buffer.append((time.time(), frame))
                except Exception as e:
                    logger.error(f"OpenCV error: {e}")
                finally:
                    self._terminate()

            if self.running:
                logger.info("Reconnecting...")
                time.sleep(self.reconnect_delay)

    def read(self):
        try:
            return self.frame_buffer[-1]
        except IndexError:
            return None, None
