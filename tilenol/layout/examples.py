from .tile import Tile, Stack

class Tile2(Tile):

    class left(Stack):
        weight = 3
        priority = 0
        limit = 1

    class right(Stack):
        pass


