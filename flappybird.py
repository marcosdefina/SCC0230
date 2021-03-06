#! /usr/bin/env python3

"""Flappy Bird, implemented using Pygame."""

import sys
import math
import os
from random import randint
from collections import deque

import pygame
from pygame.locals import *


FPS = 60
ANIMATION_SPEED = 0.18  # pixels per millisecond
WIN_WIDTH = 284 * 2     # BG image size: 284x512 px; tiled twice
WIN_HEIGHT = 512
BIRD_X=50

class Bird(pygame.sprite.Sprite):
    """Represents the bird controlled by the player.

    The bird is the 'hero' of this game.  The player can make it climb
    (ascend quickly), otherwise it sinks (descends more slowly).  It must
    pass through the space in between pipes (for every pipe passed, one
    point is scored); if it crashes into a pipe, the game ends.

    Attributes:
    x: The bird's X coordinate.
    y: The bird's Y coordinate.
    msec_to_climb: The number of milliseconds left to climb, where a
        complete climb lasts Bird.CLIMB_DURATION milliseconds.

    Constants:
    WIDTH: The width, in pixels, of the bird's image.
    HEIGHT: The height, in pixels, of the bird's image.
    SINK_SPEED: With which speed, in pixels per millisecond, the bird
        descends in one second while not climbing.
    CLIMB_SPEED: With which speed, in pixels per millisecond, the bird
        ascends in one second while climbing, on average.  See also the
        Bird.update docstring.
    CLIMB_DURATION: The number of milliseconds it takes the bird to
        execute a complete climb.
    """

    WIDTH = HEIGHT = 32
    SINK_SPEED = 0.2
    CLIMB_SPEED = 0.3
    CLIMB_DURATION = 200

    def __init__(self, x, y, msec_to_climb, images, done=1):
        """Initialise a new Bird instance.

        Arguments:
        x: The bird's initial X coordinate.
        y: The bird's initial Y coordinate.
        msec_to_climb: The number of milliseconds left to climb, where a
            complete climb lasts Bird.CLIMB_DURATION milliseconds.  Use
            this if you want the bird to make a (small?) climb at the
            very beginning of the game.
        images: A tuple containing the images used by this bird.  It
            must contain the following images, in the following order:
                0. image of the bird with its wing pointing upward
                1. image of the bird with its wing pointing downward
        """
        super(Bird, self).__init__()
        self.x, self.y = x, y
        self.msec_to_climb = msec_to_climb
        self._img_wingup, self._img_wingdown = images
        self._mask_wingup = pygame.mask.from_surface(self._img_wingup)
        self._mask_wingdown = pygame.mask.from_surface(self._img_wingdown)

    def update(self, delta_frames=1):
        """Update the bird's position.

        This function uses the cosine function to achieve a smooth climb:
        In the first and last few frames, the bird climbs very little, in the
        middle of the climb, it climbs a lot.
        One complete climb lasts CLIMB_DURATION milliseconds, during which
        the bird ascends with an average speed of CLIMB_SPEED px/ms.
        This Bird's msec_to_climb attribute will automatically be
        decreased accordingly if it was > 0 when this method was called.

        Arguments:
        delta_frames: The number of frames elapsed since this method was
            last called.
        """
        if self.msec_to_climb > 0:
            frac_climb_done = 1 - self.msec_to_climb/Bird.CLIMB_DURATION
            self.y -= (Bird.CLIMB_SPEED * frames_to_msec(delta_frames) *
                       (1 - math.cos(frac_climb_done * math.pi)))
            self.msec_to_climb -= frames_to_msec(delta_frames)
        else:
            self.y += Bird.SINK_SPEED * frames_to_msec(delta_frames)

    @property
    def image(self):
        """Get a Surface containing this bird's image.

        This will decide whether to return an image where the bird's
        visible wing is pointing upward or where it is pointing downward
        based on pygame.time.get_ticks().  This will animate the flapping
        bird, even though pygame doesn't support animated GIFs.
        """
        if pygame.time.get_ticks() % 500 >= 250:
            return self._img_wingup
        else:
            return self._img_wingdown

    @property
    def mask(self):
        """Get a bitmask for use in collision detection.

        The bitmask excludes all pixels in self.image with a
        transparency greater than 127."""
        if pygame.time.get_ticks() % 500 >= 250:
            return self._mask_wingup
        else:
            return self._mask_wingdown

    @property
    def rect(self):
        """Get the bird's position, width, and height, as a pygame.Rect."""
        return Rect(self.x, self.y, Bird.WIDTH, Bird.HEIGHT)


