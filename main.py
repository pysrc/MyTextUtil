import sublime
import sublime_plugin
import re
import urllib.request
import json
import subprocess
import os

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

curl 有tab键提示补全功能
"""

def sql_format(sql):
    sql = "query=" + sql
    req = urllib.request.urlopen("https://www.w3cschool.cn/statics/demosource/tools/toolsAjax.php?action=sql_formatter",bytes(sql, "utf-8"))
    res = req.read()
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
  "BigBecimal": ("FLOAT", "DOUBLE", "DECIMAL", "NUMBER", "FLOAT"),
  "Date": ("DATE", "TIME", "YEAR", "DATETIME", "TIMESTAMP")
}

mybatis = {
  "DATE": ("Date"),
  "DECIMAL": ("Integer", "Long", "BigBecimal")
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
        file = self.view.file_name()
        if file is not None:
            pt = os.path.dirname(file)
            os.chdir(pt)
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
        subp.kill()
        self.view.insert(edit, self.view.size(), res)

# 打开关联的文件夹/网站等
class OpenCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _, txt = getSel(self.view)
        os.system('start "" "' + txt + '"')

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

class InsCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        self.view.insert(edit, self.view.size(), args["txt"])

# 正则提取
class ExtractCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        def on_done(x): 
            _, txt = getSel(self.view)
            res = re.findall(x, txt)
            res = "\n".join(res)
            split = "\n\n----------Extract----------\n\n"
            self.view.run_command("ins", {"txt": split + res})
        def on_change(x): pass
        def on_cancel(): pass
        sublime.Window.show_input_panel(self.view.window(), "正则内容提取:", r"(\w+)", on_done, on_change, on_cancel)

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
        sublime.Window.show_quick_panel(self.view.window(), ["Hello", "sdsf"], lambda x : print(x))
