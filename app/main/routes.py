from app import db
from flask import render_template, flash, redirect, request, url_for, send_file
from app.main.forms import HoursForm

from flask_login import current_user, login_user, logout_user, login_required

from app.models import User, Work
from app.main import bp

from werkzeug.urls import url_parse
from datetime import datetime, timedelta, date
from string import Template
import pandas as pd
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
    # total_rest == datetime.datetime,
    # hours_worked == datetime.timedelta
    # official_break == datetime.timedelta

    # convert total_rest to timedelta:
    h,m=total_rest.strftime('%-H:%-M').split(':')
    total_rest_td = timedelta(hours=int(h),minutes=int(m))

    # 24 hours minus hours_worked
    hours_worked_opp = timedelta(hours=24)-hours_worked

    # returns timedelta
    return (total_rest_td-(hours_worked_opp+official_break))

# IF DATA TAKEN FROM **TODAY'S** SHIFT == TRUE, ALSO NEEDS TO SORT IF UTC+1, THEN ADD ONE HOUR TO TOTAL REST?
def breakOverOfficial_EndShiftTrue(total_rest, end, hours_worked, official_break, utc_plusone):
    # convert total_rest to timedelta
    # MAYBE USE datetime.combine(date.min,TIMEOBJ)-datetime.min instead? returns a timedelta obj
    h,m=total_rest.strftime('%-H:%-M').split(':')
    total_rest_td = timedelta(hours=int(h),minutes=int(m)) #treos

    end_td_r2 = timedelta(hours=24)-(datetime.combine(date.min,end)-datetime.min)

    total_rest_td = total_rest_td + end_td_r2
    if utc_plusone == True:
        total_rest_td += timedelta(hours=1)

    hours_worked_opp = timedelta(hours=24)-hours_worked

    #return (total_rest_td-(hours_worked_opp+official_break))

    return (total_rest_td-(official_break+hours_worked_opp))

# NEED TO ADD START OF WEEK ON FORM AND DATABASE

# column [13] is end_of_week, column [2] is END TIME, column [15] is start_of_week
def restDailyWeekly(listHours):
    for row in listHours:
        row_index = listHours.index(row)
        if row_index == 0:
            row.append('')
        else:
            if row[15] == False:
                # start/end are STRINGS!
                endtime_day_before = listHours[row_index-1][2]
                starttime_current_day = listHours[row_index][1]
                h_e,m_e=endtime_day_before.split(':')
                h_s,m_s=starttime_current_day.split(':')

                end_before_td = timedelta(hours=int(h_e),minutes=int(m_e))
                start_current_td = timedelta(hours=int(h_s),minutes=int(m_s))

                dailyRestComp = str(start_current_td + (timedelta(hours=24)-end_before_td))

                #row.append(dailyRestComp)
                row.append(str(str(dailyRestComp)+', D'))
            else: # weekly rest
                if listHours[row_index-1][13]==True:
                    endtime_day_before = datetime.strptime(listHours[row_index-1][2],'%H:%M').time()
                    starttime_current_day = datetime.strptime(listHours[row_index][1],'%H:%M').time()

                    weeklyRestComp=datetime.combine(listHours[row_index][0],starttime_current_day)-datetime.combine(listHours[row_index-1][0],endtime_day_before)

                    row.append(strfdelta(weeklyRestComp, '%H:%M')+', W') #str(str(weeklyRestComp)
                else:
                    row.append('Error. No End of Week has been defined')
    return listHours






