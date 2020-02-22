#http://jwhsmith.net/2014/12/capturing-a-webcam-stream-using-v4l2/

import v4l2
import fcntl

vd = open('/dev/video0', 'rw')
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
print(fmt.fmt.pix.pixelformat, str(chr(a)),str(chr(b)),str(chr(c)),str(chr(d)))

