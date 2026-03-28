import subprocess,sys
subprocess.run([sys.executable,'-m','pip','install','av','sounddevice','numpy','pygame'],capture_output=True)
import av,sounddevice,numpy as np,os,ssl,queue,threading,urllib.request,time,pygame

URL='https://raw.githubusercontent.com/leightonoliver82-create/py/main/badapple.mov'
f=os.path.join(os.environ['TEMP'],'v.mp4')
ctx=ssl._create_unverified_context()
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
print('Downloading...')
open(f,'wb').write(urllib.request.urlopen(req,context=ctx).read())
print('Done.')

container=av.open(f)
vs=container.streams.video[0]
aus=container.streams.audio[0]
vs.thread_type='AUTO'
vw=vs.codec_context.width;vh=vs.codec_context.height
resampler=av.AudioResampler(format='fltp',layout='stereo',rate=44100)
audio_q=queue.Queue(maxsize=100)
frame_q=queue.Queue(maxsize=4)
start_time=[None]
pending=[None]

sd=sounddevice.OutputStream(samplerate=44100,channels=2,dtype='float32',blocksize=256)
sd.start()

pygame.init()
screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN|pygame.HWSURFACE|pygame.DOUBLEBUF)
W,H=screen.get_size()
# pre-create scaled surface once
surf=pygame.Surface((W,H))
raw=pygame.Surface((vw,vh))

def audio_worker():
    while True:
        d=audio_q.get()
        if d is None:break
        sd.write(d)

def decode_worker():
    try:
        for packet in container.demux(vs,aus):
            for frame in packet.decode():
                if isinstance(frame,av.AudioFrame):
                    for rf in resampler.resample(frame):
                        audio_q.put(np.ascontiguousarray(rf.to_ndarray().T.astype(np.float32)))
                elif isinstance(frame,av.VideoFrame):
                    pts=float(frame.pts*vs.time_base) if frame.pts else 0
                    # reformat to screen size in C — zero Python resize cost
                    arr=frame.reformat(W,H,format='rgb24').to_ndarray()
                    frame_q.put((pts,arr),block=True)
    except:pass
    finally:frame_q.put(None);audio_q.put(None)

threading.Thread(target=audio_worker,daemon=True).start()
threading.Thread(target=decode_worker,daemon=True).start()

clock=pygame.time.Clock()
running=True
while running:
    for e in pygame.event.get():
        if e.type==pygame.QUIT or(e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE):running=False

    if pending[0] is None:
        try:pending[0]=frame_q.get_nowait()
        except queue.Empty:clock.tick(120);continue

    if pending[0] is None:running=False;break
    pts,arr=pending[0]
    if start_time[0] is None:start_time[0]=time.time()
    if time.time()-start_time[0]<pts:clock.tick(120);continue
    pending[0]=None
    # blit already-scaled array directly — no transform.scale needed
    pygame.surfarray.blit_array(surf,arr.swapaxes(0,1))
    screen.blit(surf,(0,0))
    pygame.display.flip()
    clock.tick(60)

sd.stop();sd.close();container.close();pygame.quit()
