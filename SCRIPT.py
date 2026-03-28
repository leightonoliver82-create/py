import subprocess,sys
subprocess.run([sys.executable,'-m','pip','install','av','sounddevice','numpy','pillow'],capture_output=True)
import av,sounddevice,numpy as np,os,ssl,queue,threading,urllib.request,time,tkinter
from PIL import Image,ImageTk

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
frame_q=queue.Queue(maxsize=2)
start_time=[None]
pending=[None]

sd=sounddevice.OutputStream(samplerate=44100,channels=2,dtype='float32',blocksize=512)
sd.start()

root=tkinter.Tk()
root.attributes('-fullscreen',True)
root.configure(bg='black')
root.bind('<Escape>',lambda e:root.destroy())
W,H=root.winfo_screenwidth(),root.winfo_screenheight()

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
                    scaled=frame.reformat(W,H,format='rgb24')
                    frame_q.put((pts,scaled.to_ndarray()),block=True)
    except Exception as e:print(e)
    finally:frame_q.put(None);audio_q.put(None)

threading.Thread(target=audio_worker,daemon=True).start()
threading.Thread(target=decode_worker,daemon=True).start()

canvas=tkinter.Canvas(root,width=W,height=H,bg='black',highlightthickness=0)
canvas.pack()
img_id=canvas.create_image(0,0,anchor='nw')
img_ref=[None]

def update():
    if pending[0] is None:
        try:pending[0]=frame_q.get_nowait()
        except queue.Empty:root.after(1,update);return
    if pending[0] is None:root.destroy();return
    pts,arr=pending[0]
    if start_time[0] is None:start_time[0]=time.time()
    if time.time()-start_time[0]<pts:root.after(1,update);return
    pending[0]=None
    img_ref[0]=ImageTk.PhotoImage(image=Image.fromarray(arr))
    canvas.itemconfig(img_id,image=img_ref[0])
    root.after(1,update)

root.after(10,update)
root.mainloop()
sd.stop();sd.close();container.close()
