#!/usr/bin/env python2

import curses
import time
import random
import copy
import fcntl
import time
import itertools

random.seed()

class Glyph:
    def __init__(self,string,color):
        self.string = string
        self.color = curses.color_pair(color)

def draw(win, glyph, x, y):
    win.addstr(y, x, glyph.string, glyph.color)

class Wrapper:
    def __init__(self, value):
        self.value = value
    def get():
        return self.value
    def set(val):
        self.value = val
    
class Signal:
    def __init__(self):
        self.slots = []
    def __call__(self, *args):
        for slot in self.slots:
            slot(*args)
    def connect(self, cb):
        self.slots += [cb]

class Object(object):
    def __init__(self, name, glyph, world):
        self.name = name
        self.glyph = glyph
        self.x = 0
        self.y = 0
        self.world = world
        
        self.attach()

        self.on_try_move = Signal()
        self.on_collision = Signal()

    def draw(self, win):
        draw(win, self.glyph)
    def draw(self, win, x, y):
        draw(win, self.glyph, x, y)

    def attach(self):
        tile = self.world.tile(self.x,self.y)
        if tile and not self in tile.objects:
            tile.objects.append(self)
        
    def detach(self):
        tile = self.world.tile(self.x,self.y)
        if tile and self in tile.objects:
            tile.objects.remove(self)

    def attached(self):
        if not self.world:
            return False
        tile = self.world.tile(self.x,self.y)
        if not tile:
            return False
        return self in tile.objects

    def tick(self, t):
        pass

    def try_move(self, x, y):
        if not self.attached():
            return False
        
        target = self.world.tile(self.x + x, self.y + y)
        result = False
        if target and not target.solid:
            self.detach()
            self.x += x
            self.y += y
            self.attach()
            result = True

        self.on_try_move(x, y, result)

        if result and len(target.objects) > 1:
            post_signal = Signal()
            for p in itertools.combinations(target.objects, 2):
                p[0].on_collision(p[1], post_signal)
                p[1].on_collision(p[0], post_signal)
            post_signal()
    
    def move(self, x, y):
        self.detach()
        self.x += x
        self.y += y
        self.attach()

    def teleport(self, x, y):
        self.detach()
        self.x = x
        self.y = y
        self.attach()
        
class Player(Object):
    def __init__(self, name, glyph, world):
        super(self.__class__, self).__init__(name, glyph, world)
        self.hp = 100
        self.on_try_move.connect(self.orient)
        self.on_collision.connect(self.collision)
        self.dir = [0,1]
        self.last_target = ""
        self.gold = 0
        self.last_pickup = ""

    def collision(self, other, post_signal):
        if other.__class__.__name__ == 'Monster':
            self.hp = max(0, self.hp - 10)
        elif other.__class__.__name__ == 'Item':
            if other.name == 'gold coin':
                self.gold += 10
                self.last_pickup = other.name
                post_signal.connect(lambda:
                    other.detach()
                )

    def thinking(self):
        if self.hiding():
            return "I am hiding."
        if self.last_target:
            return "I see a %s." % self.last_target
        if self.last_pickup:
            return "Picked up %s." % self.last_pickup
        
        return ""
        
    def update_targets(self):
        tile = self.immediate_tile(self.dir[0], self.dir[1])
        target = ""
        if tile:
            if tile.objects:
                target = tile.objects[0].name
                self.last_target = target
                #self.last_pickup = None # clear pickup messages
            else:
                target = tile.name
                self.last_target = target
                if target:
                    self.last_pickup = None # clear pickup messages
        
        
    def current_tile(self):
        return self.world.tile(self.x, self.y)
    
    def immediate_tile(self, x, y):
        return self.world.tile(self.x + x,  self.y + y)
        
    def hiding(self):
        t = self.current_tile()
        return t and t.conceal
    
    def orient(self, x, y, result):
        if x > 0:
            self.glyph.string = '>'
        elif x < 0:
            self.glyph.string = '<'
        elif y < 0:
            self.glyph.string = '^'
        elif y > 0:
            self.glyph.string = 'v'

        self.dir = (x, y)

    def tick(self, t):
        self.update_targets()

class Item(Object):
    def __init__(self, name, glyph, world):
        super(self.__class__, self).__init__(name, glyph, world)

class Monster(Object):
    def __init__(self, name, glyph, world):
        super(self.__class__, self).__init__(name, glyph, world)
    def tick(self, t):
        if random.random() <= 0.1:
            self.try_move(random.randint(0,2) - 1, random.randint(0,2) - 1)