class PipePair(pygame.sprite.Sprite):
    """Represents an obstacle.

    A PipePair has a top and a bottom pipe, and only between them can
    the bird pass -- if it collides with either part, the game is over.

    Attributes:
    x: The PipePair's X position.  This is a float, to make movement
        smoother.  Note that there is no y attribute, as it will only
        ever be 0.
    image: A pygame.Surface which can be blitted to the display surface
        to display the PipePair.
    mask: A bitmask which excludes all pixels in self.image with a
        transparency greater than 127.  This can be used for collision
        detection.
    top_pieces: The number of pieces, including the end piece, in the
        top pipe.
    bottom_pieces: The number of pieces, including the end piece, in
        the bottom pipe.

    Constants:
    WIDTH: The width, in pixels, of a pipe piece.  Because a pipe is
        only one piece wide, this is also the width of a PipePair's
        image.
    PIECE_HEIGHT: The height, in pixels, of a pipe piece.
    ADD_INTERVAL: The interval, in milliseconds, in between adding new
        pipes.
    """

    WIDTH = 80
    PIECE_HEIGHT = 32
    ADD_INTERVAL = 3000

    def __init__(self, pipe_end_img, pipe_body_img, pipenum):
        """Initialises a new PipePair.

        The new PipePair will automatically be assigned an x attribute of
        float(WIN_WIDTH - 1).

        Arguments:
        pipe_end_img: The image to use to represent a pipe's end piece.
        pipe_body_img: The image to use to represent one horizontal slice
            of a pipe's body.
        """
        self.x = float(WIN_WIDTH - 1)
        self.score_counted = False

        self.image = pygame.Surface((PipePair.WIDTH, WIN_HEIGHT), SRCALPHA)
        self.image.convert()   # speeds up blitting
        self.image.fill((0, 0, 0, 0))
        total_pipe_body_pieces = int(
            (WIN_HEIGHT -                  # fill window from top to bottom
             3 * Bird.HEIGHT -             # make room for bird to fit through
             3 * PipePair.PIECE_HEIGHT) /  # 2 end pieces + 1 body piece
            PipePair.PIECE_HEIGHT          # to get number of pipe pieces
        )
        self.bottom_pieces = pipenum
        self.top_pieces = total_pipe_body_pieces - self.bottom_pieces

        # bottom pipe
        for i in range(1, self.bottom_pieces + 1):
            piece_pos = (0, WIN_HEIGHT - i*PipePair.PIECE_HEIGHT)
            self.image.blit(pipe_body_img, piece_pos)
        bottom_pipe_end_y = WIN_HEIGHT - self.bottom_height_px
        bottom_end_piece_pos = (0, bottom_pipe_end_y - PipePair.PIECE_HEIGHT)
        self.image.blit(pipe_end_img, bottom_end_piece_pos)

        # top pipe
        for i in range(self.top_pieces):
            self.image.blit(pipe_body_img, (0, i * PipePair.PIECE_HEIGHT))
        top_pipe_end_y = self.top_height_px
        self.image.blit(pipe_end_img, (0, top_pipe_end_y))

        # compensate for added end pieces
        self.top_pieces += 1
        self.bottom_pieces += 1

        # for collision detection
        self.mask = pygame.mask.from_surface(self.image)

    @property
    def top_height_px(self):
        """Get the top pipe's height, in pixels."""
        return self.top_pieces * PipePair.PIECE_HEIGHT

    @property
    def bottom_height_px(self):
        """Get the bottom pipe's height, in pixels."""
        return self.bottom_pieces * PipePair.PIECE_HEIGHT

    @property
    def visible(self):
        """Get whether this PipePair on screen, visible to the player."""
        return -PipePair.WIDTH < self.x < WIN_WIDTH

    @property
    def rect(self):
        """Get the Rect which contains this PipePair."""
        return Rect(self.x, 0, PipePair.WIDTH, PipePair.PIECE_HEIGHT)

    def update(self, delta_frames=1):
        """Update the PipePair's position.

        Arguments:
        delta_frames: The number of frames elapsed since this method was
            last called.
        """
        self.x -= ANIMATION_SPEED * frames_to_msec(delta_frames)

    def collides_with(self, bird):
        """Get whether the bird collides with a pipe in this PipePair.

        Arguments:
        bird: The Bird which should be tested for collision with this
            PipePair.
        """
        return pygame.sprite.collide_mask(self, bird)


