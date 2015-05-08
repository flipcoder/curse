#!/usr/bin/env python2

import curses
import time
import random
import copy

map = []

random.seed()

class Glyph:
    def __init__(self,string,color):
        self.string = string
        self.color = curses.color_pair(color)

def draw(win, glyph, x, y):
    win.addstr(y, x, glyph.string, glyph.color)

class Object(object):
    def __init__(self, glyph, world):
        self.glyph = glyph
        self.x = 0
        self.y = 0
        self.world = world
        
        self.attach()

    def draw(self, win):
        draw(win, self.glyph)
    def draw(self, win, x, y):
        draw(win, self.glyph, x, y)

    def attach(self):
        if not self in self.world.grid[self.x][self.y].objects:
            self.world.grid[self.x][self.y].objects.append(self)
        
    def detach(self):
        if self in self.world.grid[self.x][self.y].objects:
            self.world.grid[self.x][self.y].objects.remove(self)

    def move(self, x, y):
        target = self.world.tile(self.x + x, self.y + y)
        if target and not target.solid:
            self.detach()
            self.x += x
            self.y += y
            self.attach()

        if x > 0:
            self.glyph.string = '>'
        elif x < 0:
            self.glyph.string = '<'
        elif y < 0:
            self.glyph.string = '^'
        elif y > 0:
            self.glyph.string = 'v'

class Player(Object):
    def __init__(self, glyph, world):
        super(self.__class__, self).__init__(glyph, world)
        self.hp = 100

class Tile:
    def __init__(self, glyph, **kwargs):
        self.objects = []
        self.glyph = glyph
        self.properties(**kwargs)

    def properties(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.solid = kwargs.get("solid", False)

class Map:
    def __init__(self, name, w, h, fill):
        self.name = name
        self.w = w
        self.h = h
        line = []
        self.grid = []
        for t in xrange(h):
            line.append(Tile(fill))
        for t in xrange(w):
            self.grid.append(copy.deepcopy(line))
    
    def tile(self, x, y):
        if x < 0 or y < 0:
            return None
        if x >= self.w or y >= self.h:
            return None
        return self.grid[x][y]
    
    def sprinkle(self, glyph, freq, **kwargs):
        for row in self.grid:
            for tile in row:
                if random.random() <= freq:
                    tile.glyph = glyph
                    tile.properties(**kwargs)

def main(win):
    curses.curs_set(0)
    
    PLAYER = Glyph('v',1)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    
    GRASS = Glyph('.',2)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    
    SHRUB = Glyph('*', 3)
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
    
    ROCK = Glyph('o', 4)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    TREE = Glyph('T', 5)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)

    NOTHING = Glyph('X',10)
    curses.init_pair(10, curses.COLOR_RED, curses.COLOR_BLACK)

    world = Map("The Forest", 100, 100, GRASS)
    world.sprinkle(ROCK, 0.01, solid=True, name="rock")
    world.sprinkle(SHRUB, 0.02, solid=True, name="shrub")
    world.sprinkle(TREE, 0.02, solid=True, name="tree")
    
    player = Player(PLAYER, world)

    #win.nodelay(1)
    camera = [0,0]
    while True:
        
        win_sz = win.getmaxyx()[::-1]
        view = [1, 1, win_sz[0] - 2, win_sz[1] - 3]
        
        camera[0] = player.x - view[2]/2
        camera[1] = player.y - view[3]/2
        
        win.erase()
        
        for ix in xrange(0,view[2]):
            for iy in xrange(0,view[3]):
                tile = world.tile(ix + camera[0], iy + camera[1])
                if tile:
                    if not tile.objects:
                        draw(win, tile.glyph, ix + view[0], iy + view[1])
                    else:
                        for obj in tile.objects:
                            draw(win, obj.glyph, ix + view[0], iy + view[1])
                else:
                    draw(win, NOTHING, ix + view[0], iy + view[1])
        
        win.addstr(view[1]+view[3], 1, world.name)
        
        status = "HP %s / 100" % player.hp
        win.addstr(view[1]+view[3], view[0]+view[2]-len(status), status)
        
        #player.draw(win)
        win.box()
        
        ch = win.getch()
        if ch == ord('q'):
            break
        
        if ch == ord('i') or ch == curses.KEY_UP:
            player.move(0,-1)
        elif ch == ord('k') or ch == curses.KEY_DOWN:
            player.move(0,1)
        elif ch == ord('j') or ch == curses.KEY_LEFT:
            player.move(-1,0)
        elif ch == ord('l') or ch == curses.KEY_RIGHT:
            player.move(1,0)

if __name__=='__main__':
    curses.wrapper(main)

