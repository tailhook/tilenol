import cairo

import ctypes
from .pixbuf import PixbufBase


IPC_CREAT = 0o1000
IPC_PRIVATE = 0


try:
    rt = ctypes.CDLL('librt.so')
    shmget = rt.shmget
    shmget.argtypes = [ctypes.c_int, ctypes.c_size_t, ctypes.c_int]
    shmget.restype = ctypes.c_int
    shmat = rt.shmat
    shmat.argtypes = [ctypes.c_int,
                      ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
    shmat.restype = ctypes.c_void_p
    shmdt = rt.shmdt
    shmdt.argtypes = [ctypes.c_void_p]
    shmdt.restype = ctypes.c_int
    shmctl = rt.shmctl
    shmctl.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    shmctl.restype = ctypes.c_int
except (OSError, AttributeError):
    raise ImportError("Shared memory is not supported")


class ShmPixbuf(PixbufBase):

    def __init__(self, width, height, conn):
        # TODO(tailhook) round up to a scanline
        size = width*height*4
        self.shmid = shmget(IPC_PRIVATE, size, IPC_CREAT|0o777)
        self.addr = shmat(self.shmid, None, 0)
        super().__init__(cairo.ImageSurface.create_for_data(
            (ctypes.c_char * size).from_address(self.addr),
            cairo.FORMAT_ARGB32, width, height, width*4), conn)
        self.shmseg = conn._conn.new_xid()
        conn.shm.Attach(
            shmseg=self.shmseg,
            shmid=self.shmid,
            read_only=True,
            )

    def draw(self, target, x=0, y=0):
        self.xcore.shm.PutImage(
            drawable=target,
            gc=self.xcore.pixbuf_gc,
            src_x=0,
            src_y=0,
            src_width=self._image.get_width(),
            src_height=self._image.get_height(),
            total_width=self._image.get_width(),
            total_height=self._image.get_height(),
            dst_x=x,
            dst_y=y,
            depth=24,
            format=self.xcore.ImageFormat.ZPixmap,
            send_event=0,
            shmseg=self.shmseg,
            offset=0,
            )

    def __del__(self):
        self.xcore.shm.Detach(shmseg=self.shmseg)
        self._image.finish()
        shmdt(self.addr)
        shmctl(self.shmid, IPC_RMID, 0)
        del self.shmid
        del self.addr
