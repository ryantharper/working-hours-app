from app import app, db
from flask import render_template, flash, redirect, request, url_for, send_file
from app.forms import LoginForm, RegistrationForm, HoursForm
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Work
from werkzeug.urls import url_parse
from datetime import datetime, timedelta
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


def listDates(id):
    listHours = Work.query.filter_by(user_id=id)

    dateList = []
    for row in listHours:
        if row.start_time == None and row.end_time == None: # if sick/holiday
            dateList.append([row.date.date(), None, None, None, row.id, row.week_beginning])
        else:
            dateList.append([row.date.date(), row.start_time.time(), row.end_time.time(), row.driving_hours.time(), row.id, row.week_beginning])

    newList = [] # 0-date, 1-hoursworkedSUB45mins, 2-1SUB8hrs45mins, 3-drivingHrs, 4-row_id, 5-week_beginning (beginning of week)
    #print('datelist:')
    #print(dateList)
    for row in dateList:
        if row[1:4] != [None,None,None]:
            hrsWorked = datetime.combine(row[0],row[2])-datetime.combine(row[0],row[1])
            hrsWorkedSubbed = hrsWorked-timedelta(minutes=45)

            # avoiding negative times
            if hrsWorkedSubbed <= timedelta(hours=8, minutes=45):
                overtime = '0:00'
            else:
                overtime = hrsWorkedSubbed-timedelta(hours=8)
                # this gets the DAY of the date
                day = datetime.strptime(row[0].isoformat(), '%Y-%m-%d').strftime('%A')
                if day == 'Saturday' or day == 'Sunday':
                    overtime = hrsWorked
                    hrsWorked, hrsWorkedSubbed = '0:00', '0:00' # would be just 0 but are 0:00 to allow for [:-3]
            # adds data to list, [:-3] cuts off seconds (which are not needed)
            newList.append([row[0], row[1].strftime('%H:%M'), row[2].strftime('%H:%M'), str(hrsWorked)[:-3], str(hrsWorkedSubbed)[:-3], str(overtime)[:-3], str(row[3])[:-3], row[4], row[5]])

        # if start time, end time, and working hours are None (holiday/sick is True)
        else:
            newList.append([row[0], '0:00', '0:00', '0:00', '0:00', '0:00', '0:00', row[4], row[5]])


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
        cols = list(zip(*listHours))
        array_hours = list(zip(cols[4], cols[8]))
        array_overtime = list(zip(cols[5], cols[8]))

        dct_hours = {}
        dct_overtime = {}

        for time, weekbegin in array_hours:
            if time is not 0:
                dct_hours.setdefault(weekbegin,timedelta())
                (h,m)=time.split(':')
                d = timedelta(hours=int(h), minutes=int(m))
                dct_hours[weekbegin]+=d

        for time, weekbegin in array_overtime:
            dct_overtime.setdefault(weekbegin,timedelta())#timedelta()
            (h,m)=time.split(':')
            d = timedelta(hours=int(h), minutes=int(m))
            dct_overtime[weekbegin]+=d

        weeks = [i[0] for i in dct_hours.items()] # get keys which are the week beginnings

        return dct_hours, dct_overtime, weeks
    else: # when new user or no data
        return 0,0,[]