def listDates(id):
    listHours = Work.query.filter_by(user_id=id)

    dateList = []
    for row in listHours:
        if row.start_time == None and row.end_time == None: # if sick/holiday              #break,
            dateList.append([row.date.date(), None, None, None, row.id, row.week_beginning, None, None, None, None, row.end_of_week, None, None,row.start_of_week])
        else:
            dateList.append([row.date.date(), row.start_time.time(), row.end_time.time(), row.driving_hours.time(), row.id, row.week_beginning, row.breaks, row.other_work, row.poa, row.total_rest, row.end_of_week, row.end_of_shift, row.utc_plusone, row.start_of_week])

    newList = []
    #print('datelist:')
    #print(dateList)
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
                overtime = hrsWorked
                hrsWorked, hrsWorkedSubbed = '0:00', '0:00' # would be just 0 but are 0:00 to allow for [:-3] das

            # adds data to list, [:-3] cuts off seconds (which are not needed)
            newList.append([row[0], row[1].strftime('%H:%M'), row[2].strftime('%H:%M'), str(hrsWorked)[:-3], str(hrsWorkedSubbed)[:-3], str(overtime)[:-3], str(row[3])[:-3], row[4], row[5], strfdelta(eval(row[6]), '%H:%M'), row[7].strftime('%H:%M'), row[8].strftime('%H:%M'), row[9].strftime('%H:%M'), row[10], str(break_over_official), row[13]])

        # if start time, end time, and working hours are None (holiday/sick is True)
        else:
            newList.append([row[0], '0:00', '0:00', '0:00', '0:00', '0:00', '0:00', row[4], row[5], '0:00', '0:00', '0:00', '0:00', None, '0:00']) # NONE - row[10]= end of week, what to do with this?

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

    #print(listHours)
    cumuls = [i for i in listHours for j in week_list if i[0]==j]

    sumHours = timedelta()

    # adds up work hours
    for x in cumuls:
        if x[4] is not int(): # handles if holiday/sick
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
        cols = list(zip(*listHours)) # cols[8] == week beginning
        array_hours = list(zip(cols[4], cols[8]))
        array_overtime = list(zip(cols[5], cols[8]))

        driving_plus_other=[]
        for i,j in zip(cols[6],cols[10]):
            h_i, m_i=i.split(':')
            h_j, m_j=j.split(':')
            ijSum = timedelta(hours=int(h_i),minutes=int(m_i))+timedelta(hours=int(h_j),minutes=int(m_j))
            driving_plus_other.append(strfdelta(ijSum,'%H:%M'))

        array_drivingPlusOther = list(zip(driving_plus_other,cols[8]))

        array_poa = list(zip(cols[11], cols[8]))
        array_breaksAfterOB = list(zip(cols[14],cols[8]))
        array_driving = list(zip(cols[6],cols[8]))
        array_other = list(zip(cols[10],cols[8]))

        dct_drivingPlusOther = {}
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
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_driving[weekbegin]+=d

        for time, weekbegin in array_other:
            if time not in ('0'):
                dct_other.setdefault(weekbegin,timedelta(0))
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_other[weekbegin]+=d

        weeks = [i[0] for i in dct_hours.items()] # get keys which are the week beginnings

        return dct_hours, dct_overtime, weeks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other
    else: # when new user or no data
        return 0,0,[],0,0,0

def getCumul(week_Begin, listHours):
    if listHours != []:
        dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)
        if isinstance(week_Begin, str):
            print('GET CUMUL WEEK BEGIN')
            print(week_Begin)
            print(type(week_Begin))
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



# TEST PAGE -- DELETES WORK DB DATA
@bp.route('/start')
def start():
    # TESTING: DELETE WORK DB ROWS
    db.session.query(Work).delete()
    db.session.commit()

    return render_template('startpage.html')


