import subprocess, sys

# Install dependencies
subprocess.run(
    [sys.executable, '-m', 'pip', 'install', 'av', 'pyglet', 'sounddevice', 'numpy'],
    capture_output=True
)

import av
import pyglet
import pyglet.gl as gl
import sounddevice
import numpy as np
import ctypes
import os
import ssl
import queue
import threading
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────
URL        = "https://tinyurl.com/leighty82"
TEMP_FILE  = os.path.join(os.environ['TEMP'], 'v.mp4')
AUDIO_RATE = 44100
FPS_TARGET = 60
# ──────────────────────────────────────────────────────────────────────────────


def download(url: str, dest: str) -> None:
    """Download file with a simple progress indicator."""
    print(f"Downloading {url} ...")

    def progress(block, block_size, total):
        if total > 0:
            pct = min(block * block_size / total * 100, 100)
            print(f"\r  {pct:.1f}%", end='', flush=True)

    ctx = ssl.create_unverified_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx)
    )
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, dest, reporthook=progress)
    print("\nDownload complete.")


def cleanup(path: str) -> None:
    try:
        os.remove(path)
        print(f"Cleaned up {path}")
    except OSError:
        pass


# ── Download ──────────────────────────────────────────────────────────────────
download(URL, TEMP_FILE)

# ── Open container ────────────────────────────────────────────────────────────
container = av.open(TEMP_FILE)
vs  = container.streams.video[0]
aus = container.streams.audio[0]
vs.thread_type = 'AUTO'

vw = vs.codec_context.width
vh = vs.codec_context.height
duration = float(vs.duration * vs.time_base) if vs.duration else 0

print(f"Video: {vw}x{vh}  |  Duration: {duration:.1f}s")

# ── Audio ─────────────────────────────────────────────────────────────────────
resampler  = av.AudioResampler(format='fltp', layout='stereo', rate=AUDIO_RATE)
audio_q    = queue.Queue(maxsize=50)
sd_stream  = sounddevice.OutputStream(
    samplerate=AUDIO_RATE, channels=2, dtype='float32',
    blocksize=1024
)
sd_stream.start()

def audio_worker():
    while True:
        data = audio_q.get()
        if data is None:
            break
        sd_stream.write(data)

threading.Thread(target=audio_worker, daemon=True).start()

# ── Video frame queue ─────────────────────────────────────────────────────────
frame_q = queue.Queue(maxsize=4)

def decode_worker():
    try:
        for packet in container.demux(vs, aus):
            for frame in packet.decode():
                if isinstance(frame, av.VideoFrame):
                    frame_q.put(
                        frame.to_ndarray(format='rgb24'),
                        block=True
                    )
                elif isinstance(frame, av.AudioFrame):
                    for rf in resampler.resample(frame):
                        chunk = np.ascontiguousarray(
                            rf.to_ndarray().T.astype(np.float32)
                        )
                        audio_q.put(chunk)
    except av.AVError as e:
        print(f"Decode error: {e}")
    finally:
        frame_q.put(None)   # sentinel
        audio_q.put(None)   # sentinel

threading.Thread(target=decode_worker, daemon=True).start()

# ── Window ────────────────────────────────────────────────────────────────────
win = pyglet.window.Window(fullscreen=True, caption="Player")
W, H = win.width, win.height

sx = W / vw
sy = H / vh

tex    = pyglet.image.Texture.create(vw, vh)
sprite = pyglet.sprite.Sprite(tex)
sprite.scale_x = sx
sprite.scale_y = sy

_done = False  # set when decode finishes

@win.event
def on_draw():
    win.clear()
    sprite.draw()

@win.event
def on_key_press(sym, mod):
    if sym == pyglet.window.key.ESCAPE:
        pyglet.app.exit()

def update(dt):
    global _done
    if _done:
        return

    item = None
    # drain stale frames, keep the newest
    while not frame_q.empty():
        item = frame_q.get_nowait()

    if item is None and not frame_q.empty():
        return          # nothing new yet
    if item is None:
        return

    if item is None:    # sentinel — playback finished
        _done = True
        pyglet.app.exit()
        return

    d = np.ascontiguousarray(np.flip(item, axis=0))
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex.id)
    gl.glTexSubImage2D(
        gl.GL_TEXTURE_2D, 0, 0, 0, vw, vh,
        gl.GL_RGB, gl.GL_UNSIGNED_BYTE,
        d.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
    )

pyglet.clock.schedule_interval(update, 1 / FPS_TARGET)

# ── Run ───────────────────────────────────────────────────────────────────────
try:
    pyglet.app.run()
finally:
    sd_stream.stop()
    sd_stream.close()
    container.close()
    cleanup(TEMP_FILE)
