#!/usr/bin/env python2

import curses
import time
import random
import copy
import time
import itertools

random.seed()

class Glyph:
    def __init__(self,name,string,color,**kwargs):
        self.name = name
        self.string = string
        self.color = curses.color_pair(color)
        self.plural = kwargs.get("plural", False)

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
    def __init__(self, name, glyph, world, **kwargs):
        assert name
        self.name = name
        assert glyph
        self.glyph = glyph
        assert world
        self.world = world
        self.properties(**kwargs)

        self.on_try_move = Signal()
        self.on_collision = Signal()

    def draw(self, win):
        draw(win, self.glyph, self.x, self.y)
        
    def draw(self, win, x, y):
        draw(win, self.glyph, x, y)

    def tile_pos(self):
        if isinstance(self.x, int):
            return (self.x, self.y)
        else:
            return (int(round(self.x), int(round(self.y))))
        
    def properties(self, **kwargs):
        self.plural = kwargs.get("plural", False)
        self.obvious = kwargs.get("obvious", False)
        
        if "pos" in kwargs:
            (self.x, self.y) = kwargs["pos"]
        else:
            self.x = kwargs.get("x", 0)
            self.y = kwargs.get("y", 0)
        
        (self.vx, self.vy) = kwargs.get("vel", (0,0))
        self.vx *= 1.0
        self.vy *= 1.0

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

    def can_pass(self, x, y):
        t = tile(x,y)
        return t and self.can_pass(t)
        
    def can_pass(self, tile):
        assert tile
        return not tile.solid
        
    def move(self, x, y):
        assert self.attached()
        self.detach()
        self.x += x
        self.y += y
        self.attach()
        
    def try_move(self, x, y):
        assert self.attached()
        
        target = self.immediate_tile(x, y)
        result = False
        if target and self.can_pass(target):
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

        assert self.attached()
        return result
    
    def move(self, x, y):
        assert self.attached()
        self.detach()
        self.x += x
        self.y += y
        self.attach()

    def teleport(self, x, y):
        self.detach()
        self.x = x
        self.y = y
        self.attach()

    def random_teleport(self):
        done = False
        use_floats = isinstance(self.x, float)
        while True:
            # pick a random tile
            rx = random.randint(0, self.world.w - 1)
            ry = random.randint(0, self.world.h - 1)
            t = self.world.tile(rx, ry)
            assert t
            
            # attempt to nudge it a few times into a non-solid area
            attempts = 0
            while attempts < 20:
                if self.can_pass(t) and not t.objects:
                    done = True
                    break
                
                rx += random.randint(0,2)-1
                ry += random.randint(0,2)-1
                (rx, ry) = self.world.snap(rx, ry)
                t = self.world.tile(rx, ry)
                attempts += 1
            
            if done:
                break
        
        if use_floats:
            self.teleport(rx * 1.0,ry * 1.0)
        else:
            self.teleport(rx,ry)

        
    def current_tile(self):
        assert self.attached()
        return self.world.tile(self.x, self.y)
    
    def immediate_tile(self, x, y):
        assert self.attached()
        return self.world.tile(self.x + x,self.y + y)
        
