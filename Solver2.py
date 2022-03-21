# -*- coding: utf-8 -*-
'''
@author: Marian Aldenhövel <marian.aldenhoevel@marian-aldenhoevel.de>
'''

from calendar import Calendar
import math
import random 
import uuid
import logging
import shutil
import os
import glob
import sys
import time
import copy
import datetime
import argparse 
import math
import json
import calendar

from shapely.geometry.polygon import Polygon
from shapely.geometry.point import Point
from shapely.affinity import translate
from shapely.affinity import rotate
from shapely.affinity import scale
from descartes import PolygonPatch

import matplotlib
matplotlib.use('agg') # select a non-interactive backend. Do this before importing pyplot!
from matplotlib import pyplot

# Global variables
starttime = datetime.datetime.now().replace(microsecond=0)
options = None

# Part encapsulates a single part in the puzzle. It has geometry as a shapely.geometry.polygon which is
# never transformed after creation. It has separate x/y-offset and rotation members which are set during
# the operation of the solver and a final_polygon method that returns the polygon in the position and
# attitude specified with the separate members.
#
# When a Part is constructed __init__ checks the geometry to see in which of the 90-degree rotations it
# is distinct. This list is also kept with the Part so we can optimize the placement during solving to
# eliminate duplicates.
class Part:
  
  def __init__(self, name, polygon, color, mirror):
    self.name = name
    self.polygon = polygon
    self.color = color
    self.xoffset = 0
    self.yoffset = 0
    self.rotation = 0
    self.mirror = mirror
    self.ismirrored = False
    self.candidatepositions = []

    # build a list of distinct rotations
    self.rotations = [0]
    rotation_polys = [self.polygon]
    for rotation in range(90, 360, 90):
      test = rotate(self.polygon, rotation)
      if not any(test.equals(poly) for poly in rotation_polys):
        self.rotations.append(rotation)
        rotation_polys.append(test)

  def __copy__(self):
    clone = Part(self.name, self.polygon, self.color, self.mirror)
    clone.xoffset = self.xoffset
    clone.yoffset = self.yoffset
    clone.rotation = self.rotation
    clone.ismirrored = self.ismirrored
    clone.candidatepositions = self.candidatepositions.copy()

    return clone

  def finalpolygon(self):
    p = self.polygon

    if self.ismirrored:
      p = scale(p, -1)
    p = rotate(p, self.rotation)
    p = translate(p, self.xoffset, self.yoffset)

    return p

monthlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekdaylabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
# BoardState is the main object class for the solver. It carries a reference to the puzzle being solved
# (name, list of parts and the complete geometry of the target). It has a list of parts still available,
# in their default don't-care positions as created in the catalog. It has a list of parts already placed,
# their offset- and rotation-values matter. And the remaining geometry of the target with all the placed
# parts subtracted. Instances of this class are used to maintain the state and modify it as we progress
# down the tree.
class BoardState:

  framenr = 0
  logger = logging.getLogger('Board')
  extents = Point()

  def __init__(self, target, parts_placed, parts_available):
    self.target = target
    self.remaining_target = target
    self.parts_placed = parts_placed
    self.parts_available = parts_available
    self.candidateposition = None

    # self.sanity()

  def clearmappedsquares(self):
    self.freecoords = []
    self.squarenames = []
    self.monthsquares = []
    self.daysquares = []
    self.weekdaysquares = []
    
  def mapsquares(self, target):

    #logger = logging.getLogger('mapsquares')
    #logger.debug('target.area={area}'.format(
    #  area=target.area
    #))
    
    # Find uncovered squares in the polygon target and map them 
    # to months, days and weekdays.
    freecoords = []
    for x in range(0, 8):
        for y in range(-1, 7):
            square = Polygon([(x,y), (x+1, y), (x+1, y+1), (x, y+1), (x,y)])
            i = target.intersection(square)
            if (i.area):
                minx, miny, _, _ = i.bounds
                self.freecoords.append((int(minx), int(miny)))
                freecoords.append((int(minx), int(miny)))
                #logger.debug('free square ({x},{y})'.format(
                #  x=minx,
                #  y=miny
                #))

    for square in freecoords:
        x, y = square

        weekday = None

        if y == 6: # Top row of months
          month = x + 1
          self.monthsquares.append(month)
          self.squarenames.append(monthlabels[month-1])
        elif y == 5: # Bottom row of months
          month = x + 7
          self.monthsquares.append(month)
          self.squarenames.append(monthlabels[month-1])
        elif ((y == 0) and (x <= 2)) or (y in range(1, 5)): # Day-rows
          row = 4-y # Top row: 4-4 = 0, bottom row 4-0 = 4
          day = 7*row + x + 1
          self.daysquares.append(day)
          self.squarenames.append(str(day))
        
        elif (x == 4) and (y == 0):
          weekday = 0 # 'Mon'
        elif (x == 5) and (y == 0):
          weekday = 1 # 'Tue'
        elif (x == 6) and (y == 0):
          weekday = 2 # 'Wed'
        elif (x == 4) and (y == -1):
          weekday = 3 # 'Thu'
        elif (x == 5) and (y == -1):
          weekday = 4 # 'Fri'
        elif (x == 6) and (y == -1):
          weekday = 5 # 'Sat'
        elif (x == 3) and (y == 0):
          weekday = 6 # 'Sun'

        if weekday != None:
          self.weekdaysquares.append(weekday)
          self.squarenames.append(weekdaylabels[weekday])

    #logger.debug('squarenames={squares}'.format(
    #  squares=','.join(self.squarenames)
    #))
    
  def __copy__(self):
    clone = BoardState(self.remaining_target, self.parts_placed.copy(), self.parts_available.copy())
    #clone.calendarconfiguration = self.calendarconfiguration

    return clone 

  # Create a list of all the parts that make up the puzzle.
  '''
    A: XXXX

    B: XXXX
          X
        
    C: XXX
         X

    D: XXX
        X
        X

    E: XX
        X

    F: XXXX
       XXX

    G: XXX
         X
         X

    H: X X
       XXX

    I: XXX
         XX

    J:  XX
         XX      
  '''

  partscatalog = [
    Part('A', Polygon([(0, 0), (4, 0), (4, 1), (0, 1), (0, 0)]), 'firebrick', False),        
    Part('B', Polygon([(0, 0), (4, 0), (4, 2), (3, 2), (3, 1), (0, 1), (0, 0)]), 'green', True),    
    Part('C', Polygon([(0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (0, 1), (0, 0)]), 'blue', True),
    Part('D', Polygon([(0, 0), (3, 0), (3, 1), (2, 1), (2, 3), (1, 3), (1, 1), (0, 1), (0, 0)]), 'purple', True),
    Part('E', Polygon([(0, 0), (2, 0), (2, 2), (3, 2), (3, 3), (1, 3), (1, 1), (0, 1), (0, 0)]), 'yellow', True),
    Part('F', Polygon([(0, 0), (2, 0), (2, 1), (3, 1), (3, 2), (0, 2), (0, 0)]), 'firebrick', True),    
    Part('G', Polygon([(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (0, 1), (0, 0)]), 'green', False),    
    Part('H', Polygon([(0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (1, 1), (1, 2), (0, 2), (0, 0)]), 'blue', False),    
    Part('I', Polygon([(0, 0), (3, 0), (3, 1), (4, 1), (4, 2), (2, 2), (2, 1), (0, 1), (0, 0)]), 'purple', True),
    Part('J', Polygon([(0, 0), (2, 0), (2, 1), (3, 1), (3, 2), (1, 2), (1, 1), (0, 1), (0, 0)]), 'yellow', True)
  ]

  # Plot a solution as a matplotlib-image and save to disk as an image. If the solution is valid,
  # i.e. the three free squares indicate a possible calendar-date, then name it accordingly. If the
  # solution is not valid generate a generic name. 
  def plot(self):
    
    global options

    logger = logging.getLogger('plot')

    # Find uncovered squares. There should be exactly three.
    self.clearmappedsquares()
    self.mapsquares(self.remaining_target)
    
    # Is this a valid calendarpuzzle-solution?
    valid = False
    if (len(self.monthsquares)==1) and (len(self.daysquares)==1) and (len(self.weekdaysquares)==1):
        # This may be a valid calendar-configuration, it has one of each element.
        # Now check number of days:
        if (self.monthsquares[0] == 2) and (self.daysquares[0] <= 29):
          valid = True
        elif (self.monthsquares[0] in [4,6,9,11]) and (self.daysquares[0] <= 30):
          valid = True
        else:
          valid = True
    
    if valid:
        catalogname = '{month:02d}{day:02d}{weekday:02d}-{monthlabel}-{day:02d}-{weekdaylabel}'.format(
          month=self.monthsquares[0],
          day=self.daysquares[0],
          weekday=self.weekdaysquares[0],
          monthlabel=monthlabels[self.monthsquares[0]-1],
          weekdaylabel=weekdaylabels[self.weekdaysquares[0]]
        )

        # Is this a new solution?
        isnew = not os.path.isfile(options.runfolder + '/' + catalogname + '.png')
          
        logger.info('Valid {isnew} solution for {monthlabel}-{day:02d}-{weekdaylabel}.'.format(
          isnew= ('new' if isnew else 'duplicate'),
          monthlabel=monthlabels[self.monthsquares[0]-1],
          day=self.daysquares[0],
          weekdaylabel=weekdaylabels[self.weekdaysquares[0]]
        ))
        
        if not isnew:
          return # don't plot duplicates.

    else:
        catalogname = 'xxxxxx-'
        logger.info('Invalid solution (' + ','.join(self.squarenames) + ')')    

        return # Done. No point in plotting this.
  
    fig = pyplot.figure(1, figsize=(5,5), dpi=90)
    ax = fig.add_subplot(1,1,1) # rows, columns, index
    
    # No axes ticks
    ax.yaxis.set_major_locator(pyplot.NullLocator())
    ax.xaxis.set_major_formatter(pyplot.NullFormatter())
    ax.yaxis.set_minor_locator(pyplot.NullLocator())
    ax.xaxis.set_minor_formatter(pyplot.NullFormatter())

    xoffset = 0
    yoffset = 0
    
    # Plot the target polygon
    if (self.remaining_target.area > 0) and (
      (
        self.remaining_target.geom_type == 'MultiPolygon') 
        or (self.remaining_target.geom_type == 'Polygon')
      ):
      patch = PolygonPatch(self.remaining_target, facecolor='#cccccc')
      ax.add_patch(patch)
      BoardState.extents = BoardState.extents.union(self.remaining_target)

    # Plot the placed parts on top of the target
    for part in self.parts_placed:
      polygon = part.finalpolygon()
      BoardState.extents = BoardState.extents.union(polygon)
      patch = PolygonPatch(polygon, facecolor=part.color)
      ax.add_patch(patch)
  
    # Update the overall bounds carried over from frame to frame. We want them
    # to nicely align for montage.
    bounds = BoardState.extents.bounds

    ax.set_title('Calendar')
    xrange = [bounds[0]-1, bounds[2]+1]
    yrange = [bounds[1]-1, bounds[3]+1]
    ax.set_xlim(*xrange)
    ax.set_ylim(*yrange)
    ax.set_aspect(1)

    figname = options.runfolder + '/' + catalogname + '.png' 
    fig.savefig(figname)

    pyplot.close(fig)
    
    # Save solution as json so we have the option of plotting it in a different way.
    jsonboard = []
    for part in self.parts_placed:
      jsonpart = {
        'name': part.name,
        'xoffset': part.xoffset,
        'yoffset': part.yoffset,
        'rotation': part.rotation,
        'ismirrored': part.ismirrored
      }
      jsonboard.append(jsonpart)

    jsonname = options.runfolder + '/' + catalogname + '.json'
    with open(jsonname, 'w') as f:
      json.dump(jsonboard, f, sort_keys=True, indent=4)

    BoardState.framenr += 1

    #if valid:
    #    quit()

    return

def loadmissing():
  # Find all missing configurations.

  global options
  global missingconfigurations

  logger = logging.getLogger('loadmissing')

  missingconfigurations = {}
  missingcount = 0

  catalogfolder = options.runfolder + '/../catalog' 
  for year in range(2022,2049):
    start = datetime.datetime(year, 1, 1)
    end = datetime.datetime(year, 12, 31)
    d = start
    while (d<=end):
      catalogbasename = '{month:02d}{day:02d}{weekday:02d}-{monthlabel}-{day:02d}-{weekdaylabel}'.format(
        month=d.month,
        day=d.day,
        weekday=d.weekday(),
        monthlabel=monthlabels[d.month-1],
        weekdaylabel=weekdaylabels[d.weekday()]
      )
      configuration = '{month}-{day}-{weekday}'.format(
        month=d.month,
        day=d.day,
        weekday=d.weekday()  
      )
          
      jsonfile = catalogfolder + '/' + catalogbasename + '.json'
      if not os.path.isfile(jsonfile):
        if not d.month in missingconfigurations:
          missingconfigurations[d.month] = {}
          missingcount += 1          
        if not d.day in missingconfigurations[d.month]:
          missingconfigurations[d.month][d.day] = []
          missingcount += 1
        if not d.weekday() in missingconfigurations[d.month][d.day]:
          missingconfigurations[d.month][d.day].append(d.weekday())
          missingcount += 1
  
      d = d + datetime.timedelta(days = 1)

  logger.debug('{missingcount} missing configurations identified.'.format(missingcount=missingcount))

# Quick check for overlapping boundary boxes before going in deep.
def overlap(bounds1, bounds2):
  minx1 = bounds1[0]
  miny1 = bounds1[1]
  maxx1 = bounds1[2]
  maxy1 = bounds1[3]

  minx2 = bounds2[0]
  miny2 = bounds2[1]
  maxx2 = bounds2[2]
  maxy2 = bounds2[3]

  if (maxx1 <= minx2):
    return False # to the left
  elif (minx1 >= maxx2):
    return False # to the right
  elif (maxy1 <= miny2):
    return False # above
  elif (miny1 >= maxy2):
    return False # below
  else:
    return True # overlapping
    
# Main meat of the recursive solver. Called with a board state checks wether it is already solved.
# If not solved it generates candidate positions for available parts and can identify the board 
# as a dead end if none are found. If candidate positions are found recurse for each of them.
def solve(board, progress):

  global options
  
  logger = logging.getLogger('solve')

  indent = '  ' * len(board.parts_placed)
  
  if not board.parts_available:
    # No more parts to place. We have a solution!
    board.plot()

  else:
    # There are parts left to place, we need to recurse further down.
    
    # Optimization: Look at each disjoint part of the remaining target.
    # If the area of one of those is 1, 2 or 3 squares we can never cover 
    # them with parts. So when mapping them if we find more than one of
    # day, month and weekday each we are done with this branch.
    board.clearmappedsquares()
    if board.remaining_target.geom_type == 'MultiPolygon':
      for p in board.remaining_target.geoms:
        if p.area <= 3:
          board.mapsquares(p)
    else:
      if board.remaining_target.area <= 3:
        board.mapsquares(board.remaining_target) 
    
    if len(board.daysquares)>1 or len(board.monthsquares)>1 or len(board.weekdaysquares)>1:
      level = len(board.parts_placed)
      ll = logging.DEBUG if level>options.infolevel else logging.INFO
      logger.log(ll, '{progress}{indent}Dead end: Small disjoints violate valid solution ({squares}).'.format(
        progress=progress.ljust(options.infolevel*len('xxx/xxx|')),
        indent=indent,
        squares=','.join(board.squarenames)
      ))

    else:  
      # Not a dead-end after the check for disjoint areas.

      # For each missing configuration check wether it can still be done. If none remains we have hit
      # a dead end for a new solution.
      board.clearmappedsquares()
      board.mapsquares(board.remaining_target)
    
      foundmissing = True
      if False:
        for missingmonth in missingconfigurations.keys():
          if foundmissing or (missingmonth in board.monthsquares):
            foundmissing = True
            break
          else:
            for missingday in missingconfigurations[missingmonth].keys():
              if foundmissing or (missingday in board.daysquares):
                foundmissing = True
                break
              else:
                for missingweekday in missingconfigurations[missingmonth][missingday]:
                  if foundmissing or (missingweekday in board.weekdaysquares):
                    foundmissing = True
                    break
      
      if not foundmissing:
        level = len(board.parts_placed)
        ll = logging.DEBUG if level>options.infolevel else logging.INFO
        logger.log(ll, '{progress}{indent}Dead end: Cannot arrive at a missing solution anymore ({squares}).'.format(
          progress=progress.ljust(options.infolevel*len('xxx/xxx|')),
          indent=indent,
          squares=','.join(board.squarenames)
        ))

        quit()
      else:
        # Not a dead end after checking for missing solutions.

        # Pick the next part to place.
        nextpart=board.parts_available[0]

        # Generate all possible legal positions nextpart can go in. This is
        # done in a discrete fashion by scanning the bounding box of the candidate
        # part in steps over the bounds of the target and checking the conditions.
        # The scanning happens in steps and is repeated for each possible 90 degree
        # rotation.
        targetbounds = board.remaining_target.bounds
        targetwidth = targetbounds[2]-targetbounds[0]
        targetheight = targetbounds[3]-targetbounds[1]

        nextpart.candidatepositions = []

        mirror = [False]
        if nextpart.mirror:
          mirror.append(True)

        for m in mirror:  
          if m:
            np = scale(nextpart.polygon, -1)
          else:
            np = nextpart.polygon
          
          for rotation in nextpart.rotations:
            # Clone (possibly mirrored) part in default position 
            part = copy.copy(nextpart)

            # Rotate in place
            poly = rotate(np, rotation)
        
            # Figure out the part bounds in that orientation. This will not change
            # during the scan.
            partbounds = poly.bounds
            partwidth = partbounds[2]-partbounds[0]
            partheight = partbounds[3]-partbounds[1]
            
            # Initialize offsets so that the part is placed at the bottom-left
            # corner of the target from its position agnostic catalog-state.
            initialxoffset = targetbounds[0]-partbounds[0]
            initialyoffset = targetbounds[1]-partbounds[1]
            
            # Scan over the width and height of the target bounds.
            xoffset = 0
            while xoffset + partwidth <= targetwidth:
              yoffset = 0
              
              while yoffset + partheight <= targetheight:          
                part.ismirrored = m
                part.rotation = rotation
                part.xoffset = initialxoffset + xoffset
                part.yoffset = initialyoffset + yoffset

                # What about this position? Generate the polygon first.
                testpoly = part.finalpolygon()

                # To be a valid position the candidate part has to be completely 
                # inside the remaining target geometry
                #
                # We have removed all the area covered by parts already placed
                # from the target. So we do not need to check for overlaps with
                # placed parts, this is already covered.          
                if board.remaining_target.contains(testpoly):
                  nextpart.candidatepositions.append(copy.copy(part))

                yoffset = yoffset + 1
              xoffset = xoffset + 1

        # If there are no candidate positions for a part, we have hit a dead end.
        if len(nextpart.candidatepositions) == 0:
          level = len(board.parts_placed)
          ll = logging.DEBUG if level>options.infolevel else logging.INFO
          logger.log(ll, '{progress}{indent}Dead end: Found no candidate positions for part {name}.'.format(
            progress=progress.ljust(options.infolevel*len('xxx/xxx|')),
            indent=indent,
            name=nextpart.name))
          
        else:    
          # For each candidate position prepare a list of next boards by copying 
          # the current one. Remove the part we just (tentatively) placed from the list
          # of available parts. Append it to the placed parts and remove it from the 
          # target area.
          nextboards = []
          for candidate in nextpart.candidatepositions:    
            nextboard = copy.deepcopy(board)
            nextboard.parts_available = [part for part in nextboard.parts_available if part.name != nextpart.name]
            nextboard.candidateposition = candidate
            nextboard.parts_placed.append(candidate)
            nextboard.remaining_target = nextboard.remaining_target.difference(candidate.finalpolygon())

            nextboards.append(nextboard)
            
          level = len(board.parts_placed)
          msg = '{progress}{indent}Try part {name} with {nextboards} candidate positions.'.format(
            progress=progress.ljust(options.infolevel*len('xxx/xxx|')),
            indent=indent,
            name=nextpart.name,
            nextboards=len(nextboards)
          ) 
          ll = logging.DEBUG if level>options.infolevel else logging.INFO
          logger.log(ll, msg)

          # Update candidatepositions to include any filtering that has happened.
          nextpart.candidatepositions = list(map(lambda board: board.candidateposition, nextboards))

          # Now recurse down into each candidate board to find solutions.
          random.shuffle(nextboards)
          i = 1
          for nextboard in nextboards:        
            level = len(board.parts_placed)
            ll = logging.DEBUG if level>options.infolevel else logging.INFO
            logger.log(ll, '{progress}{indent}{parts_placed} parts placed. Try next position {i:2d} of {nextboards:2d} for part {name}.'.format(
              progress=progress.ljust(options.infolevel*len('xxx/xxx|')),
              indent=indent,
              parts_placed=len(board.parts_placed), 
              i=i, 
              nextboards=len(nextboards),
              name=nextpart.name  
            ))

            prog = progress + ('|' if progress=='' else '') + '{i:3d}/{nextboards:3d}|'.format(
              i=i,
              nextboards=len(nextboards)
            )
            solve(nextboard, prog)
          
            i += 1
          
# Conversion function for argparse booleans
def str2bool(v):
  if v.lower() in ('yes', 'true', 't', 'y', '1'):
    return True
  elif v.lower() in ('no', 'false', 'f', 'n', '0'):
    return False
  else:
    raise argparse.ArgumentTypeError('Boolean value expected.')

# Set up argparse and get the command line options.
def parse_commandline():

  global options

  parser = argparse.ArgumentParser(
    description = 'Solve Calendar-puzzles.'
  )

  parser.add_argument('-ll', '--log-level',
    action = 'store',
    default = 'INFO',
    help ='Set the logging output level to CRITICAL, ERROR, WARNING, INFO or DEBUG (default: %(default)s)',
    dest ='log_level',
    metavar = 'level'
  )

  parser.add_argument('-il', '--info-level',
    action = 'store',
    default = 4,
    type = int,
    help ='Set the logging info recursion level (default: %(default)s)',
    dest ='infolevel',
    metavar = 'infolevel'
  )

  parser.add_argument('-of', '--output-folder',
    action = 'store',
    default = '',
    help = 'Folder for output artefacts (default: timestamp)',
    dest = 'runfolder',
    metavar = 'folder'
  )

  parser.add_argument('-rs', '--random-seed',
    action = 'store',
    default = None,
    help = 'Seed to use for random generator (default: use entropy source to randomize)',
    dest = 'seed',
    metavar = 'seed'
  )

  parser.add_argument('-pf', '--play-fanfare',
    action = 'store',
    default = True,
    type = str2bool,
    help = 'Play a fanfare whenever a solution is found (default: %(default)s)',
    dest = 'playfanfare',
    metavar = 'flag'
  )

  options = parser.parse_args()
  options.log_level_int = getattr(logging, options.log_level, logging.INFO)

  if not options.runfolder:
    options.runfolder = os.path.dirname(os.path.realpath(__file__)) + '/' + time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())

# Set up a logger each for a file in the output folder and the console.      
def setup_logging():
  
  global options
  
  os.makedirs(options.runfolder, exist_ok = True)

  fh = logging.FileHandler(options.runfolder + '/Solver.log')
  fh.setLevel(options.log_level_int)

  ch = logging.StreamHandler()
  ch.setLevel(options.log_level_int)

  ch.setFormatter(logging.Formatter('{asctime} [{levelname:5}] {name} - {message}', '%H:%M:%S', style='{'))
  fh.setFormatter(logging.Formatter('{asctime} [{levelname:5}] {name} - {message}', style='{'))

  root = logging.getLogger()
  root.addHandler(ch)
  root.addHandler(fh)
  root.setLevel(logging.DEBUG)

  # Silence logging from inside matplotlib
  logging.getLogger('matplotlib').setLevel(logging.INFO)

def main():
  
    global options

    parse_commandline()
    setup_logging()

    logger = logging.getLogger('main')
    logger.info('Starting. Output goes to {runfolder}'.format(runfolder=options.runfolder))

    # Initialize random generator. This is here so that we can copy the seed and
    # put it into the code to repeat a run.
    if not options.seed:
      options.seed = str(uuid.uuid4())
    
    logger.info('Random seed in use: {0}.'.format(options.seed))
    random.seed(options.seed)

    loadmissing()

    target = Polygon([ (0, 0), (4, 0), (4, -1), (7, -1), (7, 5), (6, 5), (6, 7), (0, 7), (0, 0)])
    parts_available = copy.copy(BoardState.partscatalog)
    random.shuffle(parts_available)
    board = BoardState(target, [], parts_available)
    solve(board, '')

    endtime = datetime.datetime.now().replace(microsecond=0)
    runtime = (endtime-starttime)
    logger.info('Finished. Total runtime: {runtime}'.format(runtime=runtime))
    
if __name__ == '__main__':
    main()