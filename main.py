import sublime
import sublime_plugin
import re
import urllib.request
import json
import subprocess
import os
import base64
from urllib import parse

help_info = """
\n\n----------Upper----------\n\n
ctrl+alt+u 大写转换
ctrl+alt+l 小写转换
ctrl+alt+q 将Mybatis日志转换为sql
ctrl+alt+/ 格式化sql/json
ctrl+alt+s 执行shell命令
ctrl+alt+c 执行cmd命令
ctrl+alt+o 打开文件夹/网站/文件等
ctrl+alt+m sql表结构初始化mybatis、java数据结构
ctrl+alt+n Json压缩
ctrl+alt+t 测试命令
ctrl+alt+h 帮助命令
ctrl+alt+p 执行python脚本
ctrl+alt+f 正则提取内容
... 更多功能见右键弹出菜单

curl 有tab键提示补全功能
"""

# 当前命令文件夹
current_dir = ""

# 标准配置
stand_config = None
# 模块默认配置
my_config = None

# 获取配置
def get_config(key):
    global stand_config, my_config
    if stand_config is None:
        stand_config = sublime.load_settings("Preferences.sublime-settings")
    if my_config is None:
        my_config = sublime.load_settings("MyTextUtil.sublime-settings")
    val = stand_config.get(key)
    if val is None:
        val = my_config.get(key)
    return val

def sql_format(sql):
    sql = "query=" + sql
    req = urllib.request.urlopen("https://www.w3cschool.cn/statics/demosource/tools/toolsAjax.php?action=sql_formatter",bytes(sql, "utf-8"))
    res = req.read()
    req.close()
    res = res.decode('unicode_escape')
    res = re.findall('"result":"([\s\S]+?)"',res)
    return res[0]

def log2sql(sql, split):
    csql = re.compile("Preparing: (.*?)\n")
    carg = re.compile("Parameters: (.*?)\n")

    psql = re.findall(csql, sql)
    parg = re.findall(carg, sql)
    if len(psql) != len(parg):
        return ""
    res = ""
    for i in range(len(psql)):
        res += split
        sarg = re.sub(r"\(.*?\)","",parg[i])
        args = sarg.split(",")
        pt = psql[i]
        for k in args:
            arg = "'"+k.strip()+"'"
            pt = pt.replace("?", arg, 1)
        res += pt
    return res

def tocamel(s):
    s = s.lower()
    s = s.replace(".", "_")
    ss = s.split("_")
    res = ""
    for i in range(len(ss)):
        if ss[i] == "":
            continue
        if i == 0:
            res += ss[i]
        else:
            res += ss[i][0].upper()
            if len(ss[i]) >= 2:
                res+=ss[i][1:]
    return res

javaSql = {
  "Integer": ("TINYINT"),
  "Long": ("SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT", "INTEGER"),
  "BigDecimal": ("FLOAT", "DOUBLE", "DECIMAL", "NUMBER", "FLOAT"),
  "Date": ("DATE", "TIME", "YEAR", "DATETIME", "TIMESTAMP")
}

mybatis = {
  "DATE": ("Date"),
  "DECIMAL": ("Integer", "Long", "BigDecimal")
}

def getJavaType(sqltype):
  for i in javaSql:
    if sqltype.startswith(javaSql[i]):
        return i
  return "String"

def getJdbctype(javatype):
  for i in mybatis:
    if javatype.startswith(mybatis[i]):
      return i
  return "VARCHAR"

def tocamelb(s):
  t = tocamel(s)
  res = t[0].upper()
  if len(t) >= 2:
    res += t[1:]
  return res