class Player(Object):
    def __init__(self, name, glyph, world, **kwargs):
        super(self.__class__, self).__init__(name, glyph, world, **kwargs)
        self.hp = 100
        self.on_try_move.connect(self.orient)
        self.on_collision.connect(self.collision)
        self.dir = [0,1]
        self.last_target = ""
        self.gold = 0
        self.last_pickup = ""
        self.obvious = False

    def collision(self, other, post_signal):
        if other.__class__.__name__ == 'Monster':
            self.hp = max(0, self.hp - 25)
        elif other.__class__.__name__ == 'Item':
            if other.name == 'gold coin':
                self.gold += 10
                self.last_pickup = other.name
                post_signal.connect(lambda:
                    other.detach()
                )
            elif other.name == 'health kit':
                #self.hp += min(self.hp + 25, 100)
                self.hp = 100
                self.last_pickup = other.name
                post_signal.connect(lambda:
                    other.detach()
                )

    def thinking(self):
        if self.hiding():
            return "I am hiding."
        if self.last_target:
            return "I see %s." % self.last_target
        if self.last_pickup:
            return "Picked up %s." % self.last_pickup
        
        return ""
        
    def update_targets(self):
        tile = self.immediate_tile(self.dir[0], self.dir[1])
        target = ""
        if tile:
            objs = filter(lambda o: not o.obvious, tile.objects)
            if objs:
                target = self.last_target = \
                    ("" if objs[0].plural else "a ") + \
                    objs[0].name
            elif not tile.obvious:
                target = self.last_target = \
                    ("" if tile.plural else "a ") + \
                    tile.name
        if target:
            self.last_pickup = None # clear pickup messages
        else:
            self.last_target = ""

    def hiding(self):
        t = self.current_tile()
        return t and t.conceal

    def shoot(self):
        speed = 20.0
        self.world.spawn(
            "bullet",
            pos=(1.0*(self.x + self.dir[0]), 1.0*(self.y + self.dir[1])),
            vel=(self.dir[0]*1.0*speed,self.dir[1]*1.0*speed)
        )
    
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

class Bullet(Object):
    def __init__(self, name, glyph, world, **kwargs):
        super(self.__class__, self).__init__(name, glyph, world, **kwargs)
        self.obvious = True
    def tick(self, t):
        self.move(self.vx * t, self.vy * t)
    
class Item(Object):
    def __init__(self, name, glyph, world, **kwargs):
        super(self.__class__, self).__init__(name, glyph, world, **kwargs)

class Monster(Object):
    def __init__(self, name, glyph, world, **kwargs):
        super(self.__class__, self).__init__(name, glyph, world, **kwargs)
        self.speed = kwargs.get("speed", 0.0)
    def tick(self, t):
        if not self.attached():
            return
        speed = self.speed * t
        while speed > 0.0:
            if random.random() <= min(speed, 1.0):
                self.try_move(random.randint(0,2) - 1, random.randint(0,2) - 1)
            speed -= 1.0
    def can_pass(self, tile):
        # prevent monsters from moving over tiles that can conceal player
        return super(self.__class__, self).can_pass(tile) and not tile.conceal

class Tile:
    def __init__(self, glyph, **kwargs):
        self.objects = []
        name = kwargs.get("name", "")
        if not name:
            self.name = glyph.name
        self.glyph = glyph
        self.properties(**kwargs)

    def properties(self, **kwargs):
        self.solid = kwargs.get("solid", False)
        self.plural = kwargs.get("plural", False)
        self.conceal = kwargs.get("conceal", False)
        self.obvious = kwargs.get("obvious", False)
        self.theme = kwargs.get("theme", "")

