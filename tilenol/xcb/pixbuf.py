import cairo


class Pixbuf(object):

    def __init__(self, width, height, xcore):
        # TODO(tailhook) round up to a scanline
        self._image = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self._context = cairo.Context(self._image)
        self.xcore = xcore

    def context(self):
        return self._context

    def draw(self, x, y, target):
        self.xcore.raw.PutImage(
            format=self.xcore.ImageFormat.ZPixmap,
            drawable=target,
            gc=self.xcore.pixbuf_gc,
            width=self._image.get_width(),
            height=self._image.get_height(),
            dst_x=x,
            dst_y=y,
            left_pad=0,
            depth=24,
            data=self._image,
            )
