import cairo


class PixbufBase(object):

    def __init__(self, image, xcore):
        self._image = image
        self._context = cairo.Context(self._image)
        self.xcore = xcore

    def context(self):
        return self._context


class Pixbuf(object):

    def __init__(self, width, height, xcore):
        # TODO(tailhook) round up to a scanline
        super().__init__(cairo.ImageSurface(
            cairo.FORMAT_ARGB32, width, height))

    def draw(self, target, x=0, y=0):
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