class Map:
    def __init__(self, name, w, h, fill):
        self.name = name
        self.w = w
        self.h = h
        line = []
        self.grid = []
        for t in xrange(w):
            line.append(Tile(fill, obvious=True))
        for t in xrange(h):
            self.grid.append(copy.deepcopy(line))
        
        self.nothing_glyph = None
        
        self.glyphs = {}
        self.glyphs[fill.name] = fill
        
        self.objects = []
        self.object_factories = {}
    
    def tile(self, x, y):
        (x,y) = (int(round(x)),int(round(y)))
        if x < 0 or y < 0:
            return None
        if x >= self.w or y >= self.h:
            return None
        return self.grid[y][x]
    
    #def structure(self, **kwargs):
    #    doors = kwargs["doors"]
    #    wall = kwargs["wall"]
    #    floor = kwargs.get("floor", None)

    def sprinkle(self, T, freq, **kwargs):
        try:
            if T.__class__.__name__ == Glyph.__name__:
                # T is a Glyph
                self.sprinkle_tile(T, freq, **kwargs)
                return
        except:
            pass
        
        # T is an object factory
        return self.sprinkle_object(T, freq, **kwargs)
        
    def sprinkle_tile(self, glyph, freq, **kwargs):
        i = 0
        for row in self.grid:
            for tile in row:
                if random.random() <= freq:
                    tile.glyph = glyph
                    tile.name = glyph.name
                    tile.properties(**kwargs)
    
    # factory must be:
    #   - a function returning a new object
    #   OR
    #   - name of factory registered with World.register_object_factory()
    # freq can be:
    #   - an integer >=1, for exact number of objects
    #   OR
    #   - float, decimal between 0 and 1, for likelihood of occurrence
    def sprinkle_object(self, factory, freq, **kwargs):
        r = []
        if int(freq) >= 1: # treat freq as object count
            count = int(freq)
        else: # treat freq as likelihood
            count = int(freq * self.w * self.h)
        
        if isinstance(factory, basestring):
            factory = object_factories[factory]
        
        for i in xrange(count):
            p = factory(**kwargs)
            self.ensure_object(p)
            p.random_teleport()
            r.append(p)
        return r

    def spawn(self, name, **kwargs):
        p = self.object_factories[name](**kwargs)
        self.ensure_object(p)
        p.attach()
        return p

    def ensure_object(self, p):
        if p not in self.objects:
            self.objects.append(p)
        
    def snap(self, x, y):
        use_floats = isinstance(x, float)
        
        if use_floats:
            x = max(0.0, min(x, self.w*1.0 - 1.0))
            y = max(0.0, min(y, self.h*1.0 - 1.0))
        else:
            x = max(0, min(x, self.w-1))
            y = max(0, min(y, self.h-1))

        return (x,y)

    def set_nothing_glyph(self, glyph):
        self.nothing = glyph
        
    def glyph(self, *args):
        if len(args) == 1:
            return self.glyphs[args[0]]
        g = Glyph(*args)
        self.glyphs[g.name] = g
        if g.name == 'nothing':
            self.nothing_glyph = g
        return g

    # factory prototype is T(name, glyph, world, **kwargs)
    #   where T is Object or derived class of Object
    def register_object_factory(self, name, factory):
        self.object_factories[name] = factory
        
    def render(self, win, camera, view):
        # render visible map region based on camera and viewport
        for ix in xrange(0,view[2]):
            for iy in xrange(0,view[3]):
                # adding camera coords transforms us into world space
                # use world space coords to get tile, null if out of range
                tile = self.tile(ix + camera[0], iy + camera[1])
                if tile:
                    # if tile has no objects or is concealing them
                    if not tile.objects or tile.conceal:
                        draw(win, tile.glyph, ix + view[0], iy + view[1])
                    else:
                        # draw first object
                        for obj in tile.objects:
                            draw(win, obj.glyph, ix + view[0], iy + view[1])
                            break
                else:
                    # tile is out of range, draw placeholders
                    if self.nothing_glyph:
                        draw(win, self.nothing_glyph, ix + view[0], iy + view[1])

def main(win):
    curses.curs_set(0)
    
    while True:
        msg = game(win)
        if not msg:
            break
        
        win_sz = win.getmaxyx()[::-1]
        msg = " %s -- (r)etry / (q)uit? " % msg
        win.addstr(win_sz[1]/2, win_sz[0]/2 - len(msg)/2, msg)
        win.refresh()
        
        op = ""
        
        time.sleep(.100)
        
        while not op:
            op = win.getch()
            if op in [ord('q'), ord('r')]:
                break
            else:
                op = ""
        
        if op == ord('q'):
            break
        elif op == ord('r'):
            continue

def interface_logic(win, player):
    ch = win.getch()
    if ch == ord('q'):
        return False
    
    # interface logic
    if ch == ord('i') or ch == curses.KEY_UP:
        player.try_move(0,-1)
    elif ch == ord('k') or ch == curses.KEY_DOWN:
        player.try_move(0,1)
    elif ch == ord('j') or ch == curses.KEY_LEFT:
        player.try_move(-1,0)
    elif ch == ord('l') or ch == curses.KEY_RIGHT:
        player.try_move(1,0)
    elif ch == ord(' '):
        player.shoot()
    return True

