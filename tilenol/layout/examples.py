from .tile import Tile, Stack

class Tile2(Tile):

    class left(Stack):
        weight = 3
        priority = 0
        limit = 1

    class right(Stack):
        pass


class Max(Tile):

    class main(Stack):
        tile = False


class InstantMsg(Tile):

    class left(Stack):
        tile = True  # or maybe false?
        weight = 3

    class right(Stack):
        limit = 1
        priority = 0  # probably roster created first
        # TODO(tailhook) implement window role matching

