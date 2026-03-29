"""
Fullscreen Borderless MP4 Player — auto-installs dependencies
Controls:  ESC / Q  →  quit
"""

import sys
import subprocess

# ── Auto-install dependencies ─────────────────────────────────────────────
REQUIRED = {
    "pygame":    "pygame",
    "av":        "av",
    "cv2":       "opencv-python",
    "numpy":     "numpy",
}

def ensure_packages():
    import importlib
    missing = [pip for mod, pip in REQUIRED.items()
               if importlib.util.find_spec(mod) is None]
    if missing:
        print(f"Installing: {', '.join(missing)} ...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Install complete.\n")

ensure_packages()

# ── Imports ───────────────────────────────────────────────────────────────
import os
import tempfile
import time
import urllib.request
import threading

import av
import cv2
import numpy as np
import pygame

DEFAULT_URL = "https://github.com/leightonoliver82-create/py/raw/refs/heads/main/error.mp4"

# ── Download ──────────────────────────────────────────────────────────────

def download_video(url: str, dest: str) -> bool:
    print("Downloading video...")
    try:
        def _hook(count, block, total):
            if total > 0:
                print(f"\r  {min(count*block*100//total, 100)}%", end="", flush=True)
        urllib.request.urlretrieve(url, dest, reporthook=_hook)
        print("\r  Done.        ")
        return True
    except Exception as e:
        print(f"\nDownload failed: {e}")
        return False

# ── Audio thread ──────────────────────────────────────────────────────────

def audio_thread(video_path, start_event, stop_event):
    try:
        container = av.open(video_path)
        stream    = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            return

        samples = []
        for packet in container.demux(stream):
            if stop_event.is_set():
                break
            for frame in packet.decode():
                arr = frame.to_ndarray()
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                samples.append(arr.T.copy())

        if not samples:
            return

        pcm  = np.concatenate(samples, axis=0)
        rate = stream.codec_context.sample_rate or 44100

        if pcm.dtype != np.int16:
            mx = np.max(np.abs(pcm))
            if mx > 0:
                pcm = (pcm / mx * 32767).astype(np.int16)
            else:
                pcm = pcm.astype(np.int16)

        if pcm.ndim == 1 or pcm.shape[1] == 1:
            pcm = np.column_stack([pcm.reshape(-1,1), pcm.reshape(-1,1)])

        pygame.mixer.init(frequency=rate, size=-16, channels=2, buffer=2048)
        sound = pygame.sndarray.make_sound(np.ascontiguousarray(pcm))

        start_event.wait()
        sound.play()

        while sound.get_num_channels() > 0 and not stop_event.is_set():
            time.sleep(0.05)

        sound.stop()
        pygame.mixer.quit()
        container.close()

    except Exception as e:
        print(f"Audio error: {e}")

# ── Main player ───────────────────────────────────────────────────────────

def play(video_path: str):
    container = av.open(video_path)
    v_stream  = next((s for s in container.streams if s.type == "video"), None)
    if v_stream is None:
        print("No video stream found.")
        sys.exit(1)

    fps   = float(v_stream.average_rate or 30)
    vid_w = v_stream.codec_context.width
    vid_h = v_stream.codec_context.height

    # ── Pygame / display setup ────────────────────────────────────────────
    pygame.init()

    # Use (0,0) so pygame picks the native resolution automatically
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.NOFRAME)
    screen_w, screen_h = screen.get_size()          # actual pixel dimensions

    pygame.display.set_caption("Video Player")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    # Letterbox: scale video to fill screen while keeping aspect ratio
    scale = min(screen_w / vid_w, screen_h / vid_h)
    dst_w = int(vid_w * scale)
    dst_h = int(vid_h * scale)
    dst_x = (screen_w - dst_w) // 2
    dst_y = (screen_h - dst_h) // 2
    dst_rect = pygame.Rect(dst_x, dst_y, dst_w, dst_h)

    # ── Audio ─────────────────────────────────────────────────────────────
    start_event = threading.Event()
    stop_event  = threading.Event()
    threading.Thread(
        target=audio_thread,
        args=(video_path, start_event, stop_event),
        daemon=True,
    ).start()

    # ── Playback loop ─────────────────────────────────────────────────────
    frame_gen  = (f for pkt in container.demux(v_stream) for f in pkt.decode())
    started    = False
    running    = True

    for av_frame in frame_gen:
        if not running:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        if not running:
            break

        # Decode frame → pygame surface
        frame_np = av_frame.to_ndarray(format="rgb24")          # H × W × 3
        frame_rs = cv2.resize(frame_np, (dst_w, dst_h),
                              interpolation=cv2.INTER_LINEAR)
        # surfarray expects W × H × 3
        surf = pygame.surfarray.make_surface(
            np.ascontiguousarray(frame_rs.transpose(1, 0, 2))
        )

        if not started:
            start_event.set()
            started = True

        screen.fill((0, 0, 0))
        screen.blit(surf, dst_rect)
        pygame.display.flip()
        clock.tick(fps)

    stop_event.set()
    container.close()
    pygame.quit()

# ── Entry point ───────────────────────────────────────────────────────────

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    if source.startswith("http://") or source.startswith("https://"):
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        if not download_video(source, tmp.name):
            sys.exit(1)
        video_path = tmp.name
        cleanup    = True
    else:
        video_path = source
        cleanup    = False

    try:
        play(video_path)
    finally:
        if cleanup:
            try:
                os.remove(video_path)
            except OSError:
                pass

if __name__ == "__main__":
    main()
