import os
import math
import cairo

'''
    The general layout of the calendar puzzle. Xs denotes the
    border and letters the parts. The three cells at the
    bottom right remain empty, the material is discarded. The
    cells marked by dots are removed in the original design but
    kept here for an overall rectangular layout.

        0 1 2 3 4 5 6 7 8 

    0   X X X X X X X X .
    1   X A Á B B C D X .
    2   X A B B C C D X X
    3   X A A E C D D D X
    4   X E E E C F F G X
    5   X H H H H F I G X
    6   X H J J F F I G X
    7   X J J J I I I G X
    8   X X X X X . . . X
    9   . . . . X X X X X

'''

# Strings for the engraved labels. You may want to adapt these to your locale.
DAY_NAMES = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
MONTH_NAMES = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dez']

# A dedication to engrave into the bottom left corner. 
DEDICATION = '' # 'Daily Calendar Puzzle'

FONTNAME = 'Arial'

# Overall scale factor
GRID = 10

# Partial paths specified between branch-points including the branch points themselves. 
# Specified as the starting coordinate and steps in the cardinal directions. Easier
# to enter from a drawing..
paths = [
    ((3,1), 'WWSSS'),
    ((3,1), 'SWSE'),
    ((3,1), 'EE'),
    ((5,1), 'E'),
    ((5,1), 'SWS'),
    ((1,4), 'EEN'),
    ((1,4), 'S'),
    ((3,3), 'E'),
    ((6,1), 'SSWS'),
    ((6,1), 'ESSES'),
    ((5,4), 'EE'),
    ((7,4), 'E'),
    ((1,5), 'EEE'),
    ((1,5), 'SS'),
    ((4,3), 'SS'),
    ((4,5), 'E'),
    ((5,4), 'S'),
    ((7,4), 'S'),
    ((1,7), 'ENEE'),
    ((4,6), 'EN'),
    ((1,7), 'SEEE'),
    ((4,6), 'S'),
    ((4,7), 'S'),
    ((4,7), 'EENNE'),
    ((4,8), 'E'),
    ((5,8), 'EE'),
    ((7,8), 'NNN'),
    ((7,8), 'E'),
    ((8,4), 'SSSS'),
    ((5,8), 'SEEEN')
]
            
# Move point one grid cell in the given direction.
def update_point(point, direction):
    if direction.upper() == 'N':
        return((point[0], point[1]-1))
    elif direction.upper() == 'W':
        return((point[0]-1, point[1]))
    elif direction.upper() == 'S':
        return((point[0], point[1]+1))
    elif direction.upper() == 'E':
        return((point[0]+1, point[1]))
    else:
        print(f"Unsupported direction '{direction}'")
        quit()

# For elegance we want to do the least number of cuts, so we want to join the paths defined above.
# The (arbitrary) goal is to find the combination with the lowest number of individual cuts and 
# the longest ones at that.
#
# Here is a naive implementation of an exhaustive search:
'''
def walk_path(point, steps):
    for step in steps:
        point = update_point(point, step)
    return point

def reverse_path(steps):
    result = ''

    for direction in steps[::-1]:
        if direction.upper() == 'N':
            result += 'S'
        elif direction.upper() == 'W':
            result += 'E'
        elif direction.upper() == 'S':
            result += 'N'
        elif direction.upper() == 'E':
            result += 'W'
        else:
            print(f"Unsupported direction '{direction}'")
            quit()

    return result

bestroute=None

def join_paths(pathstojoin):
    # pathstojoin is a list of paths defined by starting point and steps
    # to take from there.
    # Find all possible ways of joining two of the entries. That can be done if
    # either of the two ends are the same. For each of these possible joins
    # simplify the list and recurse down.
    # If there are no more possible joins evaluate the result and if it is better
    # than bestroute replace bestroute.

    global bestroute

    for n in range(len(pathstojoin)-1):
        start1, steps1 = pathstojoin[n]
        end1 = walk_path(start1, steps1)

        for m in range(n+1, len(pathstojoin)):
            start2, steps2 = pathstojoin[m]
            end2 = walk_path(start2, steps2)

        # There are four ways we can join paths:
        new = None
        if end1 == start2:
            # 1) The second starts at the end of the first one: Just do them in succession.
            new = (start1, steps1 + steps2)  
        elif end1 == end2:
            # 2) The ends coincide: To the first one and then the second in reverse. 
            new = (start1, steps1 + reverse_path(steps2))
        elif start1 == start2:
            # 3) They start at the same place: Start at the end of the first one, do that in reverse, then the second one.
            new = (end1, reverse_path(steps1) + steps2)
        elif end2 == start1:
            # 4) The second one ends at the start of the first one: Like case 1, but in reversed order.
            new = (start2, steps2 + steps1)

        if new:
            # We have found a way to join two paths. Update
            # the list and recurse.
            newpaths = pathstojoin.copy()
            del newpaths[m]
            del newpaths[n]
            newpaths.append(new)
            join_paths(newpaths)
        else:
            # Nothing left to join.
            if bestroute:
                if len(pathstojoin) < len(bestroute):
                    # Less parts is better.
                    bestroute = pathstojoin.copy()
                    print(f"New best: {len(bestroute)} parts.")
                    print(bestroute)
                elif len(pathstojoin) == len(bestroute):
                    # Add squares of lengths. The longer one wins.
                    bestlen = 0
                    for start, steps in bestroute:
                        bestlen += len(steps)**2
                    
                    newlen = 0
                    for start, steps in pathstojoin:
                        newlen += len(steps)**2

                    if newlen > bestlen:
                        bestroute = pathstojoin.copy()
                        print(f"New best: {len(bestroute)} parts, len^2 = {newlen}.")
                        print(bestroute)
                    else:
                        # Not a better route than what we already have.
                        pass    
                else:
                    # Not a better route than what we already have. 
                    pass
            else:
                bestroute = pathstojoin.copy()
                print(f"New best: {len(bestroute)} parts.")
                print(bestroute)
'''