def load_images():
    """Load all images required by the game and return a dict of them.

    The returned dict has the following keys:
    background: The game's background image.
    bird-wingup: An image of the bird with its wing pointing upward.
        Use this and bird-wingdown to create a flapping bird.
    bird-wingdown: An image of the bird with its wing pointing downward.
        Use this and bird-wingup to create a flapping bird.
    pipe-end: An image of a pipe's end piece (the slightly wider bit).
        Use this and pipe-body to make pipes.
    pipe-body: An image of a slice of a pipe's body.  Use this and
        pipe-body to make pipes.
    """

    def load_image(img_file_name):
        """Return the loaded pygame image with the specified file name.

        This function looks for images in the game's images folder
        (./images/).  All images are converted before being returned to
        speed up blitting.

        Arguments:
        img_file_name: The file name (including its extension, e.g.
            '.png') of the required image, without a file path.
        """
        file_name = os.path.join('.', 'images', img_file_name)
        img = pygame.image.load(file_name)
        img.convert()
        return img

    return {'background': load_image('background.png'),
            'pipe-end': load_image('pipe_end.png'),
            'pipe-body': load_image('pipe_body.png'),
            # images for animating the flapping bird -- animated GIFs are
            # not supported in pygame
            'bird-wingup': load_image('bird_wing_up.png'),
            'bird-wingdown': load_image('bird_wing_down.png'),
            'bird2-wingup':load_image('bird2_wing_up.png') ,
            'bird2-wingdown':load_image('bird2_wing_down.png')}


def frames_to_msec(frames, fps=FPS):
    """Convert frames to milliseconds at the specified framerate.

    Arguments:
    frames: How many frames to convert to milliseconds.
    fps: The framerate to use for conversion.  Default: FPS.
    """
    return 1000.0 * frames / fps


def msec_to_frames(milliseconds, fps=FPS):
    """Convert milliseconds to frames at the specified framerate.

    Arguments:
    milliseconds: How many milliseconds to convert to frames.
    fps: The framerate to use for conversion.  Default: FPS.
    """
    return fps * milliseconds / 1000.0


