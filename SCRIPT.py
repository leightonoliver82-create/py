import subprocess,sys
subprocess.run([sys.executable,'-m','pip','install','av','pygame','numpy'],capture_output=True)
import av,urllib.request,os,pygame,numpy

f=os.environ['TEMP']+'\\v.mp4'
urllib.request.urlretrieve('https://github.com/leightonoliver82-create/py/raw/refs/heads/main/badapple%20(1).mov',f)

pygame.init()
pygame.mixer.pre_init(44100,-16,2,512)
pygame.mixer.init()
screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN)
pygame.display.set_caption('')
W,H=screen.get_size()

container=av.open(f)
video_stream=container.streams.video[0]
audio_stream=container.streams.audio[0]
fps=float(video_stream.average_rate)
resampler=av.AudioResampler(format='s16p',layout='stereo',rate=44100)

clock=pygame.time.Clock()
channel=pygame.mixer.Channel(0)

for packet in container.demux(video_stream,audio_stream):
    for e in pygame.event.get():
        if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
    for frame in packet.decode():
        if isinstance(frame,av.VideoFrame):
            img=pygame.surfarray.make_surface(frame.to_ndarray(format='rgb24').swapaxes(0,1))
            screen.blit(pygame.transform.scale(img,(W,H)),(0,0))
            pygame.display.flip()
            clock.tick(fps)
        elif isinstance(frame,av.AudioFrame):
            for rf in resampler.resample(frame):
                arr=numpy.ascontiguousarray(numpy.frombuffer(rf.planes[0],dtype=numpy.int16))
                arr=numpy.column_stack((arr,numpy.ascontiguousarray(numpy.frombuffer(rf.planes[1],dtype=numpy.int16))))
                sound=pygame.sndarray.make_sound(arr)
                while channel.get_busy():
                    pygame.time.wait(1)
                channel.queue(sound)

pygame.quit()