# Or: Just use this, found by a combination of the code above and manual scribbling:
bestroute = [
    ((5, 8), 'EENNNWSSWWNENWNNNENESSWSEEESSSSSWWWNWWWWNNNNNNNEESWSESWW'),
    ((3, 1), 'EE'), 
    ((3, 3), 'E'), 
    ((6, 1), 'ESSES'), 
    ((1, 5), 'EEE'), 
    ((5, 4), 'S'), 
    ((7, 4), 'S'), 
    ((1, 7), 'ENEE'), 
    ((4, 7), 'S'), 
    ((7, 8), 'E')
]

FILENAME_TOP = 'top_and_parts.svg'
FILENAME_BOTTOM = 'bottom.svg'

# https://pycairo.readthedocs.io/en/latest/reference/index.html

# Global pyCairo context used by all the common drawing functions.
context = None

# Switch context to cutting. See your service provider design guidelines or the
# rules your cutting software uses. 
def set_to_cut():    
    context.set_line_width(0.1)
    context.set_source_rgb(0, 0, 0)

# Switch context to engraving. See your service provider design guidelines or the
# rules your cutting software uses. 
def set_to_engrave():    
    context.set_line_width(0.1)
    context.set_source_rgb(1.0, 0, 0)

# Draw a rounded rectangle.
def roundrect(x, y, w, h, r):
    context.move_to(x + r, y)
    context.line_to(x + w - r, y)
    context.arc(x + w - r, y + r, r,     3*math.pi/2, 4*math.pi/2)
    context.line_to(x + w, y + h - r)
    context.arc(x + w - r, y + h - r, r, 0*math.pi/2, 1*math.pi/2)
    context.line_to(x + r, y + h)
    context.arc(x + r, y + h - r, r,     1*math.pi/2, 2*math.pi/2)
    context.line_to(x, y + r)
    context.arc(x + r, y + r, r,         2*math.pi/2, 3*math.pi/2)
    
    context.stroke()
    
# Cut the outside border. This is common to both top and bottom layers.
def cut_outside_border():
    set_to_cut()
    roundrect((    0.3) * GRID, (    0.3) * GRID, (9 - 0.3 - 0.3) *GRID, (10 - 0.3 - 0.3) * GRID, GRID/4)

# Draw text centered in grid cell.
def center_text_in_cell(cellx, celly, text):
    x_bearing, y_bearing, width, height, x_advance, y_advance = context.text_extents(text)

    tx = (cellx + 0.5) * GRID - x_bearing - width/2
    ty = (celly + 0.5) * GRID - y_bearing - height/2

    context.move_to(tx, ty)
    context.text_path(text)
    context.stroke()