class Tile:
    def __init__(self, glyph, **kwargs):
        self.objects = []
        self.glyph = glyph
        self.properties(**kwargs)

    def properties(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.solid = kwargs.get("solid", False)
        self.conceal = kwargs.get("conceal", False)

class Map:
    def __init__(self, name, w, h, fill):
        self.name = name
        self.w = w
        self.h = h
        line = []
        self.grid = []
        for t in xrange(w):
            line.append(Tile(fill))
        for t in xrange(h):
            self.grid.append(copy.deepcopy(line))
    
    def tile(self, x, y):
        if x < 0 or y < 0:
            return None
        if x >= self.w or y >= self.h:
            return None
        return self.grid[y][x]
    
    def sprinkle(self, glyph, freq, **kwargs):
        i = 0
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
    
    BUSH = Glyph('*', 3)
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
    
    ROCK = Glyph('o', 4)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    TREE = Glyph('T', 5)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)

    MONSTER = Glyph("M", 6)
    curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)

    GOLD = Glyph('*', 7)
    curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    
    NOTHING = Glyph('X',10)
    curses.init_pair(10, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(11, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    world = Map("The Forest", 100, 100, GRASS)
    world.sprinkle(ROCK, 0.01, solid=True, name="rock")
    world.sprinkle(BUSH, 0.02, conceal=True, name="bush")
    world.sprinkle(TREE, 0.02, solid=True, name="tree")

    objects = []
    
    for i in xrange(int(0.01 * world.w * world.h)):
        p = Monster("monster", MONSTER, world)
        p.teleport(random.randint(0, world.w), random.randint(0, world.h))
        objects.append(p)
    
    for i in xrange(int(0.001 * world.w * world.h)):
        p = Item("gold coin", GOLD, world)
        p.teleport(random.randint(0, world.w), random.randint(0, world.h))
        objects.append(p)

    player = Player("Player", PLAYER, world)
    player.teleport(random.randint(0, world.w), random.randint(0, world.h))

    camera = [0,0]
    
    win.nodelay(1)
    t0 = time.time()
    accum = 0 # time accumulated since last tick
    
    FPS = 30.0
    FPS_INV = 1.0 / FPS
    
    while True:
        
        advance = 0
        while True:
            t1 = time.time()
            accum += t1 - t0
            t0 = t1
            if accum > FPS_INV:
                advance = FPS_INV
                accum = advance - accum # rollover excess time
                break
            time.sleep(0.001)
        
        win_sz = win.getmaxyx()[::-1]
        view = [1, 1, win_sz[0] - 2, win_sz[1] - 3]
        
        camera[0] = player.x - view[2]/2
        camera[1] = player.y - view[3]/2
        
        win.erase()

        for ix in xrange(0,view[2]):
            for iy in xrange(0,view[3]):
                tile = world.tile(ix + camera[0], iy + camera[1])
                if tile:
                    if not tile.objects or tile.conceal:
                        draw(win, tile.glyph, ix + view[0], iy + view[1])
                    else:
                        for obj in tile.objects:
                            draw(win, obj.glyph, ix + view[0], iy + view[1])
                else:
                    draw(win, NOTHING, ix + view[0], iy + view[1])
        
        t = player.thinking()
        if t:
            ft = " %s " % t 
            win.addstr(2, view[0] + view[2]/2 - len(t)/2, ft, curses.color_pair(11))
        
        win.addstr(view[1]+view[3], 1, world.name)
        
        status = "Gold: %s | HP %s / 100" % (player.gold, player.hp)
        win.addstr(view[1]+view[3], view[0]+view[2]-len(status), status)
        
        win.box()
        
        ch = win.getch()
        if ch == ord('q'):
            break
        
        if ch == ord('i') or ch == curses.KEY_UP:
            player.try_move(0,-1)
        elif ch == ord('k') or ch == curses.KEY_DOWN:
            player.try_move(0,1)
        elif ch == ord('j') or ch == curses.KEY_LEFT:
            player.try_move(-1,0)
        elif ch == ord('l') or ch == curses.KEY_RIGHT:
            player.try_move(1,0)

        player.tick(advance)
        
        objects = filter(lambda obj: obj.attached(), objects)
        for obj in objects:
            obj.tick(advance)

if __name__=='__main__':
    curses.wrapper(main)

