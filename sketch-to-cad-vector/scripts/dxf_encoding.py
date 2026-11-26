import re
import sys

path = sys.argv[1]
raw = open(path, "rb").read()
m = re.search(rb"\\$DWGCODEPAGE\r?\n  3\r?\n([^\r\n]*)", raw)
print("文件:", path.split("\\")[-1], "大小", len(raw), "字节")
print("$DWGCODEPAGE =", m.group(1).decode("ascii", "replace") if m else "未找到")
head = raw[:200].decode("ascii", "replace").splitlines()
print("DXFVER = ASCII" if b"AC1032" in raw[:400] else f"版本标签 = {head[1] if len(head) > 1 else '?'}")
esc = raw.count(rb"\U+")
print("\\U+XXXX 转义出现次数 =", esc)
# 找非 ASCII 字节，判断是不是 GBK
nonascii = [b for b in raw if b > 127]
print("非 ASCII 字节数 =", len(nonascii))
if nonascii:
    try:
        txt = raw.decode("gbk")
        zh = set(re.findall(r"[一-鿿]", txt))
        print("按 GBK 解码可读中文:", "".join(sorted(zh))[:20] if zh else "无")
    except UnicodeDecodeError as e:
        print("GBK 解码失败:", e)
    try:
        txt = raw.decode("utf-8")
        zh = set(re.findall(r"[一-鿿]", txt))
        print("按 UTF-8 解码可读中文:", "".join(sorted(zh))[:20] if zh else "无")
    except UnicodeDecodeError as e:
        print("UTF-8 解码失败:", str(e)[:60])
