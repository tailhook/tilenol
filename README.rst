Tilenol
=======

Tilenol is a tiling manager. It's similar in look and feel to qtile, but
has much different implementation and configuration.

Dependencies
------------

 * python3
 * python-greenlet
 * xcb-proto (package containing `/usr/share/xcb/*.xml`)
 * zorro (http://github.com/tailhook/zorro)
 * pycairo (patched to support get_data(), http://github.com/tailhook/pycairo)

.. note::

    Tilenol includes pure-python implementation of xcb, so only xml files are
    needed

Running
-------

After installing python package. You may want to copy ``examples/*.yaml`` into
``/etc/xdg/tilenol`` or ``~/.config/tilenol`` before starting, as tilenol is
non-functional without a configuration.


