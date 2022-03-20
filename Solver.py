# -*- coding: utf-8 -*-
'''
@author: Marian Aldenhövel <marian.aldenhoevel@marian-aldenhoevel.de>
'''

from calendar import Calendar
import math
import logging
import shutil
import os
import random
import uuid
import glob
import sys
import time
import copy
import simpleaudio
import datetime
import argparse 
import math
import json
import calendar
import portalocker

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
finalpositions = 0
solutions = 0

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

# A configuration is  made up from a name and a target-geometry as a shapely.geometry.polygon.
# The target geometry is created according to the selections for month, day and day of week
# that are to be kept free in the .
class CalendarConfiguration:
  
  def __init__(self, weekday, day, month):
    self.weekday = weekday
    self.day = day
    self.month = month

    self.create_target()
    
  def square(self, x, y):
    return Polygon([(x, y), (x+1, y), (x+1, y+1), (x, y+1), (x,y)])

  def create_target(self):
    self.name = monthlabels[self.month-1] + '-' + str(self.day) + '-' + weekdaylabels[self.weekday]

    # The overall shape of the cutout
    outer = Polygon([ (0, 0), (4, 0), (4, -1), (7, -1), (7, 5), (6, 5), (6, 7), (0, 7), (0, 0)])

    # Which square to leave free for the month
    monthx = (self.month-1) % 6      # 0..5
    monthy = 6- (self.month-1) // 6  # 6 or 5
    monthsquare = self.square(monthx, monthy)

    # Which square to leave free for the day
    dayx = (self.day-1) % 7 # 0..6
    dayy = 4 - (self.day-1) // 7 # 4..0
    daysquare = self.square(dayx, dayy)

    # And which square to leave free for the day of week
    weekdaystr = weekdaylabels[self.weekday]
    if (weekdaystr == 'Mon'):
      weekdaysquare = self.square(4,  0)
    elif (weekdaystr == 'Tue'):
      weekdaysquare = self.square(5,  0)
    elif (weekdaystr == 'Wed'):
      weekdaysquare = self.square(6,  0)
    elif (weekdaystr == 'Thu'):
      weekdaysquare = self.square(4, -1)
    elif (weekdaystr == 'Fri'):
      weekdaysquare = self.square(5, -1)
    elif (weekdaystr == 'Sat'):
      weekdaysquare = self.square(6, -1)
    elif (weekdaystr == 'Sun'):
      weekdaysquare = self.square(3, 0)
    else:
      raise ValueError(f'Unsupported weekday {self.weekday}')
  
    # Create the over all shape by taking the cutout and removing
    # the three squares.
    self.target = outer.difference(monthsquare).difference(daysquare).difference(weekdaysquare)
    
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

  def __init__(self, calendarconfiguration, parts_placed, parts_available):
    self.calendarconfiguration = calendarconfiguration
    self.remaining_target = calendarconfiguration.target
    self.parts_placed = parts_placed
    self.parts_available = parts_available
    self.candidateposition = None

    # self.sanity()

  def __copy__(self):
    clone = BoardState(self.remaining_target, self.parts_placed.copy(), self.parts_available.copy())
    clone.calendarconfiguration = self.calendarconfiguration

    return clone 

  def sanity(self):
    # Check wether the geometry-setup makes internal sense
    cc = CalendarConfiguration(0,1,1)
    self.logger.info('Target area={area}'.format(area=cc.target.area))
    self.logger.info('Parts available in descending order of area:')
    totalarea = 0
    for part in BoardState.partscatalog:
      self.logger.info('{name}: area={area}, mirror={mirror}, distinct rotations={rotations}'.format(
          name=part.name, 
          mirror=('Yes' if part.mirror else 'No'),
          area=part.polygon.area, 
          rotations=part.rotations
        ))
      totalarea += part.polygon.area
    self.logger.info('Total area of parts={totalarea}'.format(totalarea=totalarea))
    if totalarea == cc.target.area: # Three squares to remain free
      self.logger.debug('Total parts area matches target area. A valid puzzle.')
    else:
      raise ValueError('Total parts area does not match target area, puzzle is invalid.')

  # Create a list of all the parts that make up the puzzle.
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

  # Plot the current board as a matplotlib-image and save to disk as an image. Images
  # are named with a framenumber, optionally followed by a caption denoting wether this
  # is a solution, a dead-end or an intermediate step. The remaining parameters can be
  # used to further specify which type of a frame is being generated.
  def plot(self, caption = '', movingpart = None, candidatepositions = None, deadpart = None):
    
    global options

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
  
    # Plot the available parts in a grid off to the side.
    if self.parts_available:
      bounds = self.remaining_target.bounds
      xoffset = bounds[0] # minx
      yoffset = bounds[1]-4 # miny and down from there
      for part in self.parts_available:
        polygon = translate(part.polygon, xoffset, yoffset)
        BoardState.extents = BoardState.extents.union(polygon)
        patch = PolygonPatch(polygon, facecolor=part.color)
        ax.add_patch(patch)

        # Is this the dead part? If so draw a red edge around it in its
        # resting position.
        if deadpart and (deadpart.name == part.name):
          patch = PolygonPatch(polygon, facecolor=part.color, edgecolor='red')
          ax.add_patch(patch)

        # Next cell in the grid
        xoffset = xoffset + 5
        if xoffset > 12:
          xoffset = 0
          yoffset = yoffset - 4

    # Plot the part that is currently on the move slightly ghosted.
    if movingpart:
      polygon = movingpart.finalpolygon()
      BoardState.extents = BoardState.extents.union(polygon)
      patch = PolygonPatch(polygon, facecolor=movingpart.color, alpha=0.5)
      ax.add_patch(patch)

    # Plot candidatepositions. These are drawn with a smaller alpha so we
    # can see them overlap.
    if candidatepositions:
      for part in candidatepositions:
        polygon = part.finalpolygon()
        BoardState.extents = BoardState.extents.union(polygon)
        patch = PolygonPatch(polygon, facecolor=part.color, alpha=0.2)
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
    
    basename = '{n:05d}'.format(n=BoardState.framenr)
    if options.decorateframes and caption:
      basename += '.' + caption
    basename += '.png'
    
    figname = options.runfolder + '\\' + basename 
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

    jsonname = os.path.splitext(figname)[0] + '.json'
    with open(jsonname, 'w') as f:
      json.dump(jsonboard, f, sort_keys=True, indent=4)

    BoardState.framenr += 1

    return basename

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

