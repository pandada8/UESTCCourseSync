import requests
import re
import logging
from pyquery import PyQuery as pq
import json
import pprint

logging.basicConfig()  # init a basic output in terminal

s = requests.session()

class APIError(Exception):
    pass

def lazyJsonParse(j):
    j = re.sub(r"{\s*'?(\w)", r'{"\1', j)
    j = re.sub(r",\s*'?(\w)", r',"\1', j)
    j = re.sub(r"(\w)'?\s*:", r'\1":', j)
    j = re.sub(r":\s*'(\w+)'\s*([,}])", r':"\1"\2', j)
    return json.loads(j)


class UESTC:

    def __init__(self):
        self.s = requests.session()
        self.s.headers.setdefault('Content-Language', 'zh_CN')
        self.s.headers.setdefault('X-Requested-With', 'XMLHttpRequest')
        self.s.headers.setdefault('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.22 Safari/537.36')
        self.logger = logging.getLogger('UESTC API')
        self.logger.setLevel(logging.INFO)

    def getToken(self):
        self.logger.info('获取登陆令牌...')
        html = self.s.get("https://uis.uestc.edu.cn/amserver/UI/Login", params={'goto':'http://portal.uestc.edu.cn/login.portal'}).text
        token = re.search(r'(?<=value=")[a-zA-Z0-9]{52}(?=">)',html)
        if token:
            self.logger.debug('登陆令牌: %s', token.group())
            return token.group()
        else:
            self.logger.critical('无效的令牌！')
            self.logger.debug('返回页面: \n%s',html)
            raise APIError

    def login(self, username, password):
        self.logger.info('开始登陆...')
        token = self.getToken()

        ret = self.s.post("https://uis.uestc.edu.cn/amserver/UI/Login", data={
            "IDToken0":"",
            "IDToken1":username,
            "IDToken2":password,
            "IDButton":"Submit",
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

    def getSemester(self):
        """
        get the semesters of the student
        """
        self.logger.info('载入学期...')
        self.s.get('http://eams.uestc.edu.cn/eams/courseTableForStd.action')
        # a trick to get the correct semster
        ret = self.s.post('http://eams.uestc.edu.cn/eams/dataQuery.action', data={
            "tagId":"semesterBar9375549431Semester",
            "dataType":"semesterCalendar",
            "empty":"true"
        })
        semsters = lazyJsonParse(ret.text)['semesters']
        ret = []
        for i in semsters.values():
            ret.extend(i)
        self.logger.info('载入学期成功, 共 %d 个学期', len(ret))
        return ret

    def _parseCourse(self, text):
        basicData = json.loads('[' + re.search(r"(?<=TaskActivity\().+?(?=\);)", text).group() + "]")
        basicData.append([(i[0],i[2]) for i in  re.findall(r'(\d+)(\*unitCount\+)(\d)', text)])
        return basicData

    def getCourse(self, semester, stu=True):
        self.logger.info('载入 %s 学年第 %s 学期的课程， 学期编号 %d ',semester['schoolYear'], semester['name'], semester['id'])
        source = self.s.post('http://eams.uestc.edu.cn/eams/courseTableForStd!courseTable.action', data={
            "ignoreHead": 1,
            "setting.kind": "std",  # only student supported now
            "startWeek": 1,
            "semesterId": semester['id'],
            "ids": '132081' if stu else "2463"  # unknow if this will change in different student or class
        }, headers={
            "Accept-Language": "zh-CN,zh;q=0.8"
        }).text
        self.logger.debug('课程RAW Requests: %s', source)
        # Strip the html code and get the js code
        courses = [self._parseCourse(i) for i in re.findall(r'activity\s=\snew[\s\S]*?=activity', source)]
        return courses