def mybatisGen(sql):
  sql = sql.upper()
  sql = sql.replace("`", "")
  p=re.compile("CREATE\s*TABLE\s*(.+?)\s*\(([\s\S]+)\)")
  r=re.findall(p,sql)

  table = r[0][0]
  t = r[0][1].split(",")
  prop = []
  for i in t:
      line = i.strip()
      if line.startswith(("PRIMARY", "UNIQUE", "KEY")):
          continue
      line = re.sub("\s+", " ", line)
      prop.append(line.split(" "))

  java = "public class " + tocamelb(table) + " {\n"
  my = '<resultMap id="BaseResultMap" type="'+ tocamelb(table) +'">\n'
  for p in prop:
    jtype = getJavaType(p[1])
    mtype = getJdbctype(jtype)
    jf = tocamel(p[0])
    line = "    private " + jtype + " " + jf + ";\n"
    java += line
    my += '    <result column="'+ p[0] +'" property="'+ jf +'" jdbcType="'+ mtype +'" />\n'
  java += "}\n"
  my += "</resultMap>\n"
  return java + "\n\n" + my


def getSel(view):
    sel = view.sel()
    reg = sel[0]
    sels = view.substr(reg)
    if sels == "":
        reg = sublime.Region(0, view.size())
        sels = view.substr(reg) # 全部内容
    return reg, sels

# 转大写
class UpCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        reg, txt = getSel(self.view)
        txt = txt.upper()
        self.view.replace(edit, reg, txt)


# 转为小写
class LowCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        reg, txt = getSel(self.view)
        txt = txt.lower()
        self.view.replace(edit, reg, txt)

# mybatis日志sql解析
class SqlCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        reg, txt = getSel(self.view)
        split = "\n\n----------sql----------\n\n"
        self.view.replace(edit, reg, log2sql(txt, split))

# 格式化(sql/json)
class MyformatCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        reg, txt = getSel(self.view)
        txt = txt.strip()
        if txt.startswith(("{", "[")):
            # json
            self.view.replace(edit, reg, json.dumps(json.loads(txt), ensure_ascii=False, indent=4))
        else:
            # sql
            self.view.replace(edit, reg, sql_format(txt))

# json压缩（反格式化）
class NoformatCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        reg, txt = getSel(self.view)
        txt = txt.strip()
        if not txt.startswith(("{", "[")):
          return
        self.view.replace(edit, reg, json.dumps(json.loads(txt), ensure_ascii=False, separators=(',',':')))


