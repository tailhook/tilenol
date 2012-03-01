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

    class right(Stack):
        limit = 1
        priority = 0  # probably roster created first
        # TODO(tailhook) implement window role matching


class Gimp(Split):

    class left(Stack):
        limit = 1
        weight = 1

    class center(Stack):
        weight = 4
        priority = 0

    class right(Stack):
        limit = 1
        weight = 2
