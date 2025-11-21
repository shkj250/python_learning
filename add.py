def add(a,b):
    return a+b
def abs(x):
    if x>=0:
        return x
    else:
        return -x
    

class Person:
    # 修改 __init__ 方法，增加 name 和 age 参数
    def __init__(self, name="张三", age=20):
        self.name = name
        self.age = age   
    def info(self):
        return f"姓名：{self.name}，年龄：{self.age}"
    def set_name(self,name):
        self.name = name
    def set_age(self,age):
        self.age = age
