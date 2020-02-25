#http://jwhsmith.net/2014/12/capturing-a-webcam-stream-using-v4l2/

import v4l2
import fcntl
import mmap
import os
import time

#from io import StringIO # "import StringIO" directly in python2
from PIL import Image
from io import BytesIO

#vd = open('/dev/video0', 'rw')
vd = os.open('/dev/video0', os.O_RDWR | os.O_NONBLOCK, 0)
cp = v4l2.v4l2_capability()
fcntl.ioctl(vd, v4l2.VIDIOC_QUERYCAP, cp)

print("Driver:", cp.driver)
print("Name:", cp.card)
print("Support:")
print("Capturing - ", cp.capabilities & v4l2.V4L2_CAP_VIDEO_CAPTURE)
print("Read - ", cp.capabilities & v4l2.V4L2_CAP_READWRITE)
print("Streaming", cp.capabilities & v4l2.V4L2_CAP_STREAMING)

# Setup video format (V4L2_PIX_FMT_MJPEG)
fmt = v4l2.v4l2_format()
fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
fcntl.ioctl(vd, v4l2.VIDIOC_G_FMT, fmt)  # get current settings
d = fmt.fmt.pix.pixelformat >> 24
c = (fmt.fmt.pix.pixelformat >> 16) & 0xFF
b = (fmt.fmt.pix.pixelformat >> 8) & 0xFF
a = (fmt.fmt.pix.pixelformat) & 0xFF
print("width:", fmt.fmt.pix.width, "height", fmt.fmt.pix.height)
print(fmt.fmt.pix.pixelformat, str(chr(a)),str(chr(b)),str(chr(c)),str(chr(d)))

fmt.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_MJPEG
fmt.fmt.pix.width  = 800
fmt.fmt.pix.height = 600
fcntl.ioctl(vd, v4l2.VIDIOC_S_FMT, fmt)  # set whatever default settings we got before

req         = v4l2.v4l2_requestbuffers()
req.type    = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
req.memory  = v4l2.V4L2_MEMORY_MMAP
req.count   = 1  # nr of buffer frames
fcntl.ioctl(vd, v4l2.VIDIOC_REQBUFS, req)  # tell the driver that we want some buffers 

print(req.count)

buf         = v4l2.v4l2_buffer()
buf.type    = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
buf.memory  = v4l2.V4L2_MEMORY_MMAP
buf.index   = 0
fcntl.ioctl(vd, v4l2.VIDIOC_QUERYBUF, buf)
mm = mmap.mmap(vd, buf.length, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=buf.m.offset)
# queue the buffer for capture
fcntl.ioctl(vd, v4l2.VIDIOC_QBUF, buf)

print(">> Start streaming")
buf_type = v4l2.v4l2_buf_type(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
fcntl.ioctl(vd, v4l2.VIDIOC_STREAMON, buf_type)

time.sleep(5)

buf         = v4l2.v4l2_buffer()
buf.type    = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
buf.memory  = v4l2.V4L2_MEMORY_MMAP
fcntl.ioctl(vd, v4l2.VIDIOC_DQBUF, buf)

vid = open("video.jpeg", "wb")
frame = mm.read(buf.length)
#vid.write(frame)
#mm.seek(0)
#fcntl.ioctl(vd, v4l2.VIDIOC_QBUF, buf)  # requeue the buffer

print(">> Stop streaming")
fcntl.ioctl(vd, v4l2.VIDIOC_STREAMOFF, buf_type)
vid.close()

#img = Image.open("video.jpeg")
img = Image.open(BytesIO(frame))
img.save("out.jpg", "JPEG", quality=25, optimize=True, progressive=True)
img.save("out.webp",'webp',quality = 50)

output = BytesIO()
img.save(output, "JPEG", quality=5, optimize=True, progressive=True)
#print(output.getvalue())

#vd.close()