def main():
    """The application's entry point.

    If someone executes this module (instead of importing it, for
    example), this function is called.
    """

    pygame.init()

    display_surface = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
    pygame.display.set_caption('Pygame Flappy Bird')

    clock = pygame.time.Clock()
    score=0
    score_font = pygame.font.SysFont(None, 32, bold=True)  # default font
    images = load_images()
    
    # the bird stays in the same x position, so bird.x is a constant
    # Create birds and center them on screen
    if len(sys.argv)>1:
      birdnum=int(sys.argv[1])
    else:
      birdnum=250
    if len(sys.argv)>2:
      player=int(sys.argv[2])
    else:
      player=0
    birds=[]
    autoinput=[]
    if player:
      bird=Bird(BIRD_X, int(WIN_HEIGHT/2 - Bird.HEIGHT/2), 2,
                (images['bird2-wingup'], images['bird2-wingdown']))
    for i in range(birdnum):
      birds.append(Bird(BIRD_X, int(WIN_HEIGHT/2 - Bird.HEIGHT/2), 2,
                (images['bird-wingup'], images['bird-wingdown'])))
      autoinput.append(ai())
    pipes = deque()
    PS=(5, 4, 8, 3, 8, 7, 3, 2, 6, 5) #preset pipe size
    end=0
    firstcheck=1
    restart=1
    while end==0: # Make game restart with collision
        restart=1
        for i in autoinput:
          if i.done<restart:
            restart=i.done

        if restart==1 and (player==0 or player==-1 or firstcheck):
          if player:
            bird=Bird(50, int(WIN_HEIGHT/2 - Bird.HEIGHT/2), 2,
              (images['bird2-wingup'], images['bird2-wingdown']), 0)
            bird.score=0
            player=1
          score=0
          paused = 0
          for i in range(len(birds)):
            autoinput[i].done=0
            autoinput[i].deathprocessed=0
            birds[i] = Bird(50, int(WIN_HEIGHT/2 - Bird.HEIGHT/2), 2,
            (images['bird-wingup'], images['bird-wingdown']), 0)
            if firstcheck==0:
              autoinput[i].resetvar(autoinput[i].score)
              autoinput[i].score=0
          if firstcheck:
            firstcheck=0
          pipes=deque() # Make pipes vanish
          pscount=0 # Reset pipesize index to make them the same every time
          frame_clock = 0  # this counter is only incremented if the game isn't paused
          best=0
          bestindex=-1
          for i in range(len(autoinput)):
            if autoinput[i].best[0]>best:
              bestindex=i
              best=autoinput[i].best[0]
          if best>0:
            for i in autoinput:
              if i.best[0]<best:
                i.best=autoinput[bestindex].best
          best=2
          bestindex=-1
          for i in range(len(autoinput)):
            if autoinput[i].best[1]<best:
              bestindex=i
              best=autoinput[i].best[1]
          if best<2:
            for i in autoinput:
              if i.best[1]>best:
                i.best=autoinput[bestindex].best
          for i in autoinput:
            i.resetvar(i.score)

        clock.tick(FPS)
        # Handle this 'manually'.  If we used pygame.time.set_timer(),
        # pipe addition would be messed up when paused.
        if not (paused or frame_clock % msec_to_frames(PipePair.ADD_INTERVAL)):
            pp = PipePair(images['pipe-end'], images['pipe-body'], PS[pscount])
            pscount+=1
            if pscount==10:
              pscount=0
            pipes.append(pp)

        for e in pygame.event.get():
            if e.type == KEYUP and e.key == K_ESCAPE: #Get game to quit only when key is pressed
                end = True
            if e.type == QUIT or (e.type == KEYUP and e.key == K_ESCAPE):
                done = True
                break
            elif e.type == KEYUP and e.key in (K_PAUSE, K_p):
                paused = not paused
            elif e.type == MOUSEBUTTONUP or (e.type == KEYUP and
                    e.key in (K_UP, K_RETURN, K_SPACE)):
                      if player:
                        bird.msec_to_climb = Bird.CLIMB_DURATION

        if paused:
            continue  # don't draw anything

        # check for collisions
        for i in range(len(birds)):
          pipe_collision = any(p.collides_with(birds[i]) for p in pipes)
          if autoinput[i].deathprocessed==0 and (pipe_collision or 0 >= birds[i].y or birds[i].y >= WIN_HEIGHT - Bird.HEIGHT):
            autoinput[i].deathprocessed=1
            birds[i].x=-100
            autoinput[i].done = True
            if pipe_collision:
              if birds[i].rect[1]>(pipes[0].top_pieces-1)*pipes[0].PIECE_HEIGHT and birds[i].rect[1]<WIN_HEIGHT-(pipes[0].bottom_pieces)*pipes[0].PIECE_HEIGHT: # If collision is with pipe head
                autoinput[i].deathtype=0
              else:
                autoinput[i].deathtype=1
            else:
              autoinput[i].deathtype=2
        for x in (0, WIN_WIDTH / 2):
            display_surface.blit(images['background'], (x, 0))

        if player:
          pipe_collision = any(p.collides_with(bird) for p in pipes)
          if pipe_collision or 0 >= bird.y or bird.y >= WIN_HEIGHT - Bird.HEIGHT:
            bird.x=-100
            player=-1

        while pipes and not pipes[0].visible:
            pipes.popleft()

        for p in pipes:
            p.update()
            display_surface.blit(p.image, p.rect)

        for i in birds:
          i.update()
          display_surface.blit(i.image, i.rect)
        if player:
          bird.update()
          display_surface.blit(bird.image, bird.rect)

        # update and display score
        for p in pipes:
            if p.x + PipePair.WIDTH < BIRD_X and not p.score_counted:
                for i in range(len(birds)):
                  if autoinput[i].done==0:
                    autoinput[i].score += 1
                    autoinput[i].scorecount()
                score+=1
                p.score_counted = True
        score_surface = score_font.render(str(score), True, (255, 255, 255))
        score_x = WIN_WIDTH/2 - score_surface.get_width()/2
        display_surface.blit(score_surface, (score_x, PipePair.PIECE_HEIGHT))

        pygame.display.flip()
        frame_clock += 1

        # Machine learning call
        for i in range(len(birds)):
          if autoinput[i].done==0:
            fly=autoinput[i].play()
            if fly==1:
              birds[i].msec_to_climb=Bird.CLIMB_DURATION

    finalscore=[]
    for i in autoinput:
      finalscore.append(i.best[0])
    print('Game over! Highest score: ', max(finalscore))
    pygame.quit()