def hud_render(win, view, player):
    t = player.thinking()
    if t:
        ft = " %s " % t 
        win.addstr(2, view[0] + view[2]/2 - len(t)/2, ft, curses.color_pair(11))
    win.addstr(view[1]+view[3], 1, player.world.name)
    status = "Gold: %s | HP %s / 100" % (player.gold, player.hp)
    win.addstr(view[1]+view[3], view[0]+view[2]-len(status), status)

def game(win):
    win_sz = win.getmaxyx()[::-1]
    win.clear()
    win.box()
    
    text = "Loading..."
    win.addstr(win_sz[1]/2, win_sz[0]/2 - len(text)/2, text)
    win.refresh()
    
    PLAYER = Glyph('player', 'v', 1)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    GRASS = Glyph('grass', '.',2,plural=True)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    world = Map("The Forest", 300, 300, GRASS)
    
    BUSH = world.glyph('bush', '*', 3)
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
    
    ROCK = world.glyph('rock', 'o', 4)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    TREE = world.glyph('tree', 'T', 5)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)

    MONSTER = world.glyph('monster', "M", 6)
    curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)

    GOLD = world.glyph('gold', '*', 7)
    curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    HEALTH = world.glyph('health', "+", 8)
    curses.init_pair(8, curses.COLOR_RED, curses.COLOR_WHITE)

    BULLET = world.glyph('bullet', "\'", 9)
    curses.init_pair(9, curses.COLOR_RED, curses.COLOR_BLACK)

    DOOR_H = world.glyph('door_h', '-', 4)
    DOOR_V = world.glyph('door_v', '|', 4)
    WALL = world.glyph('wall', 'H', 4)
    FENCE = world.glyph('fence', '#', 4)
    
    NOTHING = world.glyph('nothing', 'X',10)

    world.sprinkle(ROCK, 0.01, solid=True)
    world.sprinkle(BUSH, 0.02, conceal=True)
    world.sprinkle(TREE, 0.02, solid=True)
    
    curses.init_pair(10, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(11, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    #world.structure(
    #    theme="inside"
    #    wall=WALL,
    #    doors=[DOOR_H,DOOR_V],
    #    flor=[FLOOR]
    #)

    world.sprinkle(
        lambda **kwargs: Monster("monster", MONSTER, world, speed=random.random()*1.0, **kwargs),
        0.01
    )
    world.sprinkle(
        lambda **kwargs: Item("gold coin", GOLD, world, **kwargs),
        0.001
    )
    world.sprinkle(
        lambda **kwargs: Item("health kit", HEALTH, world, **kwargs),
        0.0001
    )
    world.register_object_factory(
        "bullet",
        lambda **kwargs: Bullet("bullet", BULLET, world, **kwargs)
    )

    player = Player("Player", copy.deepcopy(PLAYER), world)
    player.random_teleport()

    camera = [0,0]
    
    win.nodelay(1)
    
    # init timer
    t0 = time.time()
    accum = 0 # time accumulated since last tick
    
    FPS = 15.0
    FPS_INV = 1.0 / FPS
    
    while True:
        
        # advance timer at a fixed framerate
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
        
        # calculate view and camera values based on term size
        win_sz = win.getmaxyx()[::-1] # window size (in chars)
        view = [1, 1, win_sz[0] - 2, win_sz[1] - 3] # (view x,y,w,h)

        # x,y position where to start rendering our map
        camera = [player.x - view[2]/2, player.y - view[3]/2]
        
        win.erase()

        world.render(win, camera, view)

        # draw HUD
        hud_render(win, view, player)
        
        # draw border
        win.box()
        win.refresh()
        
        if not interface_logic(win, player):
            return "" # user quit
        
        player.tick(advance)

        # object logic
        world.objects = filter(lambda obj: obj.attached(), world.objects)
        for obj in world.objects:
            obj.tick(advance)
        
        # game state termination
        if player.hp <= 0:
            return "You are dead."

if __name__=='__main__':
    curses.wrapper(main)

