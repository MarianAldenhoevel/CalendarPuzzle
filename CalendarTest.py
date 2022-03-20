import datetime

challenges = []
repeating = False
stretch = 0
year = 2022
while True:
    print(f'{year}:')
    start = datetime.date(year,1,1)
    end = datetime.date(year,12,31)
    d = start
    unique = 0
    repeat = 0
    while d<=end:
        challenge = f'{d.month:02d}-{d.day:02d}-{d.weekday()}'
        stretch += 1
        if not challenge in challenges:
            unique += 1
            challenges.append(challenge)
            if repeating:
                print(f'  first unique {d} after {stretch} days')
                stretch = 0
            repeating = False
            if len(challenges) == 366*7:
                break
        else:
            repeat += 1
            if not repeating:
                print(f'  first repeat {d} after {stretch} days')
                stretch = 0
            repeating = True

        d = d + datetime.timedelta(days=1)

    print(f'  ({unique} unique, {repeat} repeats)')

    if len(challenges) == 366*7:
        print(f'{d}: Done, all {len(challenges)} challenges have been seen here.')
        break
    
    year += 1

'''
This puzzle offers challenges for all 366 valid dates and each weekday for a total of 2562 individual challenges.

Starting on January 1st 2022 there is a new puzzle for 2191 consecutive days up to and including December 31st 2027. 
The year 2028 starts on a Saturday just like 2022, but because it is a leap year there are only 31+29=59 puzzles repeated until
there is a fresh one on February 29th. 

Then it repeats again through to a new challenge on March 1st 2029. There follow 306 new challenges in 2029 and 59 new ones in 2030 
where we will have seen everything from March 1st on.

The five remaining new challenges appear on the leap days in 2032, 2036, 2040, 2044 and 2048.

From January 1st 2049 on the cycle repeats. But Facebook will propably have forgotten the solutions by then. 
'''