# this will be the main page, with the hours form etc
@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required # login required decorator from flask_login
def index():
    form = HoursForm()

    curUserId = current_user.get_id()

    if form.submit.data and form.validate_on_submit():
        dateEntry = form.dateEntry.data
        stime = form.start_time.data
        etime = form.end_time.data
        holSick = form.holiday_sick.data
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


        if holSick == False:
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

        hrs = Work(date=dateEntry, holiday_sick=holSick, start_time=mergedDate_StartTime, end_time=mergedDate_EndTime, driving_hours=mergedDate_Driving, week_beginning=week_beginning, user_id=curUserId, breaks=break_length, other_work=mergedOther_work, poa=mergedPoa, total_rest=mergedTotal_rest, end_of_week=end_of_week, end_of_shift=end_of_shift, utc_plusone=utc_plusone, start_of_week=start_of_week)
        db.session.add(hrs)
        db.session.commit()

        listHours = listDates(curUserId)

        return redirect(url_for('main.index'))

    # row deletion
    if request.method == 'POST':
        if 'delete' in request.form:
            row_id = request.form['delete'] # gets the row id from the delete button
            if row_id is not None:
                deleteRow(row_id)
                listHours = listDates(current_user.get_id())

                return redirect(url_for('main.index'))
        elif 'cumuls' in request.form:
            week_Begin = request.form['cumuls']
            if week_Begin is not None:
                listHours = listDates(current_user.get_id())

                # what is the need for this?:
                dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)

                #print(week_Begin)
                cumul_hrs, cumul_overtime, week_Begin_dt, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other = getCumul(week_Begin, listHours)
                week_Begin_dt = week_Begin_dt.strftime('%A %-d %b %Y')
                return redirect(url_for('main.index', cumul_hrs=cumul_hrs, cumul_overtime=cumul_overtime, week=week_Begin_dt, cumul_drivingPlusOther=cumul_drivingPlusOther, cumul_poa=cumul_poa, cumul_breaksAfterOB=cumul_breaksAfterOB, cumul_driving=cumul_driving, cumul_other=cumul_other))

    listHours = listDates(current_user.get_id())
    listHours = restDailyWeekly(listHours)

    dct_hours, dct_overtime, wks, dct_drivingPlusOther, dct_poa, dct_breaksAfterOB, dct_driving, dct_other = weeklySum2(listHours)

    #print(wks)
    wks2 = [wkbgn.strftime('%A') + ' ' + wkbgn.strftime('%-d') + ' ' + wkbgn.strftime('%b') + ' ' + wkbgn.strftime('%Y') for wkbgn in wks]

    # gets current week cumulatives -- NEED TO INCLUDE OTHERS
    currWeeklyHours, currWeeklyOvertime = getWeeklySum(listHours)

    cumul_hrs, cumul_overtime, week, cumul_drivingPlusOther, cumul_poa, cumul_breaksAfterOB, cumul_driving, cumul_other = request.args.get('cumul_hrs'), request.args.get('cumul_overtime'),request.args.get('week'), request.args.get('cumul_drivingPlusOther'), request.args.get('cumul_poa'),request.args.get('cumul_breaksAfterOB'),request.args.get('cumul_driving'),request.args.get('cumul_other')

    return render_template('index.html', form=form, hoursDb = listHours, wks=wks, wks2=wks2, zip=zip, cumul_hrs=cumul_hrs, cumul_overtime=cumul_overtime, cumul_drivingPlusOther=cumul_drivingPlusOther, currWeeklyHours=currWeeklyHours, currWeeklyOvertime=currWeeklyOvertime, cumul_poa=cumul_poa,cumul_breaksAfterOB=cumul_breaksAfterOB, cumul_driving=cumul_driving, cumul_other=cumul_other, week=week)


@bp.route('/mydata')
def download_data():

    listHours = listDates(current_user.get_id())
    dct_hours, dct_overtime, wks = weeklySum2(listHours)

    # NEED TO GET
    columns=['Start', 'End', 'Hours Worked', 'Hours Worked Minus 45mins', 'Overtime', 'Driving Hours']
    index=[row[0] for row in listHours]

    for row in listHours:
        del row[0]
        del row[7-1]
        del row[8-2]

    #print(listHours)

    test_data = pd.DataFrame(listHours, index=index, columns=columns)

    #print('dct_hours')
    #print(dct_hours)

    dct_hours = {k.date():strfdelta(v,'%H:%M') for k,v in dct_hours.items()}
    dct_overtime = {k.date():strfdelta(v,'%H:%M') for k,v in dct_overtime.items()}

    srs_hours = pd.Series(dct_hours).to_frame('Cumulative Hrs')
    srs_overtime = pd.Series(dct_overtime).to_frame('Cumulative Overtime')

    test_data = (pd.concat([test_data, srs_hours, srs_overtime], axis=1, sort=True)).fillna('')
    #print(test_data)

    fn = 'data_'+(datetime.today().date()).strftime('%d-%b-%y')+'.xlsx'

    # creates excel from pandas dataframe and downloads it
    #test_data = pd.DataFrame([{'a':i, 'b':i*2, 'c':i^3} for i in range(3)])

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    test_data.to_excel(writer, sheet_name='Sheet1')

    workbook = writer.book
    worksheet = writer.sheets['Sheet1']

    formatTimes = workbook.add_format({'num_format':'hh:mm'})

    worksheet.set_column('A:A',14)
    worksheet.set_column('D:D',13)
    worksheet.set_column('E:E',25)
    worksheet.set_column('G:G',12)
    worksheet.set_column('H:H',12)
    worksheet.set_column('I:I',17)
    worksheet.set_column('B:I',None,formatTimes)

    writer.save()
    output.seek(0)

    return send_file(output, attachment_filename=fn, as_attachment=True)

'''

<p> Selected Week Cumulative Driving + Other Work Hours:<br><b>{{ cumul_drivingPlusOther[0:2] }} hours, {{ cumul_drivingPlusOther[3:5] }} minutes</b></p>

'''