# 系统命令执行(sh)
class ShCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global current_dir
        file = self.view.file_name()
        if file is not None and current_dir == "":
            current_dir = os.path.dirname(file)
        if current_dir != "":
            os.chdir(current_dir)
        reg, txt = getSel(self.view)
        res = "\n\n----------sh----------\n\n"
        subp = subprocess.Popen("sh",shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        subp.stdin.write(bytes(txt,encoding="utf-8"))
        tp = subp.communicate()
        t = tp[0].decode("utf-8") # 正确输出
        if t != "":
            res += t
        t2 = tp[1].decode("utf-8") # 其他输出
        if t2 != "":
            t2 = "\n\n----------Execute Output----------\n\n" + t2
            res = t2 + res
        if subp.poll() != 0:
            subp.kill()
        self.view.insert(edit, self.view.size(), res)

# 打开关联的文件夹/网站等
class OpenCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _, txt = getSel(self.view)
        subprocess.Popen('start "" "' + txt + '"', shell=True)

# sql表结构初始化mybatis、java数据结构
class MybatisCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _, txt = getSel(self.view)
        split = "\n\n----------mybatis----------\n\n"
        self.view.insert(edit, self.view.size(), split + mybatisGen(txt))

# 执行Python脚本
class PyCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _, txt = getSel(self.view)
        split = "\n\n----------Python----------\n\n"
        def out(x = ""):
            self.view.insert(edit, self.view.size(), str(x) + "\n")
        self.view.insert(edit, self.view.size(), split)
        exec(txt)

# 设置命令执行目录
class ChdirCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _, txt = getSel(self.view)
        global current_dir
        current_dir = txt

class MySyncCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        if args["op"] == "insert":
            self.view.insert(edit, self.view.size(), args["txt"])
        elif args["op"] == "replace":
            reg, txt = getSel(self.view)
            self.view.replace(edit, reg, args["txt"])

# 正则提取
class ExtractCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        def on_done(x): 
            _, txt = getSel(self.view)
            res = re.findall(x, txt)
            res = "\n".join(res)
            split = "\n\n----------Extract----------\n\n"
            self.view.run_command("my_sync", {"op": "insert", "txt": split + res})
        def on_change(x): pass
        def on_cancel(): pass
        sublime.Window.show_input_panel(self.view.window(), "Regex:", r"(\w+)", on_done, on_change, on_cancel)


# 请求本地服务器
def server_request(suf, txt):
    host = get_config("server_host")
    port = get_config("server_port")
    req = urllib.request.urlopen("http://" + host + ":" + port + "/" + suf, base64.b16encode(txt.encode("utf-8")).decode("utf-8").lower().encode())
    res = req.read()
    req.close()
    res = res.decode('utf-8')
    return res

# 编码解码
class EndecodeCommand(sublime_plugin.TextCommand):
    def __init__(self, x):
        super().__init__(x)
        self._server = None
    def run(self, edit, **args):
        reg, txt = getSel(self.view)
        def aes_en(x): 
            _, txt = getSel(self.view)
            txt = base64.b16encode(txt.encode("utf-8")).decode("utf-8").lower()
            txt = server_request("aes-en", '{"Pwd":"' + x.replace('"', "\\\"") + '","Txt":"' + txt + '"}')
            self.view.run_command("my_sync", {"op": "replace", "txt": txt})
        def aes_de(x): 
            _, txt = getSel(self.view)
            txt = server_request("aes-de", '{"Pwd":"' + x.replace('"', "\\\"") + '","Txt":"' + txt + '"}')
            self.view.run_command("my_sync", {"op": "replace", "txt": txt})
        def on_change(x): pass
        def on_cancel(): pass
        if args["func"] == "encoding-base64":
            txt = str(base64.b64encode(txt.encode("utf-8")), encoding="utf-8")
        elif args["func"] == "decoding-base64":
            txt = base64.b64decode(txt.encode("utf-8")).decode("utf-8")
        elif args["func"] == "encoding-url":
            txt = parse.quote(txt)
        elif args["func"] == "decoding-url":
            txt = parse.unquote(txt)
        elif args["func"] == "encoding-unicode":
            txt = str(txt.encode('unicode_escape'), encoding="utf-8")
        elif args["func"] == "decoding-unicode":
            txt = bytes(txt, encoding="utf-8").decode('unicode_escape')
        elif args["func"] == "encoding-hex":
            txt = base64.b16encode(txt.encode("utf-8")).decode("utf-8").lower()
        elif args["func"] == "decoding-hex":
            txt = base64.b16decode(txt.upper().encode("utf-8")).decode("utf-8")
        elif args["func"] == "encoding-aes":
            sublime.Window.show_input_panel(self.view.window(), "Password:", "password", aes_en, on_change, on_cancel)
            return
        elif args["func"] == "decoding-aes":
            sublime.Window.show_input_panel(self.view.window(), "Password:", "password", aes_de, on_change, on_cancel)
            return
        elif args["func"] == "start-server":
            # 开启后端服务
            start_server()
        else:
            return
        self.view.replace(edit, reg, txt)

# Google翻译接口
def google_translation(sl, tl, txt):
    # sl 源语言
    # tl 翻译后语言
    # txt 文本
    req = urllib.request.urlopen("http://translate.google.cn/translate_a/single?client=at&sl=" + sl + "&tl=" + tl + "&dt=t&q=" + parse.quote(txt))
    res = req.read()
    req.close()
    res=res.decode("utf-8")
    res=json.loads(res)
    return res[0][0][0]

# Google翻译接口获取tk
def get_tk(a, tkk):
    def RL(a, b):
        for d in range(0, len(b)-2, 3):
            c = b[d + 2]
            c = ord(c[0]) - 87 if 'a' <= c else int(c)
            c = a >> c if '+' == b[d + 1] else a << c
            a = a + c & 4294967295 if '+' == b[d] else a ^ c
        return a
    g = []
    f = 0
    while f < len(a):
        c = ord(a[f])
        if 128 > c:
            g.append(c)
        else:
            if 2048 > c:
                g.append((c >> 6) | 192)
            else:
                if (55296 == (c & 64512)) and (f + 1 < len(a)) and (56320 == (ord(a[f+1]) & 64512)):
                    f += 1
                    c = 65536 + ((c & 1023) << 10) + (ord(a[f]) & 1023)
                    g.append((c >> 18) | 240)
                    g.append((c >> 12) & 63 | 128)
                else:
                    g.append((c >> 12) | 224)
                    g.append((c >> 6) & 63 | 128)
            g.append((c & 63) | 128)
        f += 1
    e = tkk.split('.')
    h = int(e[0]) or 0
    t = h
    for item in g:
        t += item
        t = RL(t, '+-a^+6')
    t = RL(t, '+-3^+b+-f')
    t ^= int(e[1]) or 0
    if 0 > t:
        t = (t & 2147483647) + 2147483648
    result = t % 1000000
    return str(result) + '.' + str(result ^ h)

# Google翻译接口(不禁止IP，但是tkk需要去谷歌网页版找)
def google_translation_tk(sl, tl, txt):
    tk = get_tk(txt, get_config("google_translation_tkk"))
    url = "https://translate.google.cn/translate_a/single?client=webapp&sl=" + sl + "&tl=" + tl + "&hl=zh-CN&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=sos&dt=ss&dt=t&otf=1&ssel=0&tsel=0&kc=1&tk=" + tk + "&q=" + parse.quote(txt)
    req = urllib.request.urlopen(url)
    res = req.read()
    req.close()
    res=res.decode("utf-8")
    res=json.loads(res)
    return res[0][0][0]
# 翻译
class TranslationCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        reg, txt = getSel(self.view)
        txt = google_translation_tk(args["sl"], args["tl"], txt)
        self.view.replace(edit, reg, txt)

# 帮助信息
class MyhelpCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.insert(edit, self.view.size(), help_info)



# 自动提示
class MyTextUtil(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        subtype = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
        cmds = []
        cmds.append(["curl\tcurl -X POST...", """curl -X POST 'http://127.0.0.1:8080/demo' \\\n  -H "Content-Type: application/json" \\\n  --data-binary '{}'"""])
        return (cmds, subtype)

class TestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # sublime.Window.show_quick_panel(self.view.window(), ["Hello", "sdsf"], lambda x : print(x))
        pass

# 以下是初始化逻辑
import socket
import threading
import time
import platform

# 检测可执行文件是否存在
def exe_in_path(exe):
    if platform.system() == "Windows":
        exe = exe + ".exe"
    path = os.getenv("PATH")
    dirs = path.split(os.path.pathsep)
    for i in dirs:
        if os.path.exists(i + os.sep + exe) and os.path.isfile(i + os.sep + exe):
            return True
    return False

class MyUtilThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = ("127.0.0.1", int(get_config("echo_port")))
        while True:
            time.sleep(1)
            s.sendto(b'ok', addr)

def start_server():
    # 是否开启Server
    if not get_config("server_enabled"):
        return
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    # 判断程序是否存在
    exe = _base_dir + os.sep + "bin" + os.sep + "MyUtilServer"
    if platform.system() == "Windows":
        exe = exe + ".exe"
    if not os.path.exists(exe):
        print("Service program to be compiled...")
        # 判断是否安装Golang
        if not exe_in_path("go"):
            return
        # 判断bin目录是否存在
        if not os.path.exists(_base_dir + os.sep + "/bin"):
            os.mkdir(_base_dir + os.sep + "/bin")
        print("Building Server...")
        # 编译Server
        os.chdir(_base_dir + os.sep + "MyUtilServer")
        p = subprocess.Popen('go build -o ../bin', shell=True)
        p.wait()
    my = MyUtilThread()
    my.start()
    # 开启后端服务
    cmd = '"' + exe + '"' + ' -p ' + get_config("server_port") + ' -e ' + get_config("echo_port")
    print(cmd)
    subprocess.Popen(cmd, shell=True)
def plugin_loaded():
    server = threading.Thread(target=start_server)
    server.start()