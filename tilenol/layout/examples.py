from .tile import Split, Stack, TileStack


class Tile(Split):

    class left(Stack):
        weight = 3
        priority = 0
        limit = 1

    class right(TileStack):
        pass


class Max(Split):

    class main(Stack):
        tile = False


class InstantMsg(Split):

    class left(TileStack): # or maybe not tiled ?
        weight = 3

    class roster(Stack):
        limit = 1
        priority = 0  # probably roster created first


class Gimp(Split):

    class toolbox(Stack):
        limit = 1
        size = 184

    class main(Stack):
        weight = 4
        priority = 0

    class dock(Stack):
        limit = 1
        size = 324