def mayfit(target, part):
  # Returns wether part might fit into target.
  if (target.area < part.polygon.area):
    return False
  elif (target.area == part.polygon.area):
    targetbounds = target.bounds
    for rotation in part.rotations:
      poly = rotate(part.polygon, rotation)
      partbounds = poly.bounds
      if (partbounds[2]-partbounds[0] == targetbounds[2]-targetbounds[0]) and (partbounds[3]-partbounds[1] == targetbounds[3]-targetbounds[1]):
        # same bounding box size. Move part over target and check
        xoffset = targetbounds[0]-partbounds[0]
        yoffset = targetbounds[1]-partbounds[1]
        poly = translate(poly,xoffset, yoffset)
        if (poly.equals(target)):
          return True
    return False 
  return True
    
# Main meat of the recursive solver. Called with a board state checks wether it is already solved.
# If not solved it generates candidate positions for available parts and can identify the board 
# as a dead end if none are found. If candidate positions are found recurse for each of them.
def solve(board):

  global finalpositions
  global solutions
  global options
  
  logger = logging.getLogger('solve')

  indent = '  ' * len(board.parts_placed)
  
  if not board.parts_available:
    # No more parts to place. We have a solution!
    finalpositions += 1
    logger.info('Found a solution! Checked {finalpositions} final positions.'.format(
      finalpositions=finalpositions
    ))

    solutions += 1

    if options.playfanfare:
      wavfilename = os.path.dirname(os.path.realpath(__file__)) + '\\fanfare.wav'
      if os.path.isfile(wavfilename):
        wav = simpleaudio.WaveObject.from_wave_file(wavfilename)
        wav.play()

    if options.plotsolutions:
      figname = board.plot('solution')
      figname = os.path.splitext(figname)[0]
      filenames = glob.glob(options.runfolder + '\\' + figname + '.*')
      
      # Copy all solution files out under a name for convenient lookup.
      catalogname = f'{board.calendarconfiguration.month:02d}{board.calendarconfiguration.day:02d}{board.calendarconfiguration.weekday:02d}-{monthlabels[board.calendarconfiguration.month-1]}-{board.calendarconfiguration.day:02d}-{weekdaylabels[board.calendarconfiguration.weekday]}'
      for filename in filenames:
        destname = options.runfolder + '\\..\\catalog\\' + catalogname + os.path.splitext(filename)[1]
        shutil.copyfile(filename, destname)
      
  else:
    # There are parts left to place, we need to recurse further down.
    #
    # Optimization: Check wether the smallest remaining disjoint area is still
    # applicable for the smallest part. If not we are already done with this whole
    # tree.
    min_target = board.remaining_target
    if board.remaining_target.geom_type == 'MultiPolygon':
      for p in board.remaining_target.geoms:
        if (p.area < min_target.area):
          min_target = p
    else:
      min_target = board.remaining_target 
    
    # parts_available is sorted by size
    min_part = board.parts_available[len(board.parts_available)-1]

    if min_target.area < min_part.polygon.area:
      finalpositions += 1
      logger.debug('<{level:02d}> {indent}Dead end: Minimum disjoint space {min_target_area} too small for minimum piece. Checked {finalpositions} final positions.'.format(
        level=len(board.parts_placed),
        indent=indent,
        min_target_area=min_target.area,
        finalpositions=finalpositions))
      
      if options.plotdeadends:
        board.plot('deadend_area', None, None, min_part)

    elif not mayfit(min_target, min_part):
      finalpositions += 1
      logger.debug('<{level:02d}> {indent}Dead end: Minimum disjoint space {min_target_area} same size as minimum piece but does not fit. Checked {finalpositions} final positions.'.format(
        level=len(board.parts_placed),
        indent=indent,
        min_target_area=min_target.area,
        finalpositions=finalpositions))
      
      if options.plotdeadends:
        board.plot('deadend_nofit', None, None, min_part)  

    else:
      # Not a dead-end after the check for minimum disjoint area.

      # Pick the next part to place. We use the area-wise biggest part next and 
      # have sorted the catalog accordingly.
      nextpart = board.parts_available[0]
      
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
        finalpositions += 1
        if logger.isEnabledFor(logging.DEBUG):
          logger.debug('<{level:02d}> {indent}Dead end: Found no candidate positions for part {name}. Checked {finalpositions} final positions.'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            finalpositions=finalpositions))
          
        if options.plotdeadends:
          board.plot('deadend_nopos',None, None, nextpart)
      else:    
        # For each candidate position prepare a list of next boards by copying 
        # the current one. Remove the part we just (tentatively) placed from the list
        # of available parts. Append it to the placed parts and remove it from the 
        # target area.
        if logger.isEnabledFor(logging.DEBUG):
          logger.debug('<{level:02d}> {indent}Creating next boards for part {name} with {candidatepositions} candidate positions'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            candidatepositions=len(nextpart.candidatepositions)))

        nextboards = []
        for candidate in nextpart.candidatepositions:    
          nextboard = copy.deepcopy(board)
          nextboard.parts_available = [part for part in nextboard.parts_available if part.name != nextpart.name]
          nextboard.candidateposition = candidate
          nextboard.parts_placed.append(candidate)
          nextboard.remaining_target = nextboard.remaining_target.difference(candidate.finalpolygon())

          nextboards.append(nextboard)
          
        if logger.isEnabledFor(logging.DEBUG):
          msg = '<{level:02d}> {indent}Try part {name} with {nextboards} candidate positions'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            nextboards=len(nextboards),
            candidatepositions=len(nextpart.candidatepositions)
          )
          if len(nextpart.candidatepositions) != len(nextboards):
            msg += ' (down from {candidatepositions})'.format(candidatepositions=len(nextpart.candidatepositions))
          msg += ' next.'
          logger.debug(msg)

        # Update candidatepositions to include any filtering that has happened.
        nextpart.candidatepositions = list(map(lambda board: board.candidateposition, nextboards))

        # If requested plot a frame with all remaining candidate positions displayed.    
        if options.plotcandidates:
          board.plot('candidatepositions', None, nextpart.candidatepositions)

        # Now recurse down into each candidate board to find solutions.
        i = 1
        for nextboard in nextboards:        
          if logger.isEnabledFor(logging.DEBUG):
            logger.debug('<{level:02d}> {indent}{parts_placed} parts placed. Try next position {i} of {nextboards} for part {name}.'.format(
              level=len(board.parts_placed),
              indent=indent,
              parts_placed=len(board.parts_placed), 
              i=i, 
              nextboards=len(nextboards),
              name=nextpart.name
            ))

          if options.plotstepbystep:
            nextboard.plot('try{i:02d}'.format(i=i), nextboard.candidateposition)

          solve(nextboard)

          if solutions and options.singlesolution:
            break
          
          i += 1
          
