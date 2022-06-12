import os 
import shutil
import json
import collections

monthlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekdaylabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

# We forgot to put the configuration-information into the solution-files :-/.
#
# Iterate over all json files in the current directory. Parse the filename
# out into elements and put them into the data. Then save it back.

infolder = '.'

for file in os.listdir(infolder):
    filename = infolder + '/' + os.fsdecode(file)
    basename = os.path.basename(filename)

    if filename.endswith('.json'):
        with open(filename) as f:
            try:
                jsondata = json.load(f)
            except:
                print(f'  Error loading JSON from {filename}')
                raise
        
        month = int(basename[0:2])
        day = int(basename[2:4])
        weekday = int(basename[4:6])

        print(filename, month, day, weekday, end = '')

        # Only enhance if not enhanced yet. It was an array before, should be
        # an object after.
        if isinstance(jsondata, collections.Sequence):
            print(' enhancing.')
            newdata = {
                'configuration': {
                    'month': month,
                    'monthlabel': monthlabels[month-1],
                    'day': day,
                    'weekday': weekday,
                    'weekdaylabel': weekdaylabels[weekday]
                },
                'parts': jsondata
            }

            with open(filename, 'w') as f:
                json.dump(newdata, f, sort_keys=False, indent=4)
        else:
            print(' already enhanced.')
            