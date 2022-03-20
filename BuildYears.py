import datetime
import calendar
import os 
import glob
import shutil
import json
import cairo
import math
import xlsxwriter

# Create a calendar for each year in the range from the solutions discovered
# by the Solver. For each day find the solution-JSON in the catalog, load it
# and render as a pretty picture.
#
# Also write a XLSX file with general statistics.

COVERAGEFILE = '.\\render\\coverage.xlsx'
if os.path.isfile(COVERAGEFILE):
    os.remove(COVERAGEFILE)

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

def render(d, jsonfile, destbasename):

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
        ctx.move_to(cellx(points[0][0]), celly(points[0][1]))
        for point in points[1:]:
            ctx.line_to(cellx(point[0]), celly(point[1]))
        ctx.close_path()
        
    cellwidth = 100
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
    ctx.set_font_size(40)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)    
    ctx.set_line_width(2)

    # Draw outer border
    radius = boardmargin // 3 * 2
    outer(ctx)

    ctx.set_source_rgb(1, 1, 1)
    if tex_low:
        ctx.set_source(tex_low)    
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
    for part in jsondata:
        
        name = part['name']
        xoffset = part['xoffset']
        yoffset = part['yoffset']
        rotation = part['rotation']
        ismirrored = part['ismirrored']

        if name in partscatalog:
            poly = partscatalog[name]
        
            ctx.save()

            ctx.translate(cellwidth * xoffset, -cellheight * yoffset)

            partpoly(ctx, poly)
            
            x1, y1, x2, y2 = ctx.fill_extents()
            xc = (x1 + x2) / 2
            yc = (y1 + y2) / 2
            ctx.translate(xc, yc)
            ctx.rotate(-rotation * math.pi / 180)
            if ismirrored:
                ctx.scale(-1, 1)
            ctx.translate(-xc, -yc)            
            
            ctx.new_path()
            partpoly(ctx, poly)
            
            pcol = partcol[i % len(partcol)]
            ctx.set_source_rgba(pcol[0], pcol[1], pcol[2], pcol[3])
            if tex_part:
                ctx.set_source(tex_part)
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
    if tex:
        ctx.set_source(tex)
    ctx.fill_preserve()

    ctx.set_source_rgb(0, 0, 0)
    ctx.stroke()

    ims.write_to_png(destbasename + '.png')

def counter(i):
    if i<=1:
        return ''
    else:
        return f' ({i})'

monthlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekdaylabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

teximage = cairo.ImageSurface.create_from_png('texture.png')
tex = cairo.SurfacePattern(teximage)
tex.set_extend(cairo.EXTEND_REFLECT)

teximage = cairo.ImageSurface.create_from_png('texture_low.png')
tex_low = cairo.SurfacePattern(teximage)
tex_low.set_extend(cairo.EXTEND_REFLECT)

# Texture parts. Leave as None for no texture
tex_part = None
#tex_part = tex

# Color for the parts as RGBA-tuple. Only used if tex_part is None
partcol = [
    (0, 0, 1, 0.4),
    (0, 0, 1, 0.5),
    (0, 0, 1, 0.6)
]

found = 0
notfound = 0
freshlyrendered = 0
consrendered = 0
consmissing = 0

datesrendered = []
configurationsfound = []
configurationsmissing = []

for year in range(2022,2049):
    os.makedirs(f'render\\{year}', exist_ok = True)

    start = datetime.datetime(year, 1, 1)
    end = datetime.datetime(year, 12, 31)

    d = start
    while (d<=end):
        catalogbasename = f'.\\catalog\\{d.month:02d}{d.day:02d}{d.weekday():02d}-{monthlabels[d.month-1]}-{d.day:02d}-{weekdaylabels[d.weekday()]}'
        destbasename = f'.\\render\\{d.year}\\{d.year}-{d.month:02d}-{d.day:02d}'

        configuration = f'{d.month}-{d.day}-{d.weekday()}'
            
        jsonfile = catalogbasename + '.json'
        if os.path.isfile(jsonfile):
            found += 1
                
            if configuration not in configurationsfound:
                configurationsfound.append(configuration)

            if os.path.isfile(destbasename + '.png'):
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
                    print(f'  {d:%d.%m.%Y}: Rendering ({weekdaylabels[d.weekday()]})' + ' '*50, end='\r')
                    render(d, jsondata, destbasename)
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