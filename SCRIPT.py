import subprocess,sys,urllib.request,os,ssl,queue,threading
subprocess.run([sys.executable,'-m','pip','install','av','pyglet','sounddevice','numpy'],capture_output=True)
import av,pyglet,pyglet.gl as gl,sounddevice,numpy,ctypes

f=os.environ['TEMP']+'\\v.mp4'
container=av.open(f)
vs=container.streams.video[0]
aus=container.streams.audio[0]
vs.thread_type='AUTO'
resampler=av.AudioResampler(format='fltp',layout='stereo',rate=44100)
fq=queue.Queue(maxsize=2)
aq=queue.Queue(maxsize=20)
vw=vs.codec_context.width;vh=vs.codec_context.height

sd_stream=sounddevice.OutputStream(samplerate=44100,channels=2,dtype='float32')
sd_stream.start()

def audio_worker():
    while True:
        data=aq.get()
        if data is None:break
        sd_stream.write(data)

threading.Thread(target=audio_worker,daemon=True).start()

def decode():
    for p in container.demux(vs,aus):
        for fr in p.decode():
            if isinstance(fr,av.VideoFrame):
                fq.put(fr.to_ndarray(format='rgb24'),block=True)
            elif isinstance(fr,av.AudioFrame):
                for rf in resampler.resample(fr):
                    aq.put(numpy.ascontiguousarray(rf.to_ndarray().T.astype(numpy.float32)))
    aq.put(None)

threading.Thread(target=decode,daemon=True).start()

win=pyglet.window.Window(fullscreen=True)
W,H=win.width,win.height
sx=W/vw;sy=H/vh

tex=pyglet.image.Texture.create(vw,vh)
s=pyglet.sprite.Sprite(tex)
s.scale_x=sx;s.scale_y=sy

@win.event
def on_draw():
    win.clear()
    s.draw()

@win.event
def on_key_press(sym,mod):
    if sym==pyglet.window.key.ESCAPE:pyglet.app.exit()

def upd(dt):
    if not fq.empty():
        d=numpy.ascontiguousarray(numpy.flip(fq.get(),axis=0))
        gl.glBindTexture(gl.GL_TEXTURE_2D,tex.id)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D,0,0,0,vw,vh,gl.GL_RGB,gl.GL_UNSIGNED_BYTE,d.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)))

pyglet.clock.schedule_interval(upd,1/30)
pyglet.app.run()
