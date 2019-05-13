from app import db
from flask import render_template, flash, redirect, request, url_for, send_file, session
from app.main.forms import HoursForm, CumulativeDropdown, RunningSumDropdown

from flask_login import current_user, login_user, logout_user, login_required

from app.models import User, Work
from app.main import bp

from werkzeug.urls import url_parse
from datetime import datetime, timedelta, date
from string import Template
import pandas as pd
import itertools
from io import BytesIO

class DeltaTemplate(Template):
    delimiter = '%'

# format timedelta function; takes a timedelta obj and a desired format
def strfdelta(tdelta,fmt):
    d = {}
    totsecs = tdelta.total_seconds()
    # hrs, mins, secs calculation from the total seconds
    # no days. e.g. 1 day 6 hours 30 minutes would be 30:30 (HH:MM)
    hours, minutes, seconds = int(totsecs//3600),int((totsecs%3600)//60),int((totsecs%3600)%60)
    # {:02d} formats an integer to a field of min width 2, with 0-padding on the left
    d['H'] = '{:02d}'.format(hours)
    d['M'] = '{:02d}'.format(minutes)
    d['S'] = '{:02d}'.format(seconds)
    t = DeltaTemplate(fmt)
    return t.substitute(**d)

# IF DATA TAKEN FROM **TODAY'S** SHIFT == FALSE
def breakOverOfficial(total_rest, hours_worked, official_break):
    # convert total_rest to timedelta:
    h,m=total_rest.strftime('%-H:%-M').split(':')
    total_rest_td = timedelta(hours=int(h),minutes=int(m))

    # 24 hours minus hours_worked
    hours_worked_opp = timedelta(hours=24)-hours_worked

    # returns timedelta
    return (total_rest_td-(hours_worked_opp+official_break))

# IF DATA TAKEN FROM **TODAY'S** SHIFT == TRUE
def breakOverOfficial_EndShiftTrue(total_rest, end, hours_worked, official_break, utc_plusone):
    # convert total_rest to timedelta
    # MAYBE USE datetime.combine(date.min,TIMEOBJ)-datetime.min instead? returns a timedelta obj
    h,m=total_rest.strftime('%-H:%-M').split(':')
    total_rest_td = timedelta(hours=int(h),minutes=int(m))

    end_td_r2 = timedelta(hours=24)-(datetime.combine(date.min,end)-datetime.min)

    total_rest_td = total_rest_td + end_td_r2
    if utc_plusone == True:
        total_rest_td += timedelta(hours=1)

    hours_worked_opp = timedelta(hours=24)-hours_worked

    return (total_rest_td-(official_break+hours_worked_opp))


def restDailyWeekly(listHours):
    listHours.sort(key=lambda x:x[0])
    for row in listHours:
        row_index = listHours.index(row)
        if row_index == 0:
            row.append('')
        elif row[15] == False: # if not start of week
            if row[16] == False and (row[17] == False or row[17] == None): # if not holiday
                # start/end are STRINGS!
                endtime_day_before = listHours[row_index-1][2]
                starttime_current_day = listHours[row_index][1]
                h_e,m_e=endtime_day_before.split(':')
                h_s,m_s=starttime_current_day.split(':')

                end_before_td = timedelta(hours=int(h_e),minutes=int(m_e))
                start_current_td = timedelta(hours=int(h_s),minutes=int(m_s))

                dailyRestComp = str(start_current_td + (timedelta(hours=24)-end_before_td))

                row.append(str(str(dailyRestComp)+', D'))
            else: # if holiday
                row.append('Holiday')

        elif row[15]==True: # if start of week --> calculate weekly rest
            for rowNew in reversed(listHours[:row_index]):
                if rowNew[13] != False and (rowNew[16] != True or row[17] != True): # if previous day entered
                    endtime_day_before = datetime.strptime(rowNew[2],'%H:%M').time()

                    starttime_current_day = datetime.strptime(listHours[row_index][1],'%H:%M').time()

                    weeklyRestComp=datetime.combine(listHours[row_index][0],starttime_current_day)-datetime.combine(rowNew[0],endtime_day_before)

                    row.append(strfdelta(weeklyRestComp, '%H:%M')+', W')

                    break
                else:
                    continue
        else:
            row.append('Error. No End of Week has been defined')
    return listHours


def listDates(id):
    listHours = Work.query.filter_by(user_id=id)

    dateList = []
    for row in listHours:
        if row.start_time == None and row.end_time == None: # if sick/holiday              #break,
            dateList.append([row.date.date(), None, None, None, row.id, row.week_beginning, None, None, None, None, row.end_of_week, None, None,row.start_of_week, row.holiday_sick, row.holiday_NAH])
        else:               # 0                 1                       2                   3                       4       5                   6           7               8         9              10               11                12               13                 14                 15
            dateList.append([row.date.date(), row.start_time.time(), row.end_time.time(), row.driving_hours.time(), row.id, row.week_beginning, row.breaks, row.other_work, row.poa, row.total_rest, row.end_of_week, row.end_of_shift, row.utc_plusone, row.start_of_week, row.holiday_sick, row.holiday_NAH])

            #newList.append([row[0], row[1].strftime('%H:%M'), row[2].strftime('%H:%M'), str(hrsWorked)[:-3], str(hrsWorkedSubbed)[:-3], str(overtime)[:-3], str(row[3]), row[4], row[5], strfdelta(eval(row[6]), '%H:%M'), row[7].strftime('%H:%M:%S'), row[8].strftime('%H:%M'), row[9].strftime('%H:%M'), row[10], str(break_over_official), row[13]])

            #newList.append([row[0], '0:00',                  '0:00',                   '0:00',               '0:00',                    '0:00',            '4:00:S',    row[4], row[5], '0:00',                            '4:00:S',                    '0:00',                  '0:00',                    None,      '0:00',                 row[13]]) # NONE - row[10]= end of week, what to do with this?

            # NEW LIST       0-DATE, 1-START_TIME,             2-END_TIME,               3-HOURSWORKED,        4-HOURSWORKEDminusOB,      5-OVERTIME,        6-DRIVING,  7-ROWid 8-Wkbn, 9-OFFICIAL_BREAKS,                 10-OTHER WORK,               11-POA,                   12-TOTAL_REST,           13-endWk,   14-BREAK_OVER_OFFICIAL, 15-START OF WEEK, 16 - HOLIDAY_SICK, 17-HOLIDAY_NOADDEDHOURS

    newList = []

    for row in dateList:
        if row[1] != None: #,None,None
            hrsWorked = datetime.combine(row[0],row[2])-datetime.combine(row[0],row[1])
            hrsWorkedSubbed = hrsWorked-eval(row[6]) # row[6] --> official breaks; 0,15,30,45
            # if end_of_shift false
            if row[11] == False:
                break_over_official = breakOverOfficial(row[9], hrsWorked, eval(row[6]))
            else:
                break_over_official = breakOverOfficial_EndShiftTrue(row[9], row[2], hrsWorked, eval(row[6]), row[12])

            # avoiding negative times
            if hrsWorkedSubbed <= timedelta(hours=8, minutes=45):
                overtime = '0:00'
            else:
                overtime = hrsWorkedSubbed-timedelta(hours=8)

            # this gets the DAY of the date
            day = datetime.strptime(row[0].isoformat(), '%Y-%m-%d').strftime("%A")
            if day == 'Saturday' or day == 'Sunday':
                if row[0]==date(2019,3,30):
                    pass
                else:
                    overtime = hrsWorked
                    hrsWorked, hrsWorkedSubbed = '0:00', '0:00' # would be just 0 but are 0:00 to allow for [:-3] das

            # adds data to list, [:-3] cuts off seconds (which are not needed)
            newList.append([row[0], row[1].strftime('%H:%M'), row[2].strftime('%H:%M'), str(hrsWorked)[:-3], str(hrsWorkedSubbed)[:-3], str(overtime)[:-3], str(row[3]), row[4], row[5], strfdelta(eval(row[6]), '%H:%M'), row[7].strftime('%H:%M:%S'), row[8].strftime('%H:%M'), row[9].strftime('%H:%M'), row[10], str(break_over_official), row[13], row[14], row[15]])


        # NEW LIST 0-DATE, 1-START_TIME, 2-END_TIME, 3-HOURSWORKED, 4-HOURSWORKEDminusOB, 5-OVERTIME, 6-DRIVINGHOURS, 7-ROW_ID, 8-WEEK_BEGINNING, 9-OFFICIAL_BREAKS, 10-OTHER WORK, 11-POA, 12-TOTAL_REST, 13-END_OF_WEEK, 14-BREAK_OVER_OFFICIAL, 15-START OF WEEK, 16-HOLIDAY_SICK, 17-HOLIDAY_NOADDEDHOURS

        else:                                                               #DRIVING                            #OTHER
            newList.append([row[0], '0:00', '0:00', '0:00', '0:00', '0:00', '0:00:00', row[4], row[5], '0:00:00', '0:00:00', '0:00', '0:00', row[10], '0:00:00', row[13], row[14], row[15]]) # NONE

    # sorts list by the date
    newList.sort(key=lambda x:x[0])

    return newList

def deleteRow(row_id):
    Work.query.filter_by(id=row_id).delete()
    db.session.commit()

# CURRENT WEEKLY CUMULATIVE SUMS
def getWeeklySum(listHours):
    # get date of start of the week
    currentDay = datetime.today()
    start_week = (currentDay - timedelta(days=currentDay.weekday())) #.strftime('%Y-%m-%d')
    diff = currentDay - start_week
    week_list = [(start_week + timedelta(days=i)).date() for i in range(diff.days+1)]

    cumuls = [i for i in listHours for j in week_list if i[0]==j]

    sumHours = timedelta()

    # adds up work hours
    for x in cumuls:
        if x[4] is not int() and x[4]!='0': # handles if holiday/sick
            (h, m) = x[4].split(':')
            d = timedelta(hours=int(h), minutes=int(m))
            sumHours += d

    sumOvertime = timedelta()
    # adds up overtime hours
    for x in cumuls:
        if x[5] is not int() and x[5] != '0': # handles if holiday/sick
            (h, m) = x[5].split(':')
            d = timedelta(hours=int(h), minutes=int(m))
            sumOvertime += d

    # format hours
    sumHours = strfdelta(sumHours, '%H:%M')
    sumOvertime = strfdelta(sumOvertime, '%H:%M')

    return sumHours, sumOvertime

def weeklySum2(listHours):
    if listHours != []: # if listHours not empty -- e.g. new user or no data
        cols = list(zip(*listHours))
        array_hours = list(zip(cols[4], cols[8]))
        array_overtime = list(zip(cols[5], cols[8]))

        driving_plus_other=[]
        for i,j in zip(cols[6],cols[10]):
            h_i, m_i, s_i=i.split(':')
            h_j, m_j, s_j=j.split(':')
            ijSum = timedelta(hours=int(h_i),minutes=int(m_i))+timedelta(hours=int(h_j),minutes=int(m_j))
            driving_plus_other.append(strfdelta(ijSum,'%H:%M'))

        array_drivingPlusOther = list(zip(driving_plus_other,cols[8]))

        array_poa = list(zip(cols[11], cols[8]))
        array_breaksAfterOB = list(zip(cols[14],cols[8]))
        array_driving = list(zip(cols[6],cols[8]))
        array_other = list(zip(cols[10],cols[8]))

        dct_drivingPlusOther = {} # this is WORK HOURS.
        dct_driving = {}
        dct_poa = {}
        dct_breaksAfterOB = {}
        dct_other = {}
        dct_hours = {}
        dct_overtime = {}

        for time, weekbegin in array_hours:
            if time not in ('0'):
                dct_hours.setdefault(weekbegin,timedelta())
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_hours[weekbegin]+=d

        for time, weekbegin in array_overtime:
            if time not in (0,'0'):
                dct_overtime.setdefault(weekbegin, timedelta())
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_overtime[weekbegin]+=d
            else:
                dct_overtime.setdefault(weekbegin, timedelta())
                (h,m)=0,0
                d = timedelta(hours=int(h), minutes=int(m))
                dct_overtime[weekbegin]+=d

        for time, weekbegin in array_drivingPlusOther:
            if time not in ('0'):
                dct_drivingPlusOther.setdefault(weekbegin,timedelta(0))
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_drivingPlusOther[weekbegin]+=d

        for time, weekbegin in array_poa:
            if time not in ('0'):
                dct_poa.setdefault(weekbegin,timedelta(0))
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_poa[weekbegin]+=d

        for time, weekbegin in array_breaksAfterOB:
            if time not in ('0'):
                dct_breaksAfterOB.setdefault(weekbegin,timedelta(0))
                (h,m,s)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_breaksAfterOB[weekbegin]+=d

        for time, weekbegin in array_driving:
            if time not in ('0'):
                dct_driving.setdefault(weekbegin,timedelta(0))
                t = time.split(':')
                t+=[None]*(3-len(t)) # max 3 items
                (h,m,s)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_driving[weekbegin]+=d

        for time, weekbegin in array_other:
            if time not in ('0'):
                dct_other.setdefault(weekbegin,timedelta(0))
                t = time.split(':')
                t+=[None]*(3-len(t)) # max 3 items
                (h,m,s)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_other[weekbegin]+=d

        weeks = [i[0] for i in dct_hours.items()] # get keys which are the week beginnings

        return dct_hours, dct_overtime, weeks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other
    else: # when new user or no data
        return 0,0,[],0,0,0,0,0

def getCumul(week_Begin, listHours):
    if listHours != []:
        dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)
        if isinstance(week_Begin, str):
            cumul_hrs = strfdelta(dct_hours[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_overtime = strfdelta(dct_overtime[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_drivingPlusOther = strfdelta(dct_drivingPlusOther[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_poa = strfdelta(dct_poa[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_breaksAfterOB = strfdelta(dct_breaksAfterOB[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_driving = strfdelta(dct_driving[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            cumul_other = strfdelta(dct_other[datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S')], '%H:%M')
            return cumul_hrs, cumul_overtime, datetime.strptime(week_Begin, '%Y-%m-%d %H:%M:%S'), cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other
        else:
            cumul_hrs = strfdelta(dct_hours[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_overtime = strfdelta(dct_overtime[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_drivingPlusOther = strfdelta(dct_drivingPlusOther[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_poa = strfdelta(dct_poa[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_breaksAfterOB = strfdelta(dct_breaksAfterOB[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_driving = strfdelta(dct_driving[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_other = strfdelta(dct_other[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            return cumul_hrs, cumul_overtime, week_Begin, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other
    else:
        return 0,0,0,0,0,0,0

def biannual_num(week_num):
    if week_num >= 1 and week_num <= 26:
        return 'H1'
    elif week_num >= 27 and week_num <= 53:
        return 'H2'
    else:
        raise Exception('Week number not defined')

def weekDivider(dct, week_num):
    week_nums = sorted([int(n.split(',')[1]) for n in dct]) # get week numbers
    divisor = (week_nums.index(int(week_num)))+1

    return divisor


def averagesWorkHours(listHours):
    __, __, __, dct_drivingPlusOther, __, __, __, __ = weeklySum2(listHours) # __ to ignore rest of returned items
    hlfs = {'H1':{},'H2':{}} # year halves. 26 weeks each
    # splits the driving plus other dict into a list of tuples
    list_drivingOther = list(zip(dct_drivingPlusOther.keys(), dct_drivingPlusOther.values()))

    # sets right format for key so it includes the week number
    dpo_list = [(k.strftime('%Y-%m-%d %H:%M:%S')+','+k.strftime("%V"), v) for k,v in list_drivingOther]

    # not sure if needed, but keep in otherwise just in case. Will remove later if not needed
    dpo_list = [list(elem) for elem in dpo_list]
    dpo_list = sorted(dpo_list, key=lambda x:(x[0].split(','))[0])

    # splits the driving plus other data into year halves
    for week_begin, hrs in dpo_list:
        week, week_num = week_begin.split(',')
        year_section = biannual_num(int(week_num))
        hlfs[year_section].setdefault(week_begin, timedelta())
        hlfs[year_section].update({week_begin:hrs})

    # list of tuples of work hours data
    h1_list = [(k,v) for k,v in hlfs['H1'].items()]
    h2_list = [(k,v) for k,v in hlfs['H2'].items()]

    # sorts list of tuples by WEEK NUMBER. Needed for use on server
    h1_list = sorted(h1_list, key=lambda x:(x[0].split(','))[0])
    h2_list = sorted(h2_list, key=lambda x:(x[0].split(','))[0])

    h1_dict = {}
    h2_dict = {}

    # Running sum of weekly WORK HOURS for year half 1 and half 2
    sum1=timedelta()
    for n in h1_list:
        sum1+=n[1]
        h1_dict[n[0]]=sum1

    sum1=timedelta()
    for n in h2_list:
        sum1+=n[1]
        h2_dict[n[0]]=sum1

    hlfs_runningSum = {'H1':h1_dict,'H2':h2_dict}

    # ONLY RETURN CURRENT YEAR HALF
    #return hlfs_runningSum[biannual_num(int(datetime.today().strftime('%V')))]

    return hlfs_runningSum['H1'], hlfs_runningSum['H2']


def averagesTotalHours(listHours):
    __, __, __, dct_drivingPlusOther, __, __, __, __ = weeklySum2(listHours)

    hlfs = {'H1':{},'H2':{}} # year halves. 26 weeks each

    weekBegin_holidayAddedHours = [(row[8], row[16]) for row in listHours]
    # returns something like [('week beginning', True), ('week beginning'), False]

    # adds 8 hours to weeks with holiday added hours TRUE
    for row in weekBegin_holidayAddedHours:
        if row[1] == True:
            dct_drivingPlusOther[row[0]]+=timedelta(hours=8)

    listTotalHours = list(zip(dct_drivingPlusOther.keys(), dct_drivingPlusOther.values()))

    total_list = [(k.strftime('%Y-%m-%d %H:%M:%S')+','+k.strftime("%V"), v) for k,v in listTotalHours]

    total_list = [list(elem) for elem in total_list]
    total_list = sorted(total_list, key=lambda x:(x[0].split(','))[0])

    for week_begin, hrs in total_list:
        week, week_num = week_begin.split(',')
        year_section = biannual_num(int(week_num))
        hlfs[year_section].setdefault(week_begin, timedelta())
        hlfs[year_section].update({week_begin:hrs})

    h1_list = [(k,v) for k,v in hlfs['H1'].items()]
    h2_list = [(k,v) for k,v in hlfs['H2'].items()]

    h1_list = sorted(h1_list, key=lambda x:(x[0].split(','))[0])
    h2_list = sorted(h2_list, key=lambda x:(x[0].split(','))[0])

    h1_dict = {}
    h2_dict = {}

    sum1=timedelta()
    for n in h1_list:
        sum1+=n[1]
        h1_dict[n[0]]=sum1

    sum1=timedelta()
    for n in h2_list:
        sum1+=n[1]
        h2_dict[n[0]]=sum1

    hlfs_runningSum = {'H1':h1_dict,'H2':h2_dict}

    # ONLY RETURN CURRENT YEAR HALF
    #return hlfs_runningSum[biannual_num(int(datetime.today().strftime('%V')))]

    return hlfs_runningSum['H1'], hlfs_runningSum['H2']

def getAverages(week_begin, listHours):
    runningSum_drivingOther_h1, runningSum_drivingOther_h2 = averagesWorkHours(listHours)
    runningSum_totalHours_h1, runningSum_totalHours_h2 = averagesTotalHours(listHours)

    week,week_num=week_begin.split(',')

    if listHours != []:
        if isinstance(week_begin, str):
            if biannual_num(int(datetime.today().strftime('%V'))) == 'H1':
                divisor=weekDivider(runningSum_drivingOther_h1, week_num)

                runsum_drivingOther_Avg = strfdelta(runningSum_drivingOther_h1[week_begin]/(int(divisor)), '%H:%M')
                runsum_drivingOther = strfdelta(runningSum_drivingOther_h1[week_begin], '%H:%M')

                divisor=weekDivider(runningSum_totalHours_h1, week_num)

                runsum_totalHours_Avg = strfdelta(runningSum_totalHours_h1[week_begin]/(int(divisor)), '%H:%M')
                runsum_totalHours = strfdelta(runningSum_totalHours_h1[week_begin], '%H:%M')

                return runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, divisor

            else:
                divisor=weekDivider(runningSum_drivingOther_h2, week_num)

                runsum_drivingOther_Avg = strfdelta(runningSum_drivingOther_h2[week_begin]/(int(divisor)), '%H:%M')
                runsum_drivingOther = strfdelta(runningSum_drivingOther_h2[week_begin], '%H:%M')

                divisor=weekDivider(runningSum_totalHours_h2, week_num)

                runsum_totalHours_Avg = strfdelta(runningSum_totalHours_h2[week_begin]/(int(divisor)), '%H:%M')
                runsum_totalHours = strfdelta(runningSum_totalHours_h2[week_begin], '%H:%M')

                return runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, divisor

        else:
            if biannual_num(int(datetime.today().strftime('%V'))) == 'H1':
                divisor=weekDivider(runningSum_drivingOther_h1, week_num)

                runsum_drivingOther_Avg = strfdelta(runningSum_drivingOther_h1[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)]/(int(divisor)), '%H:%M')
                runsum_drivingOther = strfdelta(runningSum_drivingOther_h1[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')

                divisor=weekDivider(runningSum_totalHours_h1, week_num)

                runsum_totalHours_Avg = strfdelta(runningSum_totalHours_h1[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)]/(int(divisor)), '%H:%M')
                runsum_totalHours = strfdelta(runningSum_totalHours_h1[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')

                return runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, divisor

            else:
                divisor=weekDivider(runningSum_drivingOther_h2, week_num)

                runsum_drivingOther_Avg = strfdelta(runningSum_drivingOther_h2[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)]/(int(divisor)-26), '%H:%M')
                runsum_drivingOther = strfdelta(runningSum_drivingOther_h2[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')

                divisor=weekDivider(runningSum_totalHours_h2, week_num)

                runsum_totalHours_Avg = strfdelta(runningSum_totalHours_h2[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)]/(int(divisor)), '%H:%M')
                runsum_totalHours = strfdelta(runningSum_totalHours_h2[week_begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')

                return runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, divisor
    else:
        return 0,0,0,0


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required # login required decorator from flask_login
def index():
    form = HoursForm()
    cumul_form = CumulativeDropdown()
    runsum_form = RunningSumDropdown()

    listHours = listDates(current_user.get_id())
    dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)
    wks2 = [wkbgn.strftime('%A') + ' ' + wkbgn.strftime('%-d') + ' ' + wkbgn.strftime('%b') + ' ' + wkbgn.strftime('%Y') for wkbgn in wks]

    cumulChoices = [('0', 'Cumulative for Week Beginning'), *[(str(i),j) for i,j in zip(wks,wks2)]]
    cumulChoices[1:]= sorted(cumulChoices[1:], key=lambda x:datetime.strptime(x[0],'%Y-%m-%d %H:%M:%S'))

    cumul_form.week_select.choices=cumulChoices

    runsumChoices = [('0', 'Select Week'), *[(str(i)+','+i.strftime("%V"),'Week '+i.strftime("%V")+': '+j) for i,j in zip(wks,wks2)]]
    runsumChoices[1:] = sorted(runsumChoices[1:], key=lambda x:datetime.strptime(x[0][:-3],'%Y-%m-%d %H:%M:%S'))


    runsum_form.week_select1.choices=runsumChoices

    curUserId = current_user.get_id()

    if form.submit.data and form.validate_on_submit():
        dateEntry = form.dateEntry.data
        stime = form.start_time.data
        etime = form.end_time.data
        holSick = form.holiday_sick.data
        holNAH = form.holiday_noAddedHours.data
        drivingHrs = form.driving_hours.data
        break_length = form.breaks.data
        other_work = form.other_work.data
        poa = form.poa.data
        total_rest = form.total_rest.data
        end_of_week = form.end_of_week.data
        start_of_week = form.start_of_week.data
        end_of_shift = form.end_of_shift.data
        week_beginning = (dateEntry - timedelta(days=dateEntry.weekday()))
        utc_plusone = form.utc_plusone.data

        if holSick == False and holNAH == False:
            mergedDate_StartTime = datetime.combine(dateEntry, stime)
            mergedDate_EndTime = datetime.combine(dateEntry, etime)
            mergedDate_Driving = datetime.combine(dateEntry, drivingHrs)
            mergedOther_work = datetime.combine(dateEntry, other_work)
            mergedPoa = datetime.combine(dateEntry, poa)
            mergedTotal_rest = datetime.combine(dateEntry, total_rest)
        else:
            mergedDate_StartTime = None
            mergedDate_EndTime = None
            mergedDate_Driving = None
            mergedOther_work = None
            mergedPoa = None
            mergedTotal_rest = None

        hrs = Work(date=dateEntry, holiday_sick=holSick, start_time=mergedDate_StartTime, end_time=mergedDate_EndTime, driving_hours=mergedDate_Driving, week_beginning=week_beginning, user_id=curUserId, breaks=break_length, other_work=mergedOther_work, poa=mergedPoa, total_rest=mergedTotal_rest, end_of_week=end_of_week, end_of_shift=end_of_shift, utc_plusone=utc_plusone, start_of_week=start_of_week, holiday_NAH=holNAH)
        db.session.add(hrs)
        db.session.commit()

        listHours = listDates(curUserId)

        return redirect(url_for('main.index'))

    if cumul_form.validate_on_submit():
        week_begin = cumul_form.week_select.data

        listHours = listDates(current_user.get_id())

        # what is the need for this?:
        dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)

        cumul_hrs, cumul_overtime, week_Begin_dt, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other = getCumul(week_begin, listHours)
        week_Begin_dt = week_Begin_dt.strftime('%A %-d %b %Y')

        cumul_list = [cumul_hrs, cumul_overtime, week_Begin_dt, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other]

        session['cumul_list'] = cumul_list
        return redirect(url_for('main.index'))

    if runsum_form.validate_on_submit():
        week_begin = runsum_form.week_select1.data

        listHours = listDates(current_user.get_id())

        runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, week_num_inContext = getAverages(week_begin, listHours)

        week = datetime.strptime(week, '%Y-%m-%d %H:%M:%S')
        week = week.strftime('%A %-d %b %Y')

        session['week_list'] = [week, week_num, week_num_inContext]
        session['runsum_drivingOther_list'] = [runsum_drivingOther, runsum_drivingOther_Avg]
        session['runsum_totalHours_list'] = [runsum_totalHours, runsum_totalHours_Avg]

        return redirect(url_for('main.index'))


    # row deletion
    if request.method == 'POST':
        if 'delete' in request.form:
            row_id = request.form['delete'] # gets the row id from the delete button
            if row_id is not None:
                deleteRow(row_id)
                listHours = listDates(current_user.get_id())

                return redirect(url_for('main.index'))


    listHours = listDates(current_user.get_id())


    listHours = restDailyWeekly(listHours)


    # gets current week cumulatives -- NEED TO INCLUDE OTHERS
    currWeeklyHours, currWeeklyOvertime = getWeeklySum(listHours)

    #cumul_hrs, cumul_overtime, week, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other =

    #return render_template('index.html', form=form, cumul_form=cumul_form, hoursDb = listHours, wks=wks, wks2=wks2, zip=zip, cumul_hrs=cumul_hrs, cumul_overtime=cumul_overtime, cumul_drivingPlusOther=cumul_drivingPlusOther, currWeeklyHours=currWeeklyHours, currWeeklyOvertime=currWeeklyOvertime, cumul_poa=cumul_poa,cumul_breaksAfterOB=cumul_breaksAfterOB, cumul_driving=cumul_driving, cumul_other=cumul_other, week=week)
    return render_template('index.html', form=form, cumul_form=cumul_form, runsum_form=runsum_form, hoursDb = listHours, wks=wks, wks2=wks2, zip=zip, currWeeklyHours=currWeeklyHours, currWeeklyOvertime=currWeeklyOvertime)


@bp.route('/mydata')
def download_data():

    listHours = listDates(current_user.get_id())
    dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)

    # WORK HOURS = DRIVING PLUS OTHER


    #columnsNew=['Start', 'End', 'Hours Worked', 'Official Break', 'Hours Worked Minus Official Break', 'Other Breaks', 'Overtime', 'Driving Hours', 'Other Work', 'Work Hours', 'POA', 'Total Breaks', 'Rest Completed']

    columns = ['Start', 'End', 'Hours Worked', 'Hours Worked Minus Official Break', 'Overtime', 'Driving', 'Break', 'Other Work', 'POA', 'Break Over Official']
    columnsNew = ['Start', 'End', 'Hours Worked', 'Break', 'Hours Worked Minus Official Break', 'Break Over Official', 'Overtime', 'Driving', 'Other Work', 'POA']

    index=[row[0] for row in listHours]


    # delete rows not needed
    for row in listHours:
        del row[0]
        del row[7-1]
        del row[8-2]
        del row[12-3]
        del row[13-4]
        del row[15-5]
        del row[16-6]
        del row[17-7]

    hours_data = pd.DataFrame(listHours, index=index, columns=columns)
    # SWAP COLUMNS TO MAKE BETTER FORMATTED? reindex does not work


    dct_hours = {k.date():strfdelta(v,'%H:%M') for k,v in dct_hours.items()}
    dct_overtime = {k.date():strfdelta(v,'%H:%M') for k,v in dct_overtime.items()}

    dct_drivingPlusOther = {k.date():strfdelta(v,'%H:%M') for k,v in dct_drivingPlusOther.items()}
    dct_poa = {k.date():strfdelta(v,'%H:%M') for k,v in dct_poa.items()}
    dct_breaksAfterOB = {k.date():strfdelta(v,'%H:%M') for k,v in dct_breaksAfterOB.items()}
    dct_driving = {k.date():strfdelta(v,'%H:%M') for k,v in dct_driving.items()}
    dct_other = {k.date():strfdelta(v,'%H:%M') for k,v in dct_other.items()}


    srs_hours = pd.Series(dct_hours).to_frame('Cumulative Hrs')
    srs_overtime = pd.Series(dct_overtime).to_frame('Cumulative Overtime')

    srs_drivingPlusOther = pd.Series(dct_drivingPlusOther).to_frame('Cumulative Work Hours')
    srs_poa = pd.Series(dct_poa).to_frame('Cumulative POA')
    srs_breaksAfterOB = pd.Series(dct_breaksAfterOB).to_frame('Cumulative After Official Break')

    #hours_data = (pd.concat([hours_data, srs_hours, srs_overtime, srs_drivingPlusOther, srs_poa, srs_breaksAfterOB], axis=1, sort=True)).fillna('')
    hours_data = (pd.concat([hours_data, srs_hours, srs_overtime, srs_breaksAfterOB, srs_poa, srs_drivingPlusOther], axis=1, sort=True)).fillna('')
    #print(hours_data)

    fn = 'data_'+(datetime.today().date()).strftime('%d-%b-%y')+'.xlsx'

    # creates excel from pandas dataframe and downloads it
    #hours_data = pd.DataFrame([{'a':i, 'b':i*2, 'c':i^3} for i in range(3)])

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    hours_data.to_excel(writer, sheet_name='Sheet1')

    workbook = writer.book
    worksheet = writer.sheets['Sheet1']

    formatTimes = workbook.add_format({'num_format':'[hh]:mm'})

    worksheet.set_column('A:A',14)
    worksheet.set_column('D:D',13)
    worksheet.set_column('E:E',27)
    worksheet.set_column('G:H',12)
    worksheet.set_column('I:I',13)
    worksheet.set_column('J:J',8)
    worksheet.set_column('K:K',14)
    worksheet.set_column('L:L',12)
    worksheet.set_column('M:N',19)
    worksheet.set_column('O:O',13)
    worksheet.set_column('P:P',25)
    worksheet.set_column('B:P',None,formatTimes)

    writer.save()
    output.seek(0)

    return send_file(output, attachment_filename=fn, as_attachment=True)

@bp.route('/weeklydata')
def download_weekly_runsum():
    listHours = listDates(current_user.get_id())

    runningSum_drivingOther_h1, runningSum_drivingOther_h2 = averagesWorkHours(listHours)
    runningSum_totalHours_h1, runningSum_totalHours_h2 = averagesTotalHours(listHours)

    #runsum_drivingOther, runsum_drivingOther_Avg, runsum_totalHours, runsum_totalHours_Avg, week, week_num, week_num_inContext = getAverages(week_begin, listHours)

    # INDEX -> WEEK BEGIN

    '''
    for time, weekbegin in array_hours:
        if time not in ('0'):
            dct_hours.setdefault(weekbegin,timedelta())
            (h,m)=time.split(':')
            d = timedelta(hours=int(h), minutes=int(m))
            dct_hours[weekbegin]+=d

    return __, __, __, runsum_totalHours_Avg, __, __, __
    '''

    # get averages
    runsum_DO_h1_avg = {}
    runsum_DO_h2_avg = {}

    runsum_TH_h1_avg = {}
    runsum_TH_h2_avg = {}

    for week_begin,val in runningSum_drivingOther_h1.items():
        __, runsum_drivingOther_Avg, __, __, __, __, __ = getAverages(week_begin, listHours)
        runsum_DO_h1_avg.setdefault(week_begin, timedelta())
        h,m = runsum_drivingOther_Avg.split(':')
        td = timedelta(hours=int(h),minutes=int(m))
        runsum_DO_h1_avg[week_begin]+=td

    for week_begin,val in runningSum_drivingOther_h2.items():
        __, runsum_drivingOther_Avg, __, __, __, __, __ = getAverages(week_begin, listHours)
        runsum_DO_h2_avg.setdefault(week_begin, timedelta())
        h,m = runsum_drivingOther_Avg.split(':')
        td = timedelta(hours=int(h),minutes=int(m))
        runsum_DO_h2_avg[week_begin]+=td

    for week_begin,val in runningSum_totalHours_h1.items():
        __, __, __, runsum_totalHours_Avg, __, __, __ = getAverages(week_begin, listHours)
        runsum_TH_h1_avg.setdefault(week_begin, timedelta())
        h,m = runsum_totalHours_Avg.split(':')
        td = timedelta(hours=int(h),minutes=int(m))
        runsum_TH_h1_avg[week_begin]+=td

    for week_begin,val in runningSum_totalHours_h2.items():
        __, __, __, runsum_totalHours_Avg, __, __, __= getAverages(week_begin, listHours)
        runsum_TH_h2_avg.setdefault(week_begin, timedelta())
        h,m = runsum_totalHours_Avg.split(':')
        td = timedelta(hours=int(h),minutes=int(m))
        runsum_TH_h2_avg[week_begin]+=td



    runningSum_totalHours_h1 = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runningSum_totalHours_h1.items()}

    runningSum_totalHours_h2 = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runningSum_totalHours_h2.items()}

    runningSum_drivingOther_h1 = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runningSum_drivingOther_h1.items()}

    runningSum_drivingOther_h2 = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runningSum_drivingOther_h2.items()}

    runsum_DO_h1_avg = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runsum_DO_h1_avg.items()}

    runsum_DO_h2_avg = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runsum_DO_h2_avg.items()}

    runsum_TH_h1_avg = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runsum_TH_h1_avg.items()}

    runsum_TH_h2_avg = {datetime.strptime(k.split(',')[0], '%Y-%m-%d %H:%M:%S').date():strfdelta(v, '%H:%M') for k,v in runsum_TH_h2_avg.items()}




    srs_runsum_drivingOther_h1=pd.Series(runningSum_drivingOther_h1)        #.to_frame('Work Hours')
    srs_runsum_drivingOther_h2=pd.Series(runningSum_drivingOther_h2)        #.to_frame('Work Hours')

    srs_runsum_DO_combined = srs_runsum_drivingOther_h1.append(srs_runsum_drivingOther_h2)
    srs_runsum_DO_combined = srs_runsum_DO_combined.to_frame('Work Hours')


    srs_runsum_totalHours_h1=pd.Series(runningSum_totalHours_h1)    #.to_frame('Total Hours')
    srs_runsum_totalHours_h2=pd.Series(runningSum_totalHours_h2)    #.to_frame('Total Hours')

    srs_runsum_TH_combined = srs_runsum_totalHours_h1.append(srs_runsum_totalHours_h2)
    srs_runsum_TH_combined = srs_runsum_TH_combined.to_frame('Total Hours')


    srs_runsum_DO_avg_h1 = pd.Series(runsum_DO_h1_avg)
    srs_runsum_DO_avg_h2 = pd.Series(runsum_DO_h2_avg)

    srs_runsum_DO_avg_comb = srs_runsum_DO_avg_h1.append(srs_runsum_DO_avg_h2)
    srs_runsum_DO_avg_comb = srs_runsum_DO_avg_comb.to_frame('Work Hours Average')

    srs_runsum_TH_avg_h1 = pd.Series(runsum_TH_h1_avg)
    srs_runsum_TH_avg_h2 = pd.Series(runsum_TH_h2_avg)

    srs_runsum_TH_avg_comb = srs_runsum_TH_avg_h1.append(srs_runsum_TH_avg_h2)
    srs_runsum_TH_avg_comb = srs_runsum_TH_avg_comb.to_frame('Total Hours Average')


    weekly_data = pd.concat([srs_runsum_DO_combined, srs_runsum_TH_combined, srs_runsum_DO_avg_comb, srs_runsum_TH_avg_comb], axis=1, sort=True)

    print(weekly_data.dtypes)

    fn = 'weeklydata_'+(datetime.today().date()).strftime('%d-%b-%y')+'.xlsx'


    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    weekly_data.to_excel(writer, sheet_name='Sheet1')

    workbook = writer.book
    worksheet = writer.sheets['Sheet1']

    formatTimes = workbook.add_format({'num_format':'hh:mm'})

    worksheet.set_column('B:C',None,formatTimes)

    worksheet.set_column('A:A',13)
    worksheet.set_column('B:E',20)


    writer.save()
    output.seek(0)


    return send_file(output, attachment_filename=fn, as_attachment=True)
