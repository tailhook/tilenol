from distutils.core import setup

setup(name='Tilenol',
      version='0.1',
      description='Window manager written in python with greenlets',
      author='Paul Colomiets',
      author_email='paul@colomiets.name',
      url='http://github.com/tailhook/tilenol',
      classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        ],
      packages=[
        'tilenol',
        'tilenol.xcb',
        'tilenol.layout',
        'tilenol.widgets',
        'tilenol.ext',
        'tilenol.gadgets',
        ],
      scripts=['runtilenol'],
    )
