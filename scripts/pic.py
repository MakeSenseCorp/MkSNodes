import logging
import os
import v4l2
import fcntl
import mmap
import multiprocessing as mp
import time
#import asyncore
import selectors
 
import bufferman
import numpy
from PIL import Image
 
logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s: %(message)s'
            ,datefmt='%I:%M:%S'
#           ,filename="aalog.log"
            ,level=logging.DEBUG)
 
def opendev(vfn):
    dfile = os.open(vfn, os.O_RDWR | os.O_NONBLOCK, 0)
    return dfile
   
def closedev(dfile):
    os.close(dfile)
 
class asyncamtest():
    def __init__(self,cq,rq,vdev):
        self.vdev = vdev
        self.cq = cq
        self.rq = rq
        self.lgr = logging.getLogger('selectorscamtest')
        self._buffers = []
        self._mmaps = []
        self.asel = selectors.DefaultSelector()
        self.asel.register(self.vdev, selectors.EVENT_READ | selectors.EVENT_WRITE, self.vfileio)
        self.lgr.info("__init__ completes")
 
    def runloop(self):
        self.lgr.info("runloop starts")
        self.running = True
        while self.running:
            if not self.cq.empty():
                self.msgin(self.cq.get())
#           asyncore.loop(0.2, map = self.cmap, count = 3)
            events = self.asel.select(.2)
            self.lgr.info("runloop select returns %d events" % len(events))
            for key, mask in events:
                callback = key.data
                callback(mask)     
        self.releaseBuffs()
        self.lgr.info("runloop finishes")
 
    def vfileio(self, mask):
        ma = "" if selectors.EVENT_READ & mask == 0 else "have read "
        mb = "" if selectors.EVENT_WRITE & mask == 0 else "have write "
        self.lgr.info("fileio " + ma + mb)
        if ma != "":
            self.handle_read()
 
    def msgin(self, msgin):
        cmd = msgin['cmd']
        self.lgr.info("msgin gets %s" % cmd)
        if cmd == 'done':
            self.running = False
            self.lgr.info("msgin running unset")
            msgin['resu'] = 'closing'
            self.rq.put(msgin)
        elif cmd == 'takepics':
            self.takepics(msgin)
        else:
            self.lgr.info("msgin What> - %s" % cmd)
            qi['resu'] = 'What? - %s' % cms
            self.rq.put(msgin)
 
    def takepics(self, msgin):
        self.lgr.info("prepare to take piccy ")
        self._bufferMode = v4l2.V4L2_MEMORY_MMAP
        self.fpixformat = v4l2.V4L2_PIX_FMT_YUYV
        rbuffcount = msgin['buffcount']
        vformat = self.getFormat()
        self.allocBuffs(rbuffcount, vformat)
        procparams={}
        procparams['rotact'] = 0
#       procparams['basefilename'] = "%s%s%%04d" % ('zz', camsettings['sequnamef'])
        procparams['basefilename'] = "fred%04d"
        procparams['savetype'] = "JPEG"
        self._buffman = bufferman.bufferman(self, vformat, vformat.fmt.pix.pixelformat, procparams)
        self.stype = v4l2.v4l2_buf_type(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_STREAMON, self.stype)
        self.lgr.info("takepiccy rolling")
       
    def handle_read(self):
                #but first check we've not closed it recently....
        if self.vdev is None:
            self.lgr.debug("camera ready to read but file is None")
            return
       
        self.lgr.debug("camera ready to read....")
        self._dqbuf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        self._dqbuf.memory = v4l2.V4L2_MEMORY_MMAP
        self._dqbuf.reserved = 0
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_DQBUF, self._dqbuf)
#       self.lgr.debug(v4camSupport.expandBufferFlags(self._dqbuf.flags))
        tstamp = time.strftime("%Y:%m:%d %H:%M:%S")
        self._buffman.makeSmartImage(self._dqbuf.index, 5, tstamp)
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_STREAMOFF, self.stype)
        self._buffman.releaseSmartImageBuff()
        self.releaseBuffs()
        self.lgr.info("camera read finishes")
 
    def getFormat(self):
        vFormat = v4l2.v4l2_format()
        vFormat.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_G_FMT, vFormat) # lets just see what we get.....
        self.lgr.info("video frame format before: - linestride " + str(vFormat.fmt.pix.bytesperline)
            + ", imageInfo:" + str(vFormat.fmt.pix.width) + "/" + str(vFormat.fmt.pix.height))
        vFormat.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        vFormat.fmt.pix.width = 640
        vFormat.fmt.pix.height = 480
        vFormat.fmt.pix.pixelformat = self.fpixformat
        vFormat.fmt.pix.field = v4l2.V4L2_FIELD_NONE
        vFormat.fmt.pix.bytesperline = 0
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_S_FMT, vFormat)
        self.lgr.info("video frame format now set - linestride " + str(vFormat.fmt.pix.bytesperline)
            + ", imageInfo:" + str(vFormat.fmt.pix.width) + "/" + str(vFormat.fmt.pix.height) + " is " + str(vFormat.fmt.pix.sizeimage)
            + " from " + str(vFormat.fmt.pix.width * vFormat.fmt.pix.height))
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_G_FMT, vFormat)
        self.lgr.info("video frame format REALLY set - linestride " + str(vFormat.fmt.pix.bytesperline)
            + ", imageInfo:" + str(vFormat.fmt.pix.width) + "/" + str(vFormat.fmt.pix.height) + " is " + str(vFormat.fmt.pix.sizeimage)
            + " from " + str(vFormat.fmt.pix.width * vFormat.fmt.pix.height))
