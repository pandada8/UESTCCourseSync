import requests
import re
import logging
from pyquery import PyQuery as pq
import json
import icalendar
import datetime
import pytz
import hashlib


logging.basicConfig()  # init a basic output in terminal

s = requests.session()

CLASS_LENGTH = datetime.timedelta(minutes=45)

CLASS = {
    0: datetime.timedelta(hours=8, minutes=30),
    1: datetime.timedelta(hours=9, minutes=20),
    2: datetime.timedelta(hours=10, minutes=20),
    3: datetime.timedelta(hours=11, minutes=10),
    4: datetime.timedelta(hours=14, minutes=30),
    5: datetime.timedelta(hours=15, minutes=20),
    6: datetime.timedelta(hours=16, minutes=20),
    7: datetime.timedelta(hours=17, minutes=10),
    8: datetime.timedelta(hours=19, minutes=30),
    9: datetime.timedelta(hours=20, minutes=20),
    10: datetime.timedelta(hours=21, minutes=10),
    11: datetime.timedelta(hours=22, minutes=0)
}


def md5(s):
    return hashlib.md5(s.encode('UTF')).hexdigest()



class APIError(Exception):
    pass


def lazyJsonParse(j):
    '''
    this function is copied from stackoverflow
    '''
    j = re.sub(r"{\s*'?(\w)", r'{"\1', j)
    j = re.sub(r",\s*'?(\w)", r',"\1', j)
    j = re.sub(r"(\w)'?\s*:", r'\1":', j)
    j = re.sub(r":\s*'(\w+)'\s*([,}])", r':"\1"\2', j)
    return json.loads(j)


class Course():

    def __init__(self, data):
        self.id = data[2]
        self.name = data[3]
        self.teacherId = data[0]
        self.teacher = data[1]
        self.time = []

    def __repr__(self):
        return repr({
            "id": self.id,
            "name": self.name,
            "teacherId": self.teacherId,
            "teacher": self.teacher,
            "time": self.time
        })

    def __str__(self):
        return "{} - {}".format(self.teacher, self.name)