def getCumul(week_Begin, listHours):
    if listHours != []:
        dct_hours, dct_overtime, wks = weeklySum2(listHours)
        if isinstance(week_Begin, str):
            cumul_hrs = strfdelta(dct_hours[datetime.fromisoformat(week_Begin)], '%H:%M')
            cumul_overtime = strfdelta(dct_overtime[datetime.fromisoformat(week_Begin)], '%H:%M')
            return cumul_hrs, cumul_overtime, datetime.fromisoformat(week_Begin)
        else:
            cumul_hrs = strfdelta(dct_hours[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            cumul_overtime = strfdelta(dct_overtime[week_Begin.replace(hour=0, minute=0, second=0, microsecond=0)], '%H:%M')
            return cumul_hrs, cumul_overtime, week_Begin
    else:
        return 0,0,0



# TEST PAGE -- DELETES WORK DB DATA
@app.route('/start')
def start():
    # TESTING: DELETE WORK DB ROWS
    db.session.query(Work).delete()
    db.session.commit()

    return render_template('startpage.html')


# this will be the main page, with the hours form etc
@app.route('/index', methods=['GET', 'POST'])
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
        week_beginning = (dateEntry - timedelta(days=dateEntry.weekday()))

        if holSick == False:
            mergedDate_StartTime = datetime.combine(dateEntry, stime)
            mergedDate_EndTime = datetime.combine(dateEntry, etime)
            mergedDate_Driving = datetime.combine(dateEntry, drivingHrs)
        else:
            mergedDate_StartTime = None
            mergedDate_EndTime = None
            mergedDate_Driving = None

        hrs = Work(date=dateEntry, holiday_sick=holSick, start_time=mergedDate_StartTime, end_time=mergedDate_EndTime, driving_hours=mergedDate_Driving, week_beginning=week_beginning, user_id=curUserId)
        db.session.add(hrs)
        db.session.commit()

        listHours = listDates(curUserId)

        return redirect(url_for('index'))

    # row deletion
    if request.method == 'POST':
        if 'delete' in request.form:
            row_id = request.form['delete'] # gets the row id from the delete button
            if row_id is not None:
                deleteRow(row_id)
                listHours = listDates(current_user.get_id())
                return redirect(url_for('index'))
        elif 'cumuls' in request.form:
            week_Begin = request.form['cumuls']
            if week_Begin is not None:
                listHours = listDates(current_user.get_id())
                dct_hours, dct_overtime, wks = weeklySum2(listHours)
                #print(week_Begin)
                cumul_hrs, cumul_overtime, week_Begin_dt = getCumul(week_Begin, listHours)
                week_Begin_dt = week_Begin_dt.strftime('%A %-d %b %Y')
                return redirect(url_for('index', cumul_hrs=cumul_hrs, cumul_overtime=cumul_overtime, week=week_Begin_dt))

    listHours = listDates(current_user.get_id())

    dct_hours, dct_overtime, wks = weeklySum2(listHours)
    #print(wks)
    wks2 = [wkbgn.strftime('%A') + ' ' + wkbgn.strftime('%-d') + ' ' + wkbgn.strftime('%b') + ' ' + wkbgn.strftime('%Y') for wkbgn in wks]

    # gets current week cumulatives
    currWeeklyHours, currWeeklyOvertime = getWeeklySum(listHours)

    cumul_hrs, cumul_overtime, week = request.args.get('cumul_hrs'), request.args.get('cumul_overtime'),request.args.get('week')

    return render_template('index.html', form=form, hoursDb = listHours, wks=wks, wks2=wks2, zip=zip, cumul_hrs=cumul_hrs, cumul_overtime=cumul_overtime, currWeeklyHours=currWeeklyHours, currWeeklyOvertime=currWeeklyOvertime, week=week)




@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    # redirects to index() route if user already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm() # create object of LoginForm class from forms.py
    if form.validate_on_submit():
        # load user from database; filter_by query only includes objs that have a matching username
        # first --> used when you only need to have one result; return user obj if exists, or None if it doesn't;
        user = User.query.filter_by(username=form.username.data).first()
        # if user doesn't exist or password incorrect, display flash and redirect to login page
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        # if username and password both correct, register user as logged in
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect('index')
    return render_template('login.html', title='Sign In', form=form)

# route for if user wants to logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # creates database entry with regsiter entry
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Congratulations, you are now registered!')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', form=form)

@app.route('/mydata')
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

    print('dct_hours')
    print(dct_hours)

    dct_hours = {k.date():strfdelta(v,'%H:%M') for k,v in dct_hours.items()}
    dct_overtime = {k.date():strfdelta(v,'%H:%M') for k,v in dct_overtime.items()}

    srs_hours = pd.Series(dct_hours).to_frame('Cumulative Hrs')
    srs_overtime = pd.Series(dct_overtime).to_frame('Cumulative Overtime')

    test_data = (pd.concat([test_data, srs_hours, srs_overtime], axis=1, sort=True)).fillna('')
    print(test_data)

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