# Controller for preparing a puzzle and starting the solver.
def solvefordate(date):

  logger = logging.getLogger('solvefordate')
  logger.info(f'solvefordate({date})')

  # Extract relevant parts from the date. 
  weekday = date.weekday() # 0 = Monday matches weekdaylabels
  day = date.day # 1..31
  month = date.month # 1..12

  solvefor(month, day, weekday)

def solvefor(month, day, weekday):

  global finalpositions
  global solutions
  global options
    
  finalpositions = 0
  solutions = 0

  logger = logging.getLogger('solvefor')
  logger.info(f'solvefor({month}, {day}, {weekday} \"{weekdaylabels[weekday]}\")')
  
  cc = CalendarConfiguration(weekday, day, month)

  # Create the initial board state. Start with no parts placed, and all parts available.
  board = BoardState(cc, [], BoardState.partscatalog)

  # Plot the initial board state, this is the starting frame and shows all the parts
  # next to the empty target.
  board.plot('setup')

  # Try to solve it

  start = datetime.datetime.now()

  solve(board)

  end = datetime.datetime.now()
  duration = end - start
  logger.info(f'solvefor({month}, {day}, {weekday} \"{weekdaylabels[weekday]}\") - finished after {duration}')
  
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

  parser.add_argument('-ss', '--single-solution',
    action = 'store',
    default = True,
    type = str2bool,
    help ='Stop after the first solution found (default: %(default)s)',
    dest ='singlesolution',
    metavar = 'flag'
  )

  parser.add_argument('-pc', '--plot-candidates',
    action = 'store',
    default = False,
    type = str2bool,
    help = 'Output a frame showing all generated candidate positions shaded (default: %(default)s)',
    dest = 'plotcandidates',
    metavar = 'flag'
  )

  parser.add_argument('-pd', '--plot-deadends',
    action = 'store',
    default = False,
    type = str2bool,
    help = 'Output a frame showing each dead-end position (default: %(default)s)',
    dest = 'plotdeadends',
    metavar = 'flag'
  )

  parser.add_argument('-ps', '--plot-solutions',
    action = 'store',
    default = True,
    type = str2bool,
    help = 'Output a frame showing each solution (default: %(default)s)',
     dest = 'plotsolutions',
    metavar = 'flag'
  )

  parser.add_argument('-pb', '--plot-step-by-step',
    action = 'store',
    default = False,
    type = str2bool,
    help = 'Output a frame showing each candidate position as it is tried (default: %(default)s)',
    dest = 'plotstepbystep',
    metavar = 'flag'
  )

  parser.add_argument('-df', '--decorate-frames',
    action = 'store',
    default = True,
    type = str2bool,
    help = 'Add a bit to frame filenames that indicates what is in the frame (default: %(default)s)',
    dest = 'decorateframes',
    metavar = 'flag'
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
    options.runfolder = os.path.dirname(os.path.realpath(__file__)) + '\\' + time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())

