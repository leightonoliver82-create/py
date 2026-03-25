import subprocess,sys
subprocess.run([sys.executable,'-m','pip','install','av','pyglet','sounddevice','numpy'],capture_output=True)
import av,pyglet,pyglet.gl as gl,sounddevice,numpy as np,ctypes,os,queue,threading,time
URL='https://raw.githubusercontent.com/leightonoliver82-create/py/main/badapple.mov'
f=os.path.join(os.environ['TEMP'],'v.mp4')
os.makedirs(os.environ['TEMP'], exist_ok=True)
if os.path.exists(f): os.remove(f)
print('Downloading...')
os.system('bitsadmin /transfer j '+URL+' '+f)
print('Done.')
container=av.open(f)
vs=container.streams.video[0]
aus=container.streams.audio[0]
vs.thread_type='AUTO'
vw=vs.codec_context.width;vh=vs.codec_context.height
resampler=av.AudioResampler(format='fltp',layout='stereo',rate=44100)
audio_q=queue.Queue(maxsize=100)
frame_q=queue.Queue(maxsize=8)
start_time=[None]
pending=[None]
sd_stream=sounddevice.OutputStream(samplerate=44100,channels=2,dtype='float32',blocksize=512)
sd_stream.start()
def audio_worker():
    while True:
        data=audio_q.get()
        if data is None:break
        sd_stream.write(data)
def decode_worker():
    try:
        for packet in container.demux(vs,aus):
            for frame in packet.decode():
                if isinstance(frame,av.AudioFrame):
                    for rf in resampler.resample(frame):
                        audio_q.put(np.ascontiguousarray(rf.to_ndarray().T.astype(np.float32)))
                elif isinstance(frame,av.VideoFrame):
                    pts=float(frame.pts*vs.time_base) if frame.pts else 0
                    frame_q.put((pts,frame.to_ndarray(format='rgb24')),block=True)
    except:pass
    finally:frame_q.put(None);audio_q.put(None)
threading.Thread(target=audio_worker,daemon=True).start()
threading.Thread(target=decode_worker,daemon=True).start()
win=pyglet.window.Window(fullscreen=True)
W,H=win.width,win.height
tex=pyglet.image.Texture.create(vw,vh)
sprite=pyglet.sprite.Sprite(tex)
sprite.scale_x=W/vw;sprite.scale_y=H/vh
@win.event
def on_draw():
    win.clear();sprite.draw()
@win.event
def on_key_press(sym,mod):
    if sym==pyglet.window.key.ESCAPE:pyglet.app.exit()
def update(dt):
    if pending[0] is None:
        try:pending[0]=frame_q.get_nowait()
        except queue.Empty:return
    if pending[0] is None:pyglet.app.exit();return
    pts,arr=pending[0]
    if start_time[0] is None:start_time[0]=time.time()
    if time.time()-start_time[0]<pts:return
    pending[0]=None
    d=np.ascontiguousarray(np.flip(arr,axis=0))
    gl.glBindTexture(gl.GL_TEXTURE_2D,tex.id)
    gl.glTexSubImage2D(gl.GL_TEXTURE_2D,0,0,0,vw,vh,gl.GL_RGB,gl.GL_UNSIGNED_BYTE,d.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)))
pyglet.clock.schedule_interval(update,1/120)
try:pyglet.app.run()
finally:sd_stream.stop();sd_stream.close();container.close()