#           + ", colour space: " + colorSpaces.get(vFormat.fmt.pix.colorspace)
#           + ", pixel format: " + pixelFormats[ vFormat.fmt.pix.pixelformat])
   
        return vFormat
 
    def allocBuffs(self, buffcount, vformat):
        buffRequ = v4l2.v4l2_requestbuffers()
        buffRequ.count = buffcount
        buffRequ.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        buffRequ.memory = self._bufferMode
        fcntl.ioctl(self.vdev, v4l2.VIDIOC_REQBUFS, buffRequ)
        self.lgr.info("agent::allocBuffs requested " + str(buffcount) + ", got " + str(buffRequ.count))
 
        self._buffers = []
        self._mmaps = []
        for bi in range(0, buffRequ.count):
            abuf = v4l2.v4l2_buffer()
            self._buffers.append(abuf)
            abuf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            abuf.memory = self._bufferMode
            abuf.index = bi
            fcntl.ioctl(self.vdev, v4l2.VIDIOC_QUERYBUF, abuf)
            abuf.length = vformat.fmt.pix.sizeimage
            if self._bufferMode == v4l2.V4L2_MEMORY_MMAP:
                fcntl.ioctl(self.vdev, v4l2.VIDIOC_QBUF, abuf)
                self._mmaps.append(mmap.mmap(self.vdev, abuf.length, mmap.MAP_SHARED,  
                    mmap.PROT_READ | mmap.PROT_WRITE, offset=abuf.m.offset))
            else:
                abufarea = ctypes.c_int(55)
                abuf.m.userptr = ctypes.byref(abufarea)
                fcntl.ioctl(self.vdev, v4l2.VIDIOC_QBUF, abuf)
 
        self._dqbuf = v4l2.v4l2_buffer()
 
    def releaseBuffs(self):
        if self._bufferMode == v4l2.V4L2_MEMORY_MMAP:
            for bi in range(0, len(self._mmaps)):
                self._mmaps[bi].close()
            self._mmaps = []
        self._buffers = []
   
       
def runCamera(cq, rq, vfile):
    lgr = logging.getLogger('runCamera')
    lgr.info("camera process started")
    cdev = opendev(vfile)
    lgr.info('camera file opened')
    ct = asyncamtest(cq,rq,cdev)
    ct.runloop()
    if not cdev is None:
        closedev(cdev)
        lgr.info('camera closed')
    time.sleep(0.5)
    lgr.info("camera process finished")
 
if __name__=="__main__":
    logging.info("now attempting to run usb camera using multiple processes and memory mapped IO.......")
    import argparse
    parser = argparse.ArgumentParser(description="test app for multi processing with memory mapped IO")
    parser.add_argument( "-v", "--video"
        , type=int
        , help="number of the video device to be tested (from /dev/videox) default is video0")
    args = parser.parse_args()
    vnum = args.video if args.video else 0
    vfilename = '/dev/video%d' % vnum
    try:
        dfile = opendev(vfilename)
    except IOError:
        logging.critical("Unable to open device - IOError" + vfilename)
        quit()
    except:
        logging.critical("Device open failed for " + vfilename)
        quit()
 
    logging.info("device %s opened OK - start camera process" % vfilename)
    closedev(dfile)
    comq = mp.Queue()
    respq = mp. Queue()
    camproc = mp.Process(target=runCamera, name = "camtest video%d" % vnum
                , args= (comq, respq, vfilename))
    camproc.start()
    comq.put({'cmd': 'takepics', 'buffcount':4})
    time.sleep(4)
    comq.put({'cmd':'done'})
    resp = respq.get()
    print("->" + str(resp))
   
    camproc.join()
    logging.info("byeeee")
