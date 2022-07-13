import sys
import datetime
import calendar
import os 
import json
import cairo
import math
import xlsxwriter
import collections
import random

# Create a calendar for each year in the range from the solutions discovered
# by the Solver. For each day find the solution-JSON in the catalog, load it
# and render as a pretty picture.
#
# Also write a XLSX file with general statistics.

basename = ''
if len(sys.argv)>1:
    basename = sys.argv[1]
if not basename:
    basename = '..\\catalog'

#basename = 'do'
#basename = 'xrcloud'
#basename = 'complete'

print(f'Basename={basename}')

COVERAGEFILE = f'.\\render\\{basename}\\coverage.xlsx'
if os.path.isfile(COVERAGEFILE):
    os.remove(COVERAGEFILE)

'''
    A: XXXX

    B:    X
       XXXX
        
    C:   X
       XXX

    D: XXX
        X
        X

    E: X
       XXX
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

partscatalog = {
    'A': [(0, 0), (4, 0), (4, 1), (0, 1), (0, 0)],       
    'B': [(0, 0), (4, 0), (4, 2), (3, 2), (3, 1), (0, 1), (0, 0)],    
    'C': [(0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (0, 1), (0, 0)],
    'D': [(0, 0), (3, 0), (3, 1), (2, 1), (2, 3), (1, 3), (1, 1), (0, 1), (0, 0)],
    'E': [(0, 0), (2, 0), (2, 2), (3, 2), (3, 3), (1, 3), (1, 1), (0, 1), (0, 0)],
    'F': [(0, 0), (2, 0), (2, 1), (3, 1), (3, 2), (0, 2), (0, 0)],
    'G': [(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (0, 1), (0, 0)],
    'H': [(0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (1, 1), (1, 2), (0, 2), (0, 0)],
    'I': [(0, 0), (3, 0), (3, 1), (4, 1), (4, 2), (2, 2), (2, 1), (0, 1), (0, 0)],
    'J': [(0, 0), (2, 0), (2, 1), (3, 1), (3, 2), (1, 2), (1, 1), (0, 1), (0, 0)]
}

def render(d, jsondata, destbasename, style):

    def arctopleft(ctx, cornerx, cornery, radius):
        ctx.arc(cornerx + radius, cornery + radius, radius, math.pi, 3*math.pi/2)
    
    def arctopright(ctx, cornerx, cornery, radius):
        ctx.arc(cornerx - radius, cornery + radius, radius, 3*math.pi/2, 0)
    
    def arcbottomright(ctx, cornerx, cornery, radius):
        ctx.arc(cornerx - radius, cornery - radius, radius, 0, math.pi/2)
    
    def arcbottomleft(ctx, cornerx, cornery, radius):
        ctx.arc(cornerx + radius, cornery - radius, radius, math.pi/2, math.pi)    
    
    def arctopleftinside(ctx, cornerx, cornery, radius):
        ctx.arc_negative(cornerx + radius, cornery + radius, radius, 3*math.pi/2, math.pi)
    
    def arctoprightinside(ctx, cornerx, cornery, radius):
        ctx.arc_negative(cornerx - radius, cornery + radius, radius, 0, 3*math.pi/2)
    
    def arcbottomrightinside(ctx, cornerx, cornery, radius):
        ctx.arc_negative(cornerx - radius, cornery - radius, radius, math.pi/2, ß)
    
    def arcbottomleftinside(ctx, cornerx, cornery, radius):
        ctx.arc_negative(cornerx + radius, cornery - radius, radius, math.pi, math.pi/2)    
    
    def cellx(cellindex):
        return margin + boardmargin + cellindex * cellwidth

    def celly(cellindex):
        return renderheight - margin - boardmargin - cellheight - cellindex * cellheight

    def recttext(ctx, rx, ry, rw, rh, label):

        x, y, textwidth, textheight, dx, dy = ctx.text_extents(label)

        #print(f'{rx}, {ry}, {rw}, {rh}, {textwidth}, {textheight}, "{label}"')

        ctx.move_to(rx + rw/2 - textwidth/2, ry + rh/2 + textheight/4)    
        ctx.show_text(label)

    def celltext(ctx, xindex, yindex, label):        
        cx = cellx(xindex)
        cy = celly(yindex)

        recttext(ctx, cx, cy, cellwidth, cellheight, label)

    def outer(ctx):
        ctx.move_to(margin, margin + boardmargin)
        arctopleft(ctx, margin + 0, margin + 0, radius)
        arctopright(ctx, renderwidth - cellwidth - margin, margin + 0, radius)    
        ctx.line_to(renderwidth - cellwidth - margin, margin + 2 * cellheight)
        arctopright(ctx, renderwidth - margin, margin + 2 * cellheight, radius)
        arcbottomright(ctx, renderwidth - margin, renderheight - margin, radius)
        arcbottomleft(ctx, margin + 0, renderheight - margin, radius)
        ctx.close_path()

    def partpoly(ctx, points):
        ctx.new_path()    
        ctx.move_to(cellx(points[0][0]), celly(points[0][1]))
        for point in points[1:]:
            ctx.line_to(cellx(point[0]), celly(point[1]))
        ctx.close_path()
        
    cellwidth = 50
    cellheight = cellwidth
    margin = 2
    boardmargin = cellwidth // 2

    renderwidth =  7 * cellwidth  + 2 * margin + 2 * boardmargin
    renderheight = 8 * cellheight + 2 * margin + 2 * boardmargin 
    
    yearlabel_x = margin + boardmargin + cellwidth * 2
    yearlabel_y = renderheight - margin - boardmargin - cellheight / 2
    yearlabel_width = cellwidth * 1.5
    yearlabel_height = cellheight / 2
    
    ims = cairo.ImageSurface(cairo.FORMAT_ARGB32, renderwidth, renderheight)
    ctx = cairo.Context(ims)
    
    ctx.select_font_face('Courier', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)    
    ctx.set_line_width(1)

    # Draw outer border
    radius = boardmargin // 3 * 2
    outer(ctx)

    ctx.set_source_rgb(1, 1, 1)
    if style['texture_low']:
        ctx.set_source(style['texture_low'])    
    ctx.fill_preserve()

    ctx.set_source_rgb(0, 0, 0)
    
    recttext(ctx, yearlabel_x, yearlabel_y, yearlabel_width, yearlabel_height, str(year))

    for month in range(1,13):
        monthx = (month - 1) % 6      # 0..5
        monthy = 7 - (month - 1) // 6  # 6 or 5
        celltext(ctx, monthx, monthy, monthlabels[month-1])

    for day in range(0, 32):
        dayx = (day-1) % 7 # 0..6
        dayy = 5 - (day-1) // 7 # 4..0
        celltext(ctx, dayx, dayy, str(day))

    for weekdaystr in weekdaylabels:
        if (weekdaystr == 'Mon'):
            wdx, wdy = (4, 1)
        elif (weekdaystr == 'Tue'):
            wdx, wdy = (5, 1)
        elif (weekdaystr == 'Wed'):
            wdx, wdy = (6, 1)
        elif (weekdaystr == 'Thu'):
            wdx, wdy = (4, 0)
        elif (weekdaystr == 'Fri'):
            wdx, wdy = (5, 0)
        elif (weekdaystr == 'Sat'):
            wdx, wdy = (6, 0)
        elif (weekdaystr == 'Sun'):
            wdx, wdy = (3, 1)
        else:
            raise ValueError(f'Unsupported weekday {weekdaystr}')
        
        celltext(ctx, wdx, wdy, weekdaystr)

    # Draw parts
    i = 0
    for part in jsondata['parts']:
        
        name = part['name']
        xoffset = part['xoffset']
        yoffset = part['yoffset']
        rotation = part['rotation']
        ismirrored = part['ismirrored']

        #if name != 'F':
        #    continue

        # Now. This is terrible. When I build a new solver I modelled the orientation of parts
        # differently completely screwing up the renderer. Instead of fixing it properly I
        # fudged the values here so that everything lines up again. This is just a unit-conversion
        # done in the worst possible way. 
        # Look in the JSON solution for the proper layout if something is broken.

        v3 = True
        if v3:

            if (name != 'B') and (name != 'C') and (name != 'F'):
                if rotation == 90:
                    rotation = 270
                elif rotation == 270:
                    rotation = 90

            while rotation < 0:
                rotation +=360
            while rotation > 360:
                rotation -=360
                
            yoffset -= 1
            if name == 'A':
                if rotation == 90 or rotation == 270:
                    xoffset -= 1.5
                    yoffset += 1.5  
            elif name == 'B':
                ismirrored = not ismirrored
                
                if not ismirrored:
                    if rotation == 180:
                        rotation = 0
                    elif rotation == 0:
                        rotation = 180

                if rotation == 90 or rotation == 270:
                    xoffset -= 1
                    yoffset += 1
            elif name == 'C':                
                ismirrored = not ismirrored
                
                if not ismirrored:
                    if rotation == 180:
                        rotation = 0
                    elif rotation == 0:
                        rotation = 180

                if rotation == 90 or rotation == 270:
                    xoffset -= 0.5
                    yoffset += 0.5   
            elif name == 'D':
                pass                
            elif name == 'E':
                pass
            elif name == 'F':
                pass
                
                if ismirrored:
                    if rotation == 0:
                        rotation = 180
                    elif rotation == 180:
                        rotation = 0

                if True: #not ismirrored:
                    if rotation == 90:
                        rotation = 270
                    elif rotation == 270:
                        rotation = 90

                if rotation == 90 or rotation == 270:
                    xoffset -= 0.5
                    yoffset += 0.5
            elif name == 'G':
                pass
                #rotation -= 180
            elif name == 'H':
                if rotation == 90 or rotation == 270:
                    xoffset -= 0.5
                    yoffset += 0.5
            elif name == 'I':

                if ismirrored:
                    if rotation == 180:
                        rotation = 0
                    elif rotation == 0:
                        rotation = 180

                if rotation == 90 or rotation == 270:
                    xoffset -= 1
                    yoffset += 1                
            elif name == 'J':
                if rotation == 90 or rotation == 270:
                    xoffset -= 0.5
                    yoffset += 0.5 

        if name in partscatalog:
            poly = partscatalog[name]
        
            ctx.save()

            # Translate into position.
            ctx.translate(cellwidth * xoffset, -cellheight * yoffset)
            
            # Rotate around and mirror about the center:
            # Create path so we can get the extents.
            partpoly(ctx, poly)
            # Translate to center.
            x1, y1, x2, y2 = ctx.fill_extents()
            xc = (x1 + x2) / 2
            yc = (y1 + y2) / 2

            ctx.translate(xc, yc)
            # Mirror (v3 before rotation and on y-axis)
            if v3 and ismirrored:
                ctx.scale(-1, 1)
            # Rotate.
            ctx.rotate(-rotation * math.pi / 180)
            # Mirror (non-v3 after rotation and on x-axis).
            if not v3 and ismirrored:
                ctx.scale(-1, 1)
            # Translate back.
            ctx.translate(-xc, -yc)            
            
            ctx.new_path()
            partpoly(ctx, poly)
            
            if style['color_parts']:
                pcol = style['color_parts'][i % len(style['color_parts'])]
                ctx.set_source_rgba(pcol[0], pcol[1], pcol[2], pcol[3])
            if style['texture_parts']:
                ctx.set_source(style['texture_parts'])
            ctx.fill_preserve()

            ctx.set_source_rgb(0, 0, 0)
            ctx.stroke()

            ctx.restore()
        
            i += 1
    
    ctx.set_source_rgb(0, 0, 0)
    ctx.stroke()

    # Draw set of outer and inner border
    outer(ctx)

    radius = cellwidth // 10
    ctx.move_to(margin + boardmargin, margin + boardmargin + radius)
    arctopleft(ctx, margin + boardmargin, margin + boardmargin, radius)
    arctopright(ctx, renderwidth - cellwidth - boardmargin - margin, boardmargin + margin, radius)
    arcbottomleftinside(ctx, renderwidth - cellwidth - boardmargin - margin, margin + boardmargin + 2 * cellheight, radius)
    arctopright(ctx, renderwidth - boardmargin - margin, margin + boardmargin + 2 * cellheight, radius)
    arcbottomright(ctx, renderwidth - boardmargin - margin, renderheight - boardmargin - margin, radius)

    arcbottomleft(ctx, margin + boardmargin + 4 * cellwidth, renderheight - boardmargin - margin, radius)
    arctoprightinside(ctx, margin + boardmargin + 4 * cellwidth, renderheight - boardmargin - margin - cellheight, radius)

    arcbottomleft(ctx, margin + boardmargin, renderheight - boardmargin - margin - cellheight, radius)
    ctx.close_path()

    # cutout for year-label
    ctx.rectangle(yearlabel_x, yearlabel_y, yearlabel_width, yearlabel_height)

    ctx.set_source_rgb(1, 1, 1)
    if style['texture_high']:
        ctx.set_source(style['texture_high'])
    ctx.fill_preserve()

    ctx.set_source_rgb(0, 0, 0)
    ctx.stroke()

    ims.write_to_png(destbasename + '.png')

    # Convert to a jpg using imagemagick and delete the png. This is for size.
    cmdline = f'magick.exe convert {destbasename}.png -quality 85% {destbasename}.jpg'
    os.system(cmdline)
    os.remove(destbasename + '.png')

def counter(i):
    if i<=1:
        return ''
    else:
        return f' ({i})'

monthlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekdaylabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

found = 0
notfound = 0
freshlyrendered = 0
consrendered = 0
consmissing = 0

datesrendered = []
configurationsfound = []
configurationsmissing = []

teximage = cairo.ImageSurface.create_from_png('texture.png')
texture = cairo.SurfacePattern(teximage)
texture.set_extend(cairo.EXTEND_REFLECT)

teximage = cairo.ImageSurface.create_from_png('texture_low.png')
texture_low = cairo.SurfacePattern(teximage)
texture_low.set_extend(cairo.EXTEND_REFLECT)

styles = []

styles.append({
    'texture_high':  texture,
    'texture_low':   texture_low,
    'texture_parts': texture,
    'color_parts':   None
})

styles.append({
    'texture_high':  texture,
    'texture_low':   texture_low,
    'texture_parts': None,
    'color_parts':
        # Color for the parts as RGBA-tuple. Only used if tex_part is None
        [
            (0, 0, 1, 0.4),
            (0, 0, 1, 0.5),
            (0, 0, 1, 0.6)
        ]
})

styles.append({
    'texture_high':  texture,
    'texture_low':   texture_low,
    'texture_parts': None,
    'color_parts':
        # Color for the parts as RGBA-tuple. Only used if tex_part is None
        [
            (0, 143/255, 0, 0.4),
            (0, 143/255, 0, 0.5),
            (0, 143/255, 0, 0.6)
        ]
})

for year in range(2022,2049):
    start = datetime.datetime(year, 1, 1)
    end = datetime.datetime(year, 12, 31)

    d = start
    while (d<=end):
        catalogbasename = f'.\\render\\{basename}\\{d.month:02d}{d.day:02d}{d.weekday():02d}-{monthlabels[d.month-1]}-{d.day:02d}-{weekdaylabels[d.weekday()]}'
        destbasename = f'.\\render\\{basename}\\{d.year}\\{d.month:02d}\\{d.year}-{d.month:02d}-{d.day:02d}'

        configuration = f'{d.month}-{d.day}-{d.weekday()}'
            
        jsonfile = catalogbasename + '.json'
        if os.path.isfile(jsonfile):
            found += 1
                
            if configuration not in configurationsfound:
                configurationsfound.append(configuration)

            if os.path.isfile(destbasename + '.jpg'):
                consmissing = 0
                if consrendered == 0:
                    print('')
                consrendered += 1
                print(('..' if consrendered>1 else '  ') + f'{d:%d.%m.%Y}: Already rendered       ' + counter(consrendered) + ' '*50, end = '\r')
            else:
                print('')
                consrendered = 0
                consmissing = 0
                with open(jsonfile) as f:
                    try:
                        jsondata = json.load(f)
                    except:
                        print(f'  Error loading JSON from {jsonfile}')
                        raise

                    # We forgot to put the information on configuration in when saving the file and 
                    # it is only encoded in the filename. If we encounter such a file we parse the
                    # filename and add the information in on the fly.                    
                    if isinstance(jsondata, collections.abc.Sequence):
                        # jsondata is still "just" an array. Turn into an object, add the
                        # missing information from the filename, then save back.
                        bn = os.path.basename(jsonfile)
                        month = int(bn[0:2])
                        day = int(bn[2:4])
                        weekday = int(bn[4:6])

                        jsondata = {
                            'configuration': {
                                'month': month,
                                'monthlabel': monthlabels[month-1],
                                'day': day,
                                'weekday': weekday,
                                'weekdaylabel': weekdaylabels[weekday]
                            },
                            'parts': jsondata
                        }

                        with open(jsonfile, 'w') as f:
                            json.dump(jsondata, f, sort_keys=False, indent=4)
                       
                    print(f'  {d:%d.%m.%Y}: Rendering ({weekdaylabels[d.weekday()]})' + ' '*50, end='\r')
                    os.makedirs(f'render\\{basename}\\{d.year}\\{d.month:02d}', exist_ok = True)
                    
                    render(d, jsondata, destbasename, random.choice(styles))
                    freshlyrendered += 1
            
            datesrendered.append(d)                    
        else:
            consrendered = 0
            if consmissing == 0:
                print('')
            consmissing += 1

            if configuration not in configurationsmissing:
                configurationsmissing.append(configuration)

            print(('..' if consmissing>1 else '  ') + f'{d:%d.%m.%Y}: Solution missing' + counter(consmissing) + ' '*50, end = '\r')
            notfound += 1
        
        d = d + datetime.timedelta(days = 1)

workbook = xlsxwriter.Workbook(COVERAGEFILE)

format_label =         workbook.add_format({'bold': True, 'align': 'center'})
format_invalid =       workbook.add_format({'bg_color': '#CCCCCC','font_color': '#000000', 'align': 'center'})
format_valid_found =   workbook.add_format({'bg_color': '#00FF00','font_color': '#000000', 'align': 'center'})
format_valid_missing = workbook.add_format({'bg_color': '#FF0000','font_color': '#000000', 'align': 'center'})

# Overview of all years.
worksheet = workbook.add_worksheet('Overview')
worksheet.set_zoom(50)

yearstatus = {}

rowoffset = 0

col = 1
for year in range(2022,2049):

    if year == 2036:
        col = 1
        rowoffset = 34

    row = 0 + rowoffset
    worksheet.merge_range(row, col, row, col+11, year, format_label)
    row += 1
        
    start = datetime.datetime(year, 1, 1)
    end = datetime.datetime(year, 12, 31)

    days = 0
    missing = 0

    for month in range(1,13):
        row = 1 + rowoffset    
        
        worksheet.set_column(col, col, 1.5)
        worksheet.write(row, col, month, format_label)
        row += 1
        
        for day in range(1, 32):
            worksheet.write(row, 0, day, format_label)
            
            # Valid day?
            valid = True
            covered = False

            if (month == 2) and (day > (29 if calendar.isleap(year) else 28)):
                valid = False
            elif (month in [4,6,9,11]) and (day > 30):
                valid = False

            if valid:
                d = datetime.datetime(year, month, day)
                covered = (d in datesrendered)
            
            if not valid:
                worksheet.write(row, col, 'X', format_invalid)
            else:
                days += 1
                
                if covered:
                    worksheet.write(row, col, '1', format_valid_found)
                else:
                    worksheet.write(row, col, '0', format_valid_missing)
                    missing += 1

            row += 1        

        col += 1

    yearstatus[year] = (days, missing)

for r in range(0, row):
    worksheet.set_row(r, 14)
        

worksheet.freeze_panes(2, 1)

# Year by year.
for year in range(2022,2049):
    days = yearstatus[year][0]
    missing = yearstatus[year][1]
    worksheetname = str(year) + ('✅' if missing == 0 else f' ({(days-missing)/days*100:.1f}%)')
    worksheet = workbook.add_worksheet(worksheetname)
    
    start = datetime.datetime(year, 1, 1)
    end = datetime.datetime(year, 12, 31)

    row = 1
    for month in range(1,13):
        worksheet.write(row, 0, monthlabels[month-1], format_label)
        
        col = 1
        for day in range(1, 32):
            worksheet.write(0, col, f'{day:02d}', format_label)
            worksheet.set_column(col, col, 2)
            
            # Valid day? 31sts and Feb 29ths.
            valid = True
            covered = False

            if (month == 2):
                if (day > 29):
                    valid = False
                elif (day == 29) and (not calendar.isleap(year)):
                    valid = False
            elif (month in [4,6,9,11]) and (day > 30):
                valid = False

            if valid:
                d = datetime.datetime(year, month, day)
                covered = (d in datesrendered)
            
            if not valid:
                worksheet.write(row, col, 'X', format_invalid)
            else:
                if covered:
                    worksheet.write(row, col, '1', format_valid_found)
                else:
                    worksheet.write(row, col, '0', format_valid_missing)
                    
            col += 1        
    
        row += 1
    
    worksheet.freeze_panes(1, 1)

workbook.close()

print('')
print(f'Total {found+notfound} days.')
print(f'Freshly rendered {freshlyrendered} days.')
print(f'Found {len(configurationsfound)} configurations used by {found} days.')
print(f'Missing {len(configurationsmissing)} configurations for {notfound} days.')

D = len(configurationsfound)+len(configurationsmissing)
if D != 0:
    complete = 100*len(configurationsfound)/D
    print(f'Overall {complete:.1f}% complete.')