class ai:
  def __init__(self):
    # AI input variables - 0 is current, 1 is best, 5 is fifth best
    self.curr=[0, 2, 0] # First index is score, second is type of death, third is index number until last score change, following are bird movements
    self.best=[0, 2, 0] # Types of death are 2 for off screen, 1 for side of pipe, 0 for top or bottom or pipe
    self.count=2
    self.compframe=0
    self.deathtype = 2
    self.deathprocessed = 0
    self.done = 1
    self.score = 0

  def resetvar(self, score):
    self.curr[0]=score
    self.curr[1]=self.deathtype
    # Compare curr with best, see which is better
    if self.curr[0]>self.best[0]:
      self.best=self.curr[:]
      self.compframe=self.count
    elif self.curr[0]==self.best[0]:
      if self.curr[1]<self.best[1]:
        self.best=self.curr[:]
        self.compframe=self.count
    self.curr=self.best[:]
    self.count=2

  def play(self):
    if self.best == [0, 2, 0] or self.count>len(self.curr)-1:
      self.curr.append(randint(0,25)) # Randomize and append
    elif self.count>self.best[2]:
      if self.best[1]==2:
        self.curr[self.count]=(randint(0,25)) # Randomize and replace
      if self.best[1]==1:
        aux_count=(self.compframe-self.best[2])/2 # Move only if bird is halfway between pipes or later
        if self.count>aux_count:
          self.curr[self.count]=(randint(0,25))
      else:
        aux_count=self.compframe-20 # Move only if bird is more than 5/6 of the way to next pipe
        if self.count>aux_count:
          self.curr[self.count]=(randint(0,30)) # Possible to change chance later
    self.count+=1
    return self.curr[self.count-1]

  def scorecount(self):
    self.curr[2]=self.count


if __name__ == '__main__':
    # If this module had been imported, __name__ would be 'flappybird'.
    # It was executed (e.g. by double-clicking the file), so call main.
    main()