# Set up a logger each for a file in the output folder and the console.      
def setup_logging():
  
  global options
  
  os.makedirs(options.runfolder, exist_ok = True)

  fh = logging.FileHandler(options.runfolder + '\\Solver.log')
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

  #date = datetime.date.today() + datetime.timedelta(days=1)
  #solvefordate(date)
  #quit()

  # I have determined that the years 2022 to 2044 (inclusive) use all possible
  # configurations of month, day and weekday. Solve for each of them:
  for year in range(2023, 2045):
    # Start on the weekday that year starts on. This way we will build the configurations
    # in calendar-order. We will try configurations multiple times, but we can detect that 
    # before actually attempting to solve.
    weekday = datetime.datetime(year, 1, 1).weekday() # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    
    for month in range(1,13):
      for day in range(1,32):

        # Skip invalid dates:
        if (month == 2) and (day > (29 if calendar.isleap(year) else 28)):
          continue
        elif (month in [4,6,9,11]) and (day > 30):
          continue
        
        # Attempt to clean up stale lock files
        lockfiles = glob.glob(options.runfolder + '\\..\\catalog\\*.lck')
        for lockfile in lockfiles:
            try:
              os.remove(lockfile)
            except:
              pass # Most propably still locked

        catalogname = f'{month:02d}{day:02d}{weekday:02d}-{monthlabels[month-1]}-{day:02d}-{weekdaylabels[weekday]}'
      
        # Already solved?
        if glob.glob(options.runfolder + '\\..\\catalog\\' + catalogname + '.json'): # and glob.glob(options.runfolder + '\\..\\catalog\\' + catalogname + '.png'):
          logger.info(f'Already done {catalogname}')
        else:
          # No solution exists yet. Create a lock file so other processes know we are working on this.
          lockfilename = options.runfolder + '\\..\\catalog\\' + catalogname + '.lck'
          try:
            with portalocker.Lock(lockfilename, 'wt', timeout = 1) as lockfile:              
              lockfile.write(f'PID {os.getpid()}, started {datetime.datetime.now()}')
              lockfile.flush()
              os.fsync(lockfile.fileno())

              logger.info(f'Now solving for {catalogname}')        
              os.makedirs(options.runfolder, exist_ok = True)                            
              solvefor(month, day, weekday)
        
          except portalocker.exceptions.LockException:
              logger.info(f'{catalogname} locked, being solved by concurrent process')

          finally:
            try:
              os.remove(lockfilename)
            except:
              pass

        weekday = (weekday + 1) % 7
        
  endtime = datetime.datetime.now().replace(microsecond=0)
  runtime = (endtime-starttime)
  logger.info('Finished. Total runtime: {runtime}'.format(runtime=runtime))
    
if __name__ == '__main__':
    main()