def main():
    global context
    
    # Uncomment, if you also uncommented the optimization code at the top.
    # join_paths(paths)

    # Remove existing output files so we are not confused by old versions if something goes wrong.
    if os.path.exists(FILENAME_TOP):
        os.remove(FILENAME_TOP)

    if os.path.exists(FILENAME_BOTTOM):
        os.remove(FILENAME_BOTTOM)

    # Draw the top layer. This has a border, the dedication if any, and the parts themselves.
    with cairo.SVGSurface(FILENAME_TOP, 9*GRID, 10*GRID) as surface:
        context = cairo.Context(surface)
        
        # Engrave the dedication.
        if DEDICATION:
            set_to_engrave()
            font_size = 0.4 * GRID
            context.set_font_size(font_size)
            context.select_font_face(FONTNAME, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
     
            available_width = (4 - 0.2) * GRID
            available_height = (1 - 0.2) * GRID 

            x_bearing, y_bearing, width, height, x_advance, y_advance = context.text_extents(DEDICATION)
            scalex = available_width / width
            scaley = available_height / height
            if scalex < 1.0 or scaley < 1.0:
                scale = min(scalex, scaley)
                font_size = font_size * scale
                context.set_font_size(font_size)

            x_bearing, y_bearing, width, height, x_advance, y_advance = context.text_extents(DEDICATION)
            
            # Center in available rect.
            tx = 3 * GRID - x_bearing - width/2
            ty = (8 + 0.5) * GRID - y_bearing - height/2

            # OR: Left-Justify
            tx = 1 * GRID - x_bearing
            
            # OR: Bottom-Justify with bottom row
            ty = 9 * GRID - y_bearing - height

            context.move_to(tx, ty)
            context.text_path(DEDICATION)
            context.stroke()
             
        # Cut each path as specified.
        set_to_cut()
        for p, steps in bestroute:
            # For debugging: Draw a circle at the starting point.
            '''
            context.arc(p[0] * GRID, p[1] * GRID, 0.5, 0, 2*math.pi)
            context.stroke()
            '''

            # Move to starting point.
            context.move_to(p[0] * GRID, p[1] * GRID)
            
            # Cut a line for each step.
            for direction in steps:        
                p = update_point(p, direction)
                context.line_to(p[0] * GRID, p[1] * GRID)
            
            # One path segment done.
            context.stroke()

            # For debugging: Draw a circle at the end point.
            '''
            context.arc(p[0] * GRID, p[1] * GRID, 0.5, 0, 2*math.pi)
            context.stroke()
            '''

        cut_outside_border()

    with cairo.SVGSurface(FILENAME_BOTTOM, 9*GRID, 10*GRID) as surface:
        context = cairo.Context(surface)

        # Engrave inside border. Could be useful in alignment on assembly.
        '''
        set_to_engrave()
        context.move_to(1 * GRID, 1 * GRID)
        context.line_to(7 * GRID, 1 * GRID)
        context.line_to(7 * GRID, 3 * GRID)
        context.line_to(8 * GRID, 3 * GRID)
        context.line_to(8 * GRID, 9 * GRID)
        context.line_to(5 * GRID, 9 * GRID)
        context.line_to(5 * GRID, 8 * GRID)
        context.line_to(1 * GRID, 8 * GRID)
        context.line_to(1 * GRID, 1 * GRID)
        context.stroke()
        '''

        # Engrave vertical grid lines.
        set_to_engrave()
        for x in range(2, 8):
            context.move_to(x * GRID, (1 if x<7 else 3) * GRID)
            context.line_to(x * GRID, (8 if x<6 else 9) * GRID)
            context.stroke()
        
        # Engrave horizontal grid lines.
        set_to_engrave()
        for y in range(2, 9):
            context.move_to((1 if y<8 else 5) * GRID, y * GRID)
            context.line_to((7 if y<4 else 8) * GRID, y * GRID)
            context.stroke()
        
        # Engrave labels for dates.
        set_to_engrave()
        context.set_font_size(0.4 * GRID)
        context.select_font_face(FONTNAME, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
     
        # Month names:
        for m in range(0, 12):
            center_text_in_cell(1 + m%6, 1 + m//6, MONTH_NAMES[m])

        # Day numbers:
        for d in range(0, 31):
            center_text_in_cell(1 + d%7, 3 + d//7, str(d+1))

        # Weekday names:
        for w in range(0, 7):
            x = 4 + w%4
            y = 7 + w//4
            if w>3:
                x += 1
            center_text_in_cell(x, y, DAY_NAMES[w])
            
        cut_outside_border()

if __name__ == "__main__":

    main()