class User:

    def __init__(self):
        self.s = requests.session()
        self.s.headers.setdefault('Content-Language', 'zh_CN')
        self.s.headers.setdefault('X-Requested-With', 'XMLHttpRequest')
        self.s.headers.setdefault('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.22 Safari/537.36')
        self.logger = logging.getLogger('UESTC API')
        self.logger.setLevel(logging.INFO)

        self.courses = {}
        self.terms = []

    def getToken(self):
        self.logger.info('生成跳转网址...')
        html = self.s.get("https://uis.uestc.edu.cn/amserver/UI/Login", params={'goto': 'http://portal.uestc.edu.cn/login.portal'}).text
        token = re.search(r'(?<=value=")[a-zA-Z0-9]{52}(?=">)', html)
        if token:
            self.logger.debug('Jump Token: %s', token.group())
            return token.group()
        else:
            self.logger.critical('生成失败')
            self.logger.debug('returned data: \n%s', html)
            raise APIError

    def login(self, username, password):
        self.logger.info('开始登陆...')
        token = self.getToken()

        ret = self.s.post("https://uis.uestc.edu.cn/amserver/UI/Login", data={
            "IDToken0": "",
            "IDToken1": username,
            "IDToken2": password,
            "IDButton": "Submit",
            "goto": token,
            "encoded": "true",
            "gx_charset": "UTF-8"
        })
        if ret.url == "http://portal.uestc.edu.cn/index.portal":
            self.logger.info('登陆成功')
        else:
            reason = pq(ret.text)('.AlrtErrTxt').text()
            self.logger.critical('登录失败: %s', reason)
            raise APIError

    def getName(self):
        data = self.s.get('http://eams.uestc.edu.cn/eams/security/my.action').text
        soup = pq(data)
        self.name = soup.find("#olnks em").text()
        return self.name

    def getSemester(self):
        """
        get the semesters of the student
        """
        self.logger.info('载入学期...')
        self.s.get('http://eams.uestc.edu.cn/eams/courseTableForStd.action')
        # a trick to get the correct semster
        # the api require some cookies to be properly filled
        ret = self.s.post('http://eams.uestc.edu.cn/eams/dataQuery.action', data={
            "tagId": "semesterBar9375549431Semester",
            "dataType": "semesterCalendar",
            "empty": "true"
        })
        semsters = lazyJsonParse(ret.text)['semesters']
        ret = []
        for i in semsters.values():
            ret.extend(i)
        self.logger.info('载入学期成功, 共 %d 个学期', len(ret))
        self.terms = ret
        return ret

    def getClasses(self, term_id):
        def parseCourse(text):
            temp = json.loads('[' + re.search(r"(?<=TaskActivity\().+?(?=\);)", text).group() + "]")
            basicData = Course(temp)
            for i in re.findall(r'(\d+)(\*unitCount\+)(\d+);', text):
                basicData.time.append({"weekday": int(i[0]), "time": [int(i[2])], "week": temp[-1], "location": temp[5]})
            return basicData

        if term_id not in self.courses:
            source = self.s.post('http://eams.uestc.edu.cn/eams/courseTableForStd!courseTable.action', data={
                "ignoreHead": 1,
                "setting.kind": "std",  # only student supported now
                "startWeek": 1,
                "semesterId": term_id,
                "ids": '132081'  # unknow if this will change in different student or class
            }, headers={
                "Accept-Language": "zh-CN,zh;q=0.8"
            }).text
            # Strip the html code and get the js code
            courses = [parseCourse(i[0]) for i in re.findall(r'(activity\s=\s.*(\s+\bindex[\s\S]*?activity;)+)', source)]
            # merge the same course
            _courses = {}
            for i in courses:
                if i.id in _courses:
                    _courses[i.id].time.extend(i.time)
                else:
                    _courses[i.id] = i
            # merge the sibling course
            course = _courses.values()
            for i in course:
                time, i.time = i.time, []
                for t in time:
                    for ft in i.time:
                        if abs(t['time'][0] - ft['time'][0]) == 1 and t['weekday'] == ft['weekday']:
                            ft['time'].append(t['time'][0])
                            break
                    else:
                        i.time.append(t)

            self.courses[term_id] = list(_courses.values())
            return self.courses[term_id]
        else:
            return self.courses[term_id]

    def genTable(self, term_id, the_first_day):
        """
        the first day means the first monday of the first week.
        """
        table = icalendar.Calendar()
        table.add('PRODID', '-//Sync Course//course.pandada8.me//')
        table.add('version', '2.0')
        table.add('X-WR-CALNAME', '{}的课表'.format(self.name))
        table.add('X-WR-CALDESC', '{}的课表，由Sync生成'.format(self.name))
        table.add('X-WR-TIMEZONE', "Asia/Shanghai")
        table.add('CALSCALE', 'GREGORIAN')
        table.add('METHOD', 'PUBLISH')

        tz = pytz.timezone('Asia/Shanghai')
        _now = datetime.datetime.now()
        now = tz.localize(_now)
        if term_id in self.courses:
            for i in self.courses[term_id]:
                for t in i.time:
                    for n, w in enumerate(t['week'][1:]):
                        if int(w):
                            targetTime = datetime.timedelta(days=7*n + t['weekday']) + the_first_day + CLASS[min(t['time'])]
                            targetEndTime = datetime.timedelta(days=7*n + t['weekday'], minutes=45) + the_first_day + CLASS[max(t['time'])]
                            e = icalendar.Event()
                            e.add('dtstart', tz.localize(targetTime))
                            e.add('dtend', tz.localize(targetEndTime))
                            e['summary'] = "{} {}老师 {}".format(i.name.split('(')[0], i.teacher, t['location'])
                            e['location'] = icalendar.vText(t['location'])
                            # e['SEQUENCE'] = 1
                            e['TRANSP'] = icalendar.vText('OPAQUE')
                            e['status'] = 'confirmed'
                            e.add('created', now)
                            e.add('DTSTAMP', _now)
                            e["UID"] = '{}@sync.pandada8.me'.format(md5(str(targetTime) + i.name))
                            e.add('LAST-MODIFIED', _now)

                            table.add_component(e)
        return table


def sync():
    import getpass
    print(r"""
 ___  ___  _______   ________  _________  ________
|\  \|\  \|\  ___ \ |\   ____\|\___   ___\\   ____\
\ \  \\\  \ \   __/|\ \  \___|\|___ \  \_\ \  \___|
 \ \  \\\  \ \  \_|/_\ \_____  \   \ \  \ \ \  \
  \ \  \\\  \ \  \_|\ \|____|\  \   \ \  \ \ \  \____
   \ \_______\ \_______\____\_\  \   \ \__\ \ \_______\
    \|_______|\|_______|\_________\   \|__|  \|_______|
                       \|_________|
  """)

    u = User()
    username = input('输入你的学号：')
    password = getpass.getpass('输入密码：')
    u.login(username, password)
    u.getSemester()
    for i in u.terms:
        print("[{id:>2}] {schoolYear} 学年 {name} 学期".format_map(i))
    semsterId = int(input("输入学期:"))
    day = input('请输入开学第一周中某一天工作日(YYYY/MM/DD)：')
    day = datetime.datetime.strptime(day, "%Y/%m/%d")
    day = day - datetime.timedelta(days=day.weekday())
    u.getClasses(semsterId)
    with open(u.getName() + '.ics', 'wb') as fp:
        fp.write(u.genTable(semsterId, day).to_ical())
    print('成功导出！')

if __name__ == "__main__":
    